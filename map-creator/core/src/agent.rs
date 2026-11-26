use crate::config::{load_app_config, now_utc, RootPaths};
use crate::memory::MemoryStore;
use crate::pipeline::PipelineStore;
use crate::protocol::ServerEvent;
use crate::tools::{ToolExecution, ToolRegistry};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::sync::{broadcast, Mutex};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentStep {
    pub step: u32,
    pub kind: String, // thought | tool_call | tool_result | summary
    pub text: String,
    pub tool_exec: Option<ToolExecution>,
    pub ts_utc: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentSession {
    pub session_id: String,
    pub role: String,
    pub model: String,
    pub provider: String,
    pub project_slug: String,
    pub prompt: String,
    pub started_at: String,
    pub finished_at: Option<String>,
    pub status: String, // running | completed | failed
    pub steps: Vec<AgentStep>,
    pub bounded_summary: String,
}

pub struct AgentRuntime {
    paths: RootPaths,
    tools: Arc<ToolRegistry>,
    events_tx: broadcast::Sender<ServerEvent>,
    history: Arc<Mutex<Vec<AgentSession>>>,
    http: reqwest::Client,
}

impl AgentRuntime {
    pub fn new(
        paths: RootPaths,
        tools: Arc<ToolRegistry>,
        events_tx: broadcast::Sender<ServerEvent>,
    ) -> Self {
        Self {
            paths,
            tools,
            events_tx,
            history: Arc::new(Mutex::new(Vec::new())),
            http: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(90))
                .build()
                .unwrap_or_default(),
        }
    }

    pub async fn get_history(&self) -> Vec<AgentSession> {
        let h = self.history.lock().await;
        h.iter().rev().take(20).cloned().collect()
    }

    /// Runs the Codex-style Agent Loop:
    /// Context Injection (state + lessons) -> Model Call -> Tool Call -> Permission Check -> Execution -> Feedback -> Bounded 5-line Summary.
    pub async fn run_mission(
        &self,
        role_id: &str,
        project_slug: &str,
        prompt: &str,
    ) -> Result<AgentSession, String> {
        let cfg = load_app_config(&self.paths)?;
        let role = cfg
            .roles
            .get(role_id)
            .ok_or_else(|| format!("Rôle inconnu : {role_id}"))?
            .clone();
        let provider = cfg
            .providers
            .get(&role.provider)
            .cloned()
            .ok_or_else(|| format!("Provider inconnu : {}", role.provider))?;

        let session_id = format!("agt_{}", &uuid::Uuid::new_v4().to_string()[..8]);
        let mut session = AgentSession {
            session_id: session_id.clone(),
            role: role_id.to_string(),
            model: role.model.clone(),
            provider: role.provider.clone(),
            project_slug: project_slug.to_string(),
            prompt: prompt.to_string(),
            started_at: now_utc(),
            finished_at: None,
            status: "running".to_string(),
            steps: Vec::new(),
            bounded_summary: String::new(),
        };

        let _ = self.events_tx.send(ServerEvent::new(
            "agent.started",
            json!({ "session_id": session_id, "role": role_id, "prompt": prompt }),
        ));

        // Inject bounded Level-2 lessons + Level-1 state summary (never raw logs!)
        let mem = MemoryStore::new(self.paths.clone());
        let active_lessons: Vec<String> = mem
            .load_lessons()
            .lessons
            .into_iter()
            .filter(|l| l.active)
            .take(8)
            .map(|l| format!("- {} ({})", l.rule, l.incident))
            .collect();

        let system_prompt = format!(
            "{}\n\n[LEÇONS ACTIVES]\n{}\n\n[RÈGLE DE SORTIE]\nRends un résumé borné de 5 lignes maximum.",
            role.system_prompt,
            active_lessons.join("\n")
        );

        let api_key = if !provider.api_key_env.is_empty() {
            std::env::var(&provider.api_key_env).ok().filter(|v| !v.is_empty())
        } else {
            None
        };

        if provider.kind == "openai_compatible" && api_key.is_some() {
            self.run_openai_loop(
                &mut session,
                &provider.endpoint,
                &api_key.unwrap(),
                &role.model,
                &system_prompt,
                role.readonly,
            )
            .await;
        } else {
            // Built-in deterministic local loop: plans real tool calls, triggers real permission prompts, returns bounded summary!
            self.run_local_harness_loop(&mut session, role.readonly)
                .await;
        }

        session.finished_at = Some(now_utc());
        if session.status == "running" {
            session.status = "completed".to_string();
        }

        // Record as `agent_claim` (NEVER counts as proof!)
        let pipeline = PipelineStore::new(self.paths.clone());
        let _ = pipeline.append_event(
            project_slug,
            "agent_claim",
            &format!(
                "Mission '{}' terminée ({} étapes) — ne compte pas comme preuve",
                role.label,
                session.steps.len()
            ),
            None,
            json!({ "session_id": session.session_id, "role": role_id }),
        );

        let _ = self.events_tx.send(ServerEvent::new(
            "agent.completed",
            serde_json::to_value(&session).unwrap_or(Value::Null),
        ));

        let mut h = self.history.lock().await;
        h.push(session.clone());
        Ok(session)
    }

    async fn run_local_harness_loop(&self, session: &mut AgentSession, role_readonly: bool) {
        let lower = session.prompt.to_lowercase();
        let mut plan_calls: Vec<(&str, Value, &str)> = Vec::new();

        // Always inspect project state first (0-token context read)
        plan_calls.push((
            "state_show",
            json!({ "project": session.project_slug }),
            "Lecture de l'état courant du projet (< 20 Ko)",
        ));

        if lower.contains("biblio") || lower.contains("cherche") || lower.contains("asset") || lower.contains("verse") {
            plan_calls.push((
                "library_search",
                json!({ "query": "" }),
                "Recherche préalable dans la bibliothèque réutilisable (avant de produire)",
            ));
        }

        if lower.contains("plan") || lower.contains("quartier") || lower.contains("geometr") || lower.contains("vérif") || lower.contains("verif") {
            plan_calls.push((
                "plan_check",
                json!({ "district_id": "district_plaza" }),
                "Contrôle géométrique et raisons du plan 4 couches",
            ));
        }

        if lower.contains("valid") || lower.contains("golden") || lower.contains("audit") {
            plan_calls.push((
                "validator_run",
                json!({ "golden_only": false }),
                "Exécution des validateurs protégés (MANIFEST + 20 cas Golden + Règles)",
            ));
        }

        if lower.contains("outbox") || lower.contains("lot") || lower.contains("poser") {
            plan_calls.push((
                "outbox_submit",
                json!({ "district_id": "district_plaza", "lot_id": "lot_auto" }),
                "Préparation d'un lot dans outbox/pending/ (après vérification plan)",
            ));
        }

        if lower.contains("shell") || lower.contains("git") {
            let cmd = if lower.contains("rm") {
                "rm -rf /tmp/test_blocked"
            } else {
                "git status -s"
            };
            plan_calls.push((
                "run_shell",
                json!({ "command": cmd }),
                "Exécution d'une commande shell soumise au moteur de permissions",
            ));
        }

        if lower.contains("ecri") || lower.contains("écri") || lower.contains("triche") || lower.contains("manifest") {
            let target = if lower.contains("triche") || lower.contains("manifest") {
                "validators/MANIFEST.json"
            } else {
                "workspace/projects/neo-kyoto-slice/deliverables/note_agent.md"
            };
            plan_calls.push((
                "write_file",
                json!({
                    "path": target,
                    "content": "# Note de mission générée par l'agent\n"
                }),
                "Tentative d'écriture fichier (contrôlée par permissions.toml)",
            ));
        }

        if plan_calls.len() == 1 {
            // Default helpful sweep: library + plan check + validator status
            plan_calls.push((
                "library_search",
                json!({ "query": "" }),
                "Recherche préalable dans la bibliothèque réutilisable",
            ));
            plan_calls.push((
                "plan_check",
                json!({ "district_id": "district_plaza" }),
                "Contrôle du plan actif (4 couches + raisons + budget mémoire)",
            ));
        }

        let mut summary_lines = Vec::new();
        for (idx, (tool_name, args, thought)) in plan_calls.into_iter().enumerate() {
            let step_num = (idx as u32) + 1;
            self.push_step(session, step_num, "tool_call", thought, None);

            let exec = self
                .tools
                .execute(
                    &session.role,
                    role_readonly,
                    &session.project_slug,
                    tool_name,
                    &args,
                )
                .await;

            let msg = if exec.ok {
                format!("Outil '{tool_name}' exécuté avec succès")
            } else {
                format!(
                    "Outil '{tool_name}' bloqué/échoué : {}",
                    exec.error.clone().unwrap_or_default()
                )
            };
            summary_lines.push(format!("- {msg}"));
            self.push_step(session, step_num, "tool_result", &msg, Some(exec));
        }

        summary_lines.truncate(5);
        session.bounded_summary = summary_lines.join("\n");
        let last_step = session.steps.len() as u32 + 1;
        let summary_copy = session.bounded_summary.clone();
        self.push_step(session, last_step, "summary", &summary_copy, None);
    }

    async fn run_openai_loop(
        &self,
        session: &mut AgentSession,
        endpoint: &str,
        api_key: &str,
        model: &str,
        system_prompt: &str,
        role_readonly: bool,
    ) {
        let tool_defs: Vec<Value> = self
            .tools
            .tool_definitions()
            .into_iter()
            .map(|t| json!({ "type": "function", "function": t }))
            .collect();

        let mut messages = vec![
            json!({ "role": "system", "content": system_prompt }),
            json!({ "role": "user", "content": session.prompt }),
        ];

        for turn in 1..=6u32 {
            let body = json!({
                "model": model,
                "messages": messages,
                "tools": tool_defs,
                "temperature": 0.2
            });
            let resp = self
                .http
                .post(endpoint)
                .bearer_auth(api_key)
                .json(&body)
                .send()
                .await;

            let Ok(r) = resp else {
                session.status = "failed".into();
                session.bounded_summary = "Erreur réseau vers le provider modèle".into();
                return;
            };
            let Ok(json_body) = r.json::<Value>().await else {
                session.status = "failed".into();
                session.bounded_summary = "Réponse JSON modèle illisible".into();
                return;
            };

            let Some(msg) = json_body.pointer("/choices/0/message").cloned() else {
                session.status = "failed".into();
                session.bounded_summary = format!("Erreur API modèle : {json_body}");
                return;
            };

            if let Some(calls) = msg.get("tool_calls").and_then(Value::as_array) {
                if !calls.is_empty() {
                    messages.push(msg.clone());
                    for tc in calls {
                        let tc_id = tc.get("id").and_then(Value::as_str).unwrap_or("call_1");
                        let fname = tc
                            .pointer("/function/name")
                            .and_then(Value::as_str)
                            .unwrap_or("");
                        let fargs_str = tc
                            .pointer("/function/arguments")
                            .and_then(Value::as_str)
                            .unwrap_or("{}");
                        let fargs: Value = serde_json::from_str(fargs_str).unwrap_or_else(|_| json!({}));

                        self.push_step(
                            session,
                            turn,
                            "tool_call",
                            &format!("Appel outil {fname}"),
                            None,
                        );
                        let exec = self
                            .tools
                            .execute(
                                &session.role,
                                role_readonly,
                                &session.project_slug,
                                fname,
                                &fargs,
                            )
                            .await;
                        let result_str = serde_json::to_string(&exec).unwrap_or_default();
                        self.push_step(
                            session,
                            turn,
                            "tool_result",
                            &format!("Retour {fname} (ok={})", exec.ok),
                            Some(exec),
                        );
                        messages.push(json!({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": result_str
                        }));
                    }
                    continue;
                }
            }

            let content = msg
                .get("content")
                .and_then(Value::as_str)
                .unwrap_or("Mission terminée.")
                .to_string();
            let bounded: String = content.lines().take(5).collect::<Vec<_>>().join("\n");
            session.bounded_summary = bounded.clone();
            self.push_step(session, turn, "summary", &bounded, None);
            return;
        }
    }

    fn push_step(
        &self,
        session: &mut AgentSession,
        step: u32,
        kind: &str,
        text: &str,
        tool_exec: Option<ToolExecution>,
    ) {
        let s = AgentStep {
            step,
            kind: kind.to_string(),
            text: text.to_string(),
            tool_exec,
            ts_utc: now_utc(),
        };
        session.steps.push(s.clone());
        let _ = self.events_tx.send(ServerEvent::new(
            "agent.step",
            json!({ "session_id": session.session_id, "step": s }),
        ));
    }
}
