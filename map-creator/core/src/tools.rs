use crate::config::{load_app_config, write_atomic, RootPaths};
use crate::mcp::McpHost;
use crate::memory::MemoryStore;
use crate::outbox::OutboxEngine;
use crate::permissions::PermissionEngine;
use crate::pipeline::PipelineStore;
use crate::planner::PlannerEngine;
use crate::validators::ValidatorEngine;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fs;
use std::sync::Arc;
use tokio::process::Command;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolExecution {
    pub tool: String,
    pub ok: bool,
    pub output: Value,
    pub error: Option<String>,
}

pub struct ToolRegistry {
    pub paths: RootPaths,
    pub perms: Arc<PermissionEngine>,
    pub mcp: Arc<McpHost>,
}

impl ToolRegistry {
    pub fn new(paths: RootPaths, perms: Arc<PermissionEngine>, mcp: Arc<McpHost>) -> Self {
        Self { paths, perms, mcp }
    }

    pub fn tool_definitions(&self) -> Vec<Value> {
        vec![
            json!({
                "name": "read_file",
                "description": "Lit un fichier dans le workspace Map Creator (lecture seule, tronqué à 8 Ko).",
                "parameters": { "type": "object", "required": ["path"], "properties": { "path": { "type": "string" } } }
            }),
            json!({
                "name": "write_file",
                "description": "Écrit un fichier dans une zone autorisée (outbox/pending, deliverables, plans). Chemins protégés refusés.",
                "parameters": { "type": "object", "required": ["path", "content"], "properties": { "path": { "type": "string" }, "content": { "type": "string" } } }
            }),
            json!({
                "name": "list_dir",
                "description": "Liste les fichiers d'un dossier du workspace.",
                "parameters": { "type": "object", "required": ["path"], "properties": { "path": { "type": "string" } } }
            }),
            json!({
                "name": "run_shell",
                "description": "Exécute une commande shell (soumise au moteur de permissions allow/ask/deny).",
                "parameters": { "type": "object", "required": ["command"], "properties": { "command": { "type": "string" } } }
            }),
            json!({
                "name": "state_show",
                "description": "Lit le résumé borné (< 20 Ko) de l'état du projet actif.",
                "parameters": { "type": "object", "properties": { "project": { "type": "string" } } }
            }),
            json!({
                "name": "library_search",
                "description": "Cherche dans la bibliothèque réutilisable (Niveau 3) AVANT de produire.",
                "parameters": { "type": "object", "properties": { "query": { "type": "string" }, "category": { "type": "string" } } }
            }),
            json!({
                "name": "plan_check",
                "description": "Vérifie géométrie, collisions, flottants, accessibilité, raisons et budget mémoire d'un plan 4 couches.",
                "parameters": { "type": "object", "required": ["district_id"], "properties": { "district_id": { "type": "string" } } }
            }),
            json!({
                "name": "outbox_submit",
                "description": "Prépare un lot dans outbox/pending/ à partir d'un plan validé.",
                "parameters": { "type": "object", "required": ["district_id", "lot_id"], "properties": { "district_id": { "type": "string" }, "lot_id": { "type": "string" } } }
            }),
            json!({
                "name": "validator_run",
                "description": "Lance les validateurs protégés (MANIFEST SHA-256 -> Golden Set 20 cas -> Règles réelles).",
                "parameters": { "type": "object", "properties": { "golden_only": { "type": "boolean" } } }
            }),
            json!({
                "name": "mcp_call",
                "description": "Appelle un outil MCP via la passerelle unique (allowlist + circuit breakers).",
                "parameters": { "type": "object", "required": ["server", "tool"], "properties": { "server": { "type": "string" }, "tool": { "type": "string" }, "write": { "type": "boolean" }, "arguments": { "type": "object" } } }
            }),
        ]
    }

