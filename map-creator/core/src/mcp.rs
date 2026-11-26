use crate::config::{load_circuit_breakers, load_mcp_config, now_utc, McpServerEntry, RootPaths};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::sync::Arc;
use tokio::sync::Mutex;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct McpCallResult {
    pub rc: i32,
    pub server: String,
    pub tool: String,
    pub write: bool,
    pub mode: String,
    pub duration_ms: u128,
    pub payload: Value,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimActor {
    pub name: String,
    pub actor_path: String,
    pub bounds: Value,
}

pub struct McpHost {
    paths: RootPaths,
    http: reqwest::Client,
    sim_scenes: Arc<Mutex<BTreeMap<String, Vec<SimActor>>>>,
    sessions: Arc<Mutex<BTreeMap<String, String>>>,
}

impl McpHost {
    pub fn new(paths: RootPaths) -> Self {
        Self {
            paths,
            http: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(120))
                .build()
                .unwrap_or_default(),
            sim_scenes: Arc::new(Mutex::new(BTreeMap::new())),
            sessions: Arc::new(Mutex::new(BTreeMap::new())),
        }
    }

    pub fn list_servers(&self) -> Result<BTreeMap<String, McpServerEntry>, String> {
        Ok(load_mcp_config(&self.paths)?.servers)
    }

    pub async fn ping(&self, server_name: &str) -> Result<Value, String> {
        let cfg = load_mcp_config(&self.paths)?;
        let srv = cfg
            .servers
            .get(server_name)
            .ok_or_else(|| format!("Serveur MCP inconnu : {server_name}"))?;
        if !srv.enabled {
            return Ok(json!({ "server": server_name, "online": false, "mode": srv.mode, "reason": "désactivé" }));
        }
        if srv.mode == "simulator" {
            return Ok(json!({
                "server": server_name,
                "online": true,
                "mode": "simulator",
                "endpoint": srv.endpoint,
                "note": "Simulateur hors ligne actif (fixtures compat/)"
            }));
        }
        let body = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": { "name": "map-creator-core", "version": "0.1.0" }
            }
        });
        match self
            .http
            .post(&srv.endpoint)
            .header("Accept", "application/json, text/event-stream")
            .json(&body)
            .send()
            .await
        {
            Ok(resp) => Ok(json!({
                "server": server_name,
                "online": resp.status().is_success(),
                "http_status": resp.status().as_u16(),
                "mode": "live",
                "endpoint": srv.endpoint
            })),
            Err(e) => Ok(json!({
                "server": server_name,
                "online": false,
                "mode": "live",
                "endpoint": srv.endpoint,
                "error": e.to_string()
            })),
        }
    }

    pub async fn call(
        &self,
        project_slug: &str,
        server_name: &str,
        tool: &str,
        arguments: Value,
        write: bool,
        mode_override: Option<&str>,
    ) -> McpCallResult {
        let t0 = std::time::Instant::now();
        let policy_err = self.check_policy(server_name, tool, write);
        if let Err(err_msg) = policy_err {
            let res = McpCallResult {
                rc: 4,
                server: server_name.to_string(),
                tool: tool.to_string(),
                write,
                mode: "blocked".to_string(),
                duration_ms: t0.elapsed().as_millis(),
                payload: Value::Null,
                error: Some(err_msg),
            };
            self.write_trace(project_slug, &res, &arguments);
            return res;
        }

        let cfg = match load_mcp_config(&self.paths) {
            Ok(c) => c,
            Err(e) => {
                return McpCallResult {
                    rc: 4,
                    server: server_name.to_string(),
                    tool: tool.to_string(),
                    write,
                    mode: "error".into(),
                    duration_ms: t0.elapsed().as_millis(),
                    payload: Value::Null,
                    error: Some(e),
                };
            }
        };
        let srv = cfg.servers.get(server_name).unwrap().clone();
        let eff_mode = mode_override.unwrap_or(&srv.mode);

        let res = if eff_mode == "simulator" {
            self.call_simulator(project_slug, server_name, tool, &arguments, write, t0)
                .await
        } else {
            self.call_live_http(&srv, server_name, tool, &arguments, write, t0)
                .await
        };

        self.write_trace(project_slug, &res, &arguments);
        res
    }

    fn check_policy(&self, server_name: &str, tool: &str, write: bool) -> Result<(), String> {
        let cb = load_circuit_breakers(&self.paths)
            .map_err(|e| format!("CIRCUIT_BREAKER illisible (fail-closed): {e}"))?;
        if cb.writes_halted && write {
            return Err(format!(
                "CIRCUIT_BREAKER: toutes les écritures MCP sont coupées ({})",
                cb.reason.unwrap_or_else(|| "urgence".into())
            ));
        }
        if cb.blocked_tools.iter().any(|b| b == tool) {
            return Err(format!("CIRCUIT_BREAKER: outil '{tool}' coupé en urgence"));
        }

        let cfg = load_mcp_config(&self.paths)?;
        let srv = cfg
            .servers
            .get(server_name)
            .ok_or_else(|| format!("UNKNOWN_MCP_SERVER: '{server_name}'"))?;
        if !srv.enabled {
            return Err(format!("MCP_DISABLED: serveur '{server_name}' désactivé"));
        }
        let short_name = tool.split('.').next_back().unwrap_or(tool);
        if srv
            .forbidden_tools
            .iter()
            .any(|f| f == tool || f == short_name)
        {
            return Err(format!("FORBIDDEN_TOOL: '{tool}' interdit absolu"));
        }

        if write {
            if !srv.allowed_write_tools.iter().any(|a| a == tool) {
                return Err(format!(
                    "UNKNOWN_TOOL_BLOCKED: écriture '{tool}' non prouvée sur '{server_name}'"
                ));
            }
        } else if !srv.allowed_read_tools.iter().any(|a| a == tool)
            && !srv.allowed_write_tools.iter().any(|a| a == tool)
        {
            return Err(format!(
                "UNKNOWN_TOOL_BLOCKED: lecture '{tool}' hors allowlist sur '{server_name}'"
            ));
        }

        Ok(())
    }

    async fn call_simulator(
        &self,
        project_slug: &str,
        server_name: &str,
        tool: &str,
        args: &Value,
        write: bool,
        t0: std::time::Instant,
    ) -> McpCallResult {
        let mut scenes = self.sim_scenes.lock().await;
        let scene = scenes
            .entry(project_slug.to_string())
            .or_insert_with(|| {
                vec![
                    SimActor {
                        name: "WorldSettings".into(),
                        actor_path: format!("/Game/{project_slug}/Main.Main:PersistentLevel.WorldSettings"),
                        bounds: json!({"min": {"x": -10000.0, "y": -10000.0, "z": -500.0}, "max": {"x": 10000.0, "y": 10000.0, "z": 5000.0}}),
                    },
                    SimActor {
                        name: "LevelBounds_0".into(),
                        actor_path: format!("/Game/{project_slug}/Main.Main:PersistentLevel.LevelBounds_0"),
                        bounds: json!({"min": {"x": -12288.0, "y": -12288.0, "z": -512.0}, "max": {"x": 12288.0, "y": 12288.0, "z": 6144.0}}),
                    },
                ]
            });

        let payload = match tool {
            "SceneTools.get_current_level" => {
                json!({ "returnValue": format!("/Game/{project_slug}/Main") })
            }
            "SceneTools.find_actors" => {
                let list: Vec<Value> = scene
                    .iter()
                    .map(|a| {
                        json!({
                            "name": a.name,
                            "actorPath": a.actor_path,
                            "bounds": a.bounds
                        })
                    })
                    .collect();
                json!({ "returnValue": list })
            }
            "PrimitiveTools.add_cube"
            | "SceneTools.add_to_scene_from_class"
            | "SceneTools.add_to_scene_from_asset"
            | "DeviceToolset.PlaceDevice" => {
                let id = args
                    .get("label")
                    .or_else(|| args.get("plan_item_id"))
                    .and_then(Value::as_str)
                    .unwrap_or("MC_Actor");
                let bounds = args.get("expected_bounds").cloned().unwrap_or_else(|| {
                    json!({
                        "min": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "max": {"x": 512.0, "y": 512.0, "z": 384.0}
                    })
                });
                let actor_path = format!("/Game/{project_slug}/Main.Main:PersistentLevel.MC_{id}");
                scene.retain(|a| a.actor_path != actor_path);
                scene.push(SimActor {
                    name: format!("MC_{id}"),
                    actor_path: actor_path.clone(),
                    bounds: bounds.clone(),
                });
                json!({
                    "returnValue": {
                        "actorPath": actor_path,
                        "bounds": bounds
                    }
                })
            }
            "AssetTools.save_assets" => json!({ "returnValue": true }),
            "AssetTools.is_dirty" => json!({ "returnValue": false }),
            "ActorTools.get_actor_bounds" => {
                let ref_path = args
                    .get("actor")
                    .and_then(|a| a.get("refPath"))
                    .and_then(Value::as_str)
                    .unwrap_or("");
                let found = scene
                    .iter()
                    .find(|a| a.actor_path == ref_path)
                    .map(|a| a.bounds.clone())
                    .unwrap_or_else(|| {
                        json!({"min": {"x": -12288.0, "y": -12288.0, "z": -512.0}, "max": {"x": 12288.0, "y": 12288.0, "z": 6144.0}})
                    });
                json!({ "returnValue": found })
            }
            "VerseToolset.BuildAll" => {
                json!({ "returnValue": { "compiled": true, "diagnostics": [] } })
            }
            _ => json!({ "returnValue": { "simulated": true, "tool": tool } }),
        };

        McpCallResult {
            rc: 0,
            server: server_name.to_string(),
            tool: tool.to_string(),
            write,
            mode: "simulator".to_string(),
            duration_ms: t0.elapsed().as_millis(),
            payload,
            error: None,
        }
    }

    async fn call_live_http(
        &self,
        srv: &McpServerEntry,
        server_name: &str,
        tool: &str,
        args: &Value,
        write: bool,
        t0: std::time::Instant,
    ) -> McpCallResult {
        let sid = self.ensure_http_session(server_name, srv).await;
        let Some(session_id) = sid else {
            return McpCallResult {
                rc: 2,
                server: server_name.to_string(),
                tool: tool.to_string(),
                write,
                mode: "live".to_string(),
                duration_ms: t0.elapsed().as_millis(),
                payload: Value::Null,
                error: Some("OFFLINE: serveur MCP injoignable, rien exécuté".into()),
            };
        };

        let mut parts = tool.splitn(2, '.');
        let toolset = parts.next().unwrap_or("");
        let tool_name = parts.next().unwrap_or(tool);

        let body = json!({
            "jsonrpc": "2.0",
            "id": uuid::Uuid::new_v4().to_string(),
            "method": "tools/call",
            "params": {
                "name": "call_tool",
                "arguments": {
                    "toolset_name": toolset,
                    "tool_name": tool_name,
                    "arguments": args
                }
            }
        });

        match self
            .http
            .post(&srv.endpoint)
            .header("Accept", "application/json, text/event-stream")
            .header("Mcp-Session-Id", session_id)
            .json(&body)
            .send()
            .await
        {
            Ok(resp) => {
                let status = resp.status();
                let text = resp.text().await.unwrap_or_default();
                let parsed: Value = parse_mcp_body(&text);
                let is_err = !status.is_success()
                    || parsed.get("error").is_some()
                    || parsed
                        .get("result")
                        .and_then(|r| r.get("isError"))
                        .and_then(Value::as_bool)
                        .unwrap_or(false);
                McpCallResult {
                    rc: if is_err { 1 } else { 0 },
                    server: server_name.to_string(),
                    tool: tool.to_string(),
                    write,
                    mode: "live".to_string(),
                    duration_ms: t0.elapsed().as_millis(),
                    payload: parsed.get("result").cloned().unwrap_or(parsed),
                    error: if is_err {
                        Some(format!("Erreur MCP HTTP {}", status.as_u16()))
                    } else {
                        None
                    },
                }
            }
            Err(e) => McpCallResult {
                rc: if e.is_timeout() { 3 } else { 2 },
                server: server_name.to_string(),
                tool: tool.to_string(),
                write,
                mode: "live".to_string(),
                duration_ms: t0.elapsed().as_millis(),
                payload: Value::Null,
                error: Some(e.to_string()),
            },
        }
    }

    async fn ensure_http_session(&self, name: &str, srv: &McpServerEntry) -> Option<String> {
        {
            let map = self.sessions.lock().await;
            if let Some(s) = map.get(name) {
                return Some(s.clone());
            }
        }
        let init = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": { "name": "map-creator-core", "version": "0.1.0" }
            }
        });
        let resp = self
            .http
            .post(&srv.endpoint)
            .header("Accept", "application/json, text/event-stream")
            .json(&init)
            .send()
            .await
            .ok()?;
        let sid = resp
            .headers()
            .get("mcp-session-id")
            .and_then(|v| v.to_str().ok())
            .map(String::from)?;
        let _ = self
            .http
            .post(&srv.endpoint)
            .header("Mcp-Session-Id", &sid)
            .json(&json!({"jsonrpc": "2.0", "method": "notifications/initialized"}))
            .send()
            .await;
        let mut map = self.sessions.lock().await;
        map.insert(name.to_string(), sid.clone());
        Some(sid)
    }

    fn write_trace(&self, project_slug: &str, res: &McpCallResult, args: &Value) {
        let trace_path = self.paths.project_dir(project_slug).join("trace.jsonl");
        if let Some(p) = trace_path.parent() {
            let _ = fs::create_dir_all(p);
        }
        let line = json!({
            "ts_utc": now_utc(),
            "server": res.server,
            "tool": res.tool,
            "write": res.write,
            "mode": res.mode,
            "rc": res.rc,
            "duration_ms": res.duration_ms,
            "error": res.error,
            "args_keys": args.as_object().map(|m| m.keys().cloned().collect::<Vec<_>>()).unwrap_or_default()
        });
        if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(trace_path) {
            let _ = writeln!(f, "{}", line);
        }
    }
}

fn parse_mcp_body(raw: &str) -> Value {
    if let Ok(v) = serde_json::from_str::<Value>(raw) {
        return v;
    }
    for line in raw.lines().rev() {
        if let Some(rest) = line.strip_prefix("data:") {
            if let Ok(v) = serde_json::from_str::<Value>(rest.trim()) {
                return v;
            }
        }
    }
    json!({ "raw": raw })
}
