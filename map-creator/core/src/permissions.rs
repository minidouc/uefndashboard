use crate::config::{load_permissions_config, now_utc, RootPaths};
use crate::protocol::ServerEvent;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::path::{Component, Path, PathBuf};
use std::sync::Arc;
use tokio::sync::{broadcast, oneshot, Mutex};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Decision {
    Allow,
    Ask,
    Deny,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermissionEvaluation {
    pub decision: Decision,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PendingApproval {
    pub approval_id: String,
    pub role: String,
    pub action: String,
    pub target: String,
    pub reason: String,
    pub created_at: String,
}

struct WaitingApproval {
    meta: PendingApproval,
    responder: oneshot::Sender<bool>,
}

pub struct PermissionEngine {
    paths: RootPaths,
    pending: Arc<Mutex<HashMap<String, WaitingApproval>>>,
    events_tx: broadcast::Sender<ServerEvent>,
}

impl PermissionEngine {
    pub fn new(paths: RootPaths, events_tx: broadcast::Sender<ServerEvent>) -> Self {
        Self {
            paths,
            pending: Arc::new(Mutex::new(HashMap::new())),
            events_tx,
        }
    }

    pub fn evaluate_action(
        &self,
        action: &str,
        target: Option<&str>,
        role_readonly: bool,
    ) -> PermissionEvaluation {
        let cfg = match load_permissions_config(&self.paths) {
            Ok(c) => c,
            Err(e) => {
                return PermissionEvaluation {
                    decision: Decision::Deny,
                    reason: format!("Politique de permissions illisible (fail-closed): {e}"),
                }
            }
        };

        if role_readonly && is_mutating_action(action) {
            return PermissionEvaluation {
                decision: Decision::Deny,
                reason: format!("Rôle en lecture seule : action '{action}' interdite"),
            };
        }

        // Check file write paths with strict canonical anti-traversal
        if action == "write_file" {
            let Some(t) = target else {
                return PermissionEvaluation {
                    decision: Decision::Deny,
                    reason: "Chemin cible manquant pour write_file".into(),
                };
            };
            let rel = match self.normalize_relative_path(t) {
                Ok(r) => r,
                Err(msg) => {
                    return PermissionEvaluation {
                        decision: Decision::Deny,
                        reason: msg,
                    }
                }
            };
            for pat in &cfg.protected_paths.deny_write {
                if glob_matches(pat, &rel) {
                    return PermissionEvaluation {
                        decision: Decision::Deny,
                        reason: format!(
                            "CHEMIN PROTÉGÉ (DENY dur) : '{rel}' correspond à '{pat}'"
                        ),
                    };
                }
            }
            for pat in &cfg.protected_paths.allow_write {
                if glob_matches(pat, &rel) {
                    return PermissionEvaluation {
                        decision: Decision::Allow,
                        reason: format!("Chemin autorisé par politique ({pat})"),
                    };
                }
            }
        }

        // Check shell commands
        if action == "run_shell" {
            let Some(cmd) = target else {
                return PermissionEvaluation {
                    decision: Decision::Deny,
                    reason: "Commande shell vide".into(),
                };
            };
            let lower = cmd.to_lowercase();
            for pat in &cfg.shell.deny_patterns {
                if lower.contains(&pat.to_lowercase()) {
                    return PermissionEvaluation {
                        decision: Decision::Deny,
                        reason: format!("Commande shell interdite par motif '{pat}'"),
                    };
                }
            }
            let trimmed = cmd.trim();
            for prefix in &cfg.shell.allow_prefixes {
                if trimmed.starts_with(prefix) && !trimmed.contains(';') && !trimmed.contains("&&") && !trimmed.contains('|') {
                    return PermissionEvaluation {
                        decision: Decision::Allow,
                        reason: format!("Commande lecture seule autorisée ({prefix})"),
                    };
                }
            }
        }

        let level = cfg
            .defaults
            .get(action)
            .map(String::as_str)
            .unwrap_or("ask");

        match level {
            "allow" => PermissionEvaluation {
                decision: Decision::Allow,
                reason: format!("Autorisé par défaut ({action})"),
            },
            "deny" => PermissionEvaluation {
                decision: Decision::Deny,
                reason: format!("Refusé par défaut ({action})"),
            },
            _ => PermissionEvaluation {
                decision: Decision::Ask,
                reason: format!("Approbation humaine requise pour '{action}'"),
            },
        }
    }

    pub fn normalize_relative_path(&self, raw: &str) -> Result<String, String> {
        let p = Path::new(raw);
        let joined = if p.is_absolute() {
            p.to_path_buf()
        } else {
            self.paths.root.join(p)
        };
        let cleaned = lexically_clean(&joined);
        let root_clean = lexically_clean(&self.paths.root);
        let rel = cleaned.strip_prefix(&root_clean).map_err(|_| {
            format!(
                "Évasion hors sandbox détectée : '{}' hors de '{}'",
                raw,
                root_clean.display()
            )
        })?;
        Ok(rel.to_string_lossy().replace('\\', "/"))
    }

    /// Enforces permission, blocking on human approval via App Server if `Ask`.
    pub async fn require_permission(
        &self,
        role: &str,
        action: &str,
        target: &str,
        role_readonly: bool,
        auto_approve_for_human_api: bool,
    ) -> Result<(), String> {
        let eval = self.evaluate_action(action, Some(target), role_readonly);
        match eval.decision {
            Decision::Allow => Ok(()),
            Decision::Deny => Err(format!("PERMISSION_DENIED: {}", eval.reason)),
            Decision::Ask => {
                if auto_approve_for_human_api {
                    return Ok(());
                }
                let approval_id = format!("apr_{}", &uuid::Uuid::new_v4().to_string()[..8]);
                let meta = PendingApproval {
                    approval_id: approval_id.clone(),
                    role: role.to_string(),
                    action: action.to_string(),
                    target: target.to_string(),
                    reason: eval.reason.clone(),
                    created_at: now_utc(),
                };
                let (tx, rx) = oneshot::channel();
                {
                    let mut map = self.pending.lock().await;
                    map.insert(
                        approval_id.clone(),
                        WaitingApproval {
                            meta: meta.clone(),
                            responder: tx,
                        },
                    );
                }
                let _ = self.events_tx.send(ServerEvent::new(
                    "permission.requested",
                    serde_json::to_value(&meta).unwrap_or(Value::Null),
                ));

                // Wait up to 120 seconds for human decision
                let approved = match tokio::time::timeout(
                    std::time::Duration::from_secs(120),
                    rx,
                )
                .await
                {
                    Ok(Ok(val)) => val,
                    _ => {
                        let mut map = self.pending.lock().await;
                        map.remove(&approval_id);
                        false
                    }
                };

                let _ = self.events_tx.send(ServerEvent::new(
                    "permission.resolved",
                    serde_json::json!({
                        "approval_id": approval_id,
                        "approved": approved
                    }),
                ));

                if approved {
                    Ok(())
                } else {
                    Err(format!(
                        "PERMISSION_REJECTED: approbation humaine refusée ou expirée ({action} sur {target})"
                    ))
                }
            }
        }
    }

    pub async fn list_pending(&self) -> Vec<PendingApproval> {
        let map = self.pending.lock().await;
        map.values().map(|w| w.meta.clone()).collect()
    }

    pub async fn resolve(&self, approval_id: &str, approved: bool) -> Result<bool, String> {
        let waiting = {
            let mut map = self.pending.lock().await;
            map.remove(approval_id)
        };
        match waiting {
            Some(w) => {
                let _ = w.responder.send(approved);
                Ok(true)
            }
            None => Err(format!("Demande d'approbation introuvable : {approval_id}")),
        }
    }
}

fn is_mutating_action(action: &str) -> bool {
    matches!(
        action,
        "write_file" | "run_shell" | "mcp_write" | "outbox_submit" | "outbox_dispatch"
    )
}

fn lexically_clean(path: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for comp in path.components() {
        match comp {
            Component::CurDir => {}
            Component::ParentDir => {
                out.pop();
            }
            other => out.push(other.as_os_str()),
        }
    }
    out
}

/// Simple glob matcher supporting `*`, `?`, and `**`.
pub fn glob_matches(pattern: &str, text: &str) -> bool {
    let p: Vec<char> = pattern.chars().collect();
    let t: Vec<char> = text.chars().collect();
    glob_dp(&p, &t)
}

fn glob_dp(p: &[char], t: &[char]) -> bool {
    let (m, n) = (p.len(), t.len());
    let mut dp = vec![vec![false; n + 1]; m + 1];
    dp[0][0] = true;
    for i in 1..=m {
        if p[i - 1] == '*' {
            dp[i][0] = dp[i - 1][0];
        }
    }
    for i in 1..=m {
        for j in 1..=n {
            if p[i - 1] == '*' {
                let is_double = (i >= 2 && p[i - 2] == '*') || (i < m && p[i] == '*');
                if is_double {
                    dp[i][j] = dp[i - 1][j] || dp[i][j - 1];
                } else {
                    dp[i][j] = dp[i - 1][j] || (t[j - 1] != '/' && dp[i][j - 1]);
                }
            } else if p[i - 1] == '?' || p[i - 1] == t[j - 1] {
                dp[i][j] = dp[i - 1][j - 1];
            }
        }
    }
    dp[m][n]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_glob_matches() {
        assert!(glob_matches("validators/**", "validators/MANIFEST.json"));
        assert!(glob_matches("validators/**", "validators/golden/cas/sain.json"));
        assert!(glob_matches(
            "workspace/projects/*/outbox/pending/**",
            "workspace/projects/neo-kyoto/outbox/pending/lot_01.json"
        ));
        assert!(!glob_matches(
            "workspace/projects/*/outbox/pending/**",
            "workspace/projects/neo-kyoto/outbox/responses/lot_01.json"
        ));
    }
}