    pub async fn execute(
        &self,
        role: &str,
        role_readonly: bool,
        project_slug: &str,
        tool: &str,
        args: &Value,
    ) -> ToolExecution {
        let cfg = load_app_config(&self.paths);
        if let Ok(c) = &cfg {
            if !c.tools.enabled.iter().any(|t| t == tool) {
                return ToolExecution {
                    tool: tool.to_string(),
                    ok: false,
                    output: Value::Null,
                    error: Some(format!("TOOL_DISABLED : '{tool}' n'est pas activé dans config/app.toml")),
                };
            }
        }

        let res = match tool {
            "read_file" => self.tool_read_file(role, role_readonly, args).await,
            "write_file" => self.tool_write_file(role, role_readonly, args).await,
            "list_dir" => self.tool_list_dir(role, role_readonly, args).await,
            "run_shell" => self.tool_run_shell(role, role_readonly, args).await,
            "state_show" => {
                let slug = args.get("project").and_then(Value::as_str).unwrap_or(project_slug);
                let store = PipelineStore::new(self.paths.clone());
                store.load_state(slug).map(|(st, bytes)| {
                    json!({ "bytes": bytes, "max_bytes": 20000, "state": st })
                })
            }
            "library_search" => {
                let q = args.get("query").and_then(Value::as_str).unwrap_or("");
                let cat = args.get("category").and_then(Value::as_str);
                let mem = MemoryStore::new(self.paths.clone());
                let hits = mem.search_library(q, cat, false);
                Ok(json!({ "count": hits.len(), "entries": hits }))
            }
            "plan_check" => {
                let did = args
                    .get("district_id")
                    .and_then(Value::as_str)
                    .unwrap_or("district_plaza");
                let planner = PlannerEngine::new(self.paths.clone());
                planner
                    .load_plan(project_slug, did)
                    .map(|p| serde_json::to_value(planner.check_plan(&p)).unwrap_or(Value::Null))
            }
            "outbox_submit" => {
                let did = args
                    .get("district_id")
                    .and_then(Value::as_str)
                    .unwrap_or("district_plaza");
                let lot_id = args
                    .get("lot_id")
                    .and_then(Value::as_str)
                    .unwrap_or("lot_02");
                match self
                    .perms
                    .require_permission(role, "outbox_submit", lot_id, role_readonly, false)
                    .await
                {
                    Ok(()) => {
                        let ob = OutboxEngine::new(self.paths.clone(), self.mcp.clone());
                        ob.submit_from_plan(
                            project_slug,
                            did,
                            &["a_scene".into(), "b_fonds".into()],
                            lot_id,
                            "3_GRAYBOX",
                        )
                        .map(|j| serde_json::to_value(j).unwrap_or(Value::Null))
                    }
                    Err(e) => Err(e),
                }
            }
            "validator_run" => {
                let golden_only = args
                    .get("golden_only")
                    .and_then(Value::as_bool)
                    .unwrap_or(false);
                let val = ValidatorEngine::new(self.paths.clone());
                let rep = val.run_all(project_slug, golden_only);
                Ok(json!({
                    "verdict": rep.verdict,
                    "manifest_integrity": rep.manifest_integrity,
                    "golden_set_passed": rep.golden_set_passed,
                    "golden_total": rep.golden_total,
                    "lot_verdicts": rep.lot_verdicts
                }))
            }
            "mcp_call" => {
                let server = args
                    .get("server")
                    .and_then(Value::as_str)
                    .unwrap_or("uefn_editor");
                let mtool = args
                    .get("tool")
                    .and_then(Value::as_str)
                    .unwrap_or("SceneTools.get_current_level");
                let write = args.get("write").and_then(Value::as_bool).unwrap_or(false);
                let margs = args.get("arguments").cloned().unwrap_or_else(|| json!({}));
                let action = if write { "mcp_write" } else { "mcp_read" };
                match self
                    .perms
                    .require_permission(role, action, mtool, role_readonly, false)
                    .await
                {
                    Ok(()) => {
                        let r = self
                            .mcp
                            .call(project_slug, server, mtool, margs, write, None)
                            .await;
                        Ok(serde_json::to_value(r).unwrap_or(Value::Null))
                    }
                    Err(e) => Err(e),
                }
            }
            other => Err(format!("Outil inconnu : {other}")),
        };

        match res {
            Ok(val) => ToolExecution {
                tool: tool.to_string(),
                ok: true,
                output: val,
                error: None,
            },
            Err(e) => ToolExecution {
                tool: tool.to_string(),
                ok: false,
                output: Value::Null,
                error: Some(e),
            },
        }
    }

    async fn tool_read_file(
        &self,
        role: &str,
        role_readonly: bool,
        args: &Value,
    ) -> Result<Value, String> {
        let raw_path = args
            .get("path")
            .and_then(Value::as_str)
            .ok_or("Paramètre 'path' requis")?;
        let rel = self.perms.normalize_relative_path(raw_path)?;
        self.perms
            .require_permission(role, "read_file", &rel, role_readonly, false)
            .await?;
        let abs = self.paths.root.join(&rel);
        let content = fs::read_to_string(&abs)
            .map_err(|e| format!("Lecture '{rel}' impossible: {e}"))?;
        let truncated = if content.len() > 8000 {
            format!("{}...[TRONQUÉ à 8 Ko]", &content[..8000])
        } else {
            content
        };
        Ok(json!({ "path": rel, "content": truncated }))
    }

    async fn tool_write_file(
        &self,
        role: &str,
        role_readonly: bool,
        args: &Value,
    ) -> Result<Value, String> {
        let raw_path = args
            .get("path")
            .and_then(Value::as_str)
            .ok_or("Paramètre 'path' requis")?;
        let content = args
            .get("content")
            .and_then(Value::as_str)
            .ok_or("Paramètre 'content' requis")?;
        let rel = self.perms.normalize_relative_path(raw_path)?;
        self.perms
            .require_permission(role, "write_file", &rel, role_readonly, false)
            .await?;
        let abs = self.paths.root.join(&rel);
        write_atomic(&abs, content.as_bytes())?;
        Ok(json!({ "path": rel, "bytes_written": content.len() }))
    }

    async fn tool_list_dir(
        &self,
        role: &str,
        role_readonly: bool,
        args: &Value,
    ) -> Result<Value, String> {
        let raw_path = args.get("path").and_then(Value::as_str).unwrap_or(".");
        let rel = self.perms.normalize_relative_path(raw_path)?;
        self.perms
            .require_permission(role, "list_dir", &rel, role_readonly, false)
            .await?;
        let abs = self.paths.root.join(&rel);
        let mut entries = Vec::new();
        for e in fs::read_dir(&abs).map_err(|e| format!("list_dir '{rel}': {e}"))?.flatten() {
            let name = e.file_name().to_string_lossy().to_string();
            let is_dir = e.path().is_dir();
            entries.push(json!({ "name": name, "dir": is_dir }));
        }
        entries.sort_by(|a, b| a["name"].as_str().cmp(&b["name"].as_str()));
        Ok(json!({ "path": rel, "entries": entries }))
    }

    async fn tool_run_shell(
        &self,
        role: &str,
        role_readonly: bool,
        args: &Value,
    ) -> Result<Value, String> {
        let cmd = args
            .get("command")
            .and_then(Value::as_str)
            .ok_or("Paramètre 'command' requis")?;
        self.perms
            .require_permission(role, "run_shell", cmd, role_readonly, false)
            .await?;
        let out = Command::new("sh")
            .arg("-c")
            .arg(cmd)
            .current_dir(&self.paths.root)
            .output()
            .await
            .map_err(|e| format!("Exécution shell échouée: {e}"))?;
        let stdout = String::from_utf8_lossy(&out.stdout).to_string();
        let stderr = String::from_utf8_lossy(&out.stderr).to_string();
        Ok(json!({
            "exit_code": out.status.code().unwrap_or(-1),
            "stdout": &stdout[..stdout.len().min(4000)],
            "stderr": &stderr[..stderr.len().min(2000)]
        }))
    }
}
