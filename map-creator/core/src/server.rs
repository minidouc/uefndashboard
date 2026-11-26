use crate::agent::AgentRuntime;
use crate::compat::CompatManager;
use crate::config::{
    load_app_config, load_circuit_breakers, load_mcp_config, load_permissions_config,
    save_app_config, save_circuit_breakers, save_mcp_config, save_permissions_config, AppConfig,
    CircuitBreakersConfig, McpServersConfig, PermissionsConfig, RootPaths,
};
use crate::mcp::McpHost;
use crate::memory::{LibraryEntry, MemoryStore};
use crate::outbox::OutboxEngine;
use crate::permissions::PermissionEngine;
use crate::pipeline::{PipelineStore, NON_SACRIFIABLES, PHASES, SACRIFIABLES};
use crate::planner::{PlanItem, PlannerEngine};
use crate::protocol::{RpcRequest, RpcResponse, ServerEvent};
use crate::tools::ToolRegistry;
use crate::validators::ValidatorEngine;
use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::State;
use axum::response::IntoResponse;
use axum::routing::{get, post};
use axum::{Json, Router};
use futures_util::{SinkExt, StreamExt};
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::sync::broadcast;
use tower_http::cors::CorsLayer;
use tower_http::services::{ServeDir, ServeFile};

pub struct AppState {
    pub paths: RootPaths,
    pub events_tx: broadcast::Sender<ServerEvent>,
    pub perms: Arc<PermissionEngine>,
    pub mcp: Arc<McpHost>,
    pub agent: Arc<AgentRuntime>,
}

impl AppState {
    pub fn new(paths: RootPaths) -> Arc<Self> {
        let (events_tx, _) = broadcast::channel(256);
        let perms = Arc::new(PermissionEngine::new(paths.clone(), events_tx.clone()));
        let mcp = Arc::new(McpHost::new(paths.clone()));
        let tools = Arc::new(ToolRegistry::new(paths.clone(), perms.clone(), mcp.clone()));
        let agent = Arc::new(AgentRuntime::new(paths.clone(), tools, events_tx.clone()));
        Arc::new(Self {
            paths,
            events_tx,
            perms,
            mcp,
            agent,
        })
    }

    pub fn active_project(&self) -> String {
        load_app_config(&self.paths)
            .map(|c| c.server.active_project)
            .unwrap_or_else(|_| "neo-kyoto-slice".to_string())
    }
}

pub fn build_router(state: Arc<AppState>) -> Router {
    let ui_dist = state.paths.ui_dist_dir();
    let index_html = ui_dist.join("index.html");

    let api = Router::new()
        .route("/api/health", get(http_health))
        .route("/rpc", post(http_rpc))
        .route("/ws", get(ws_handler))
        .with_state(state)
        .layer(CorsLayer::permissive());

    if ui_dist.exists() && index_html.exists() {
        api.fallback_service(
            ServeDir::new(&ui_dist).not_found_service(ServeFile::new(&index_html)),
        )
    } else {
        api
    }
}

async fn http_health(State(st): State<Arc<AppState>>) -> Json<Value> {
    let cfg = load_app_config(&st.paths).ok();
    let val = ValidatorEngine::new(st.paths.clone());
    let (integrity, _) = val.verify_manifest();
    Json(json!({
        "status": "ok",
        "engine": "map-creator-core",
        "version": "0.1.0",
        "active_project": st.active_project(),
        "uefn_version": cfg.as_ref().map(|c| c.server.uefn_version.as_str()).unwrap_or("39.10"),
        "mcp_mode": cfg.as_ref().map(|c| c.server.mcp_mode.as_str()).unwrap_or("simulator"),
        "manifest_integrity": integrity
    }))
}

async fn http_rpc(
    State(st): State<Arc<AppState>>,
    Json(req): Json<RpcRequest>,
) -> Json<RpcResponse> {
    Json(dispatch_rpc(st, req).await)
}

async fn ws_handler(ws: WebSocketUpgrade, State(st): State<Arc<AppState>>) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_ws(socket, st))
}

async fn handle_ws(socket: WebSocket, st: Arc<AppState>) {
    let (mut sink, mut stream) = socket.split();
    let mut rx = st.events_tx.subscribe();

    let (tx_out, mut rx_out) = tokio::sync::mpsc::channel::<String>(64);

    let send_task = tokio::spawn(async move {
        while let Some(msg) = rx_out.recv().await {
            if sink.send(Message::Text(msg)).await.is_err() {
                break;
            }
        }
    });

    let tx_events = tx_out.clone();
    let event_task = tokio::spawn(async move {
        while let Ok(evt) = rx.recv().await {
            let txt = serde_json::to_string(&evt.to_jsonrpc_notification()).unwrap_or_default();
            if tx_events.send(txt).await.is_err() {
                break;
            }
        }
    });

    while let Some(Ok(msg)) = stream.next().await {
        if let Message::Text(text) = msg {
            if let Ok(req) = serde_json::from_str::<RpcRequest>(&text) {
                let st_clone = st.clone();
                let tx_resp = tx_out.clone();
                tokio::spawn(async move {
                    let resp = dispatch_rpc(st_clone, req).await;
                    let _ = tx_resp
                        .send(serde_json::to_string(&resp).unwrap_or_default())
                        .await;
                });
            }
        }
    }

    event_task.abort();
    send_task.abort();
}

pub async fn dispatch_rpc(st: Arc<AppState>, req: RpcRequest) -> RpcResponse {
    let id = req.id.clone();
    match dispatch_rpc_inner(st, &req).await {
        Ok(val) => RpcResponse::ok(id, val),
        Err(msg) => RpcResponse::err(id, -32000, msg),
    }
}

async fn dispatch_rpc_inner(st: Arc<AppState>, req: &RpcRequest) -> Result<Value, String> {
    let p = &req.params;
    let project = p
        .get("project")
        .and_then(Value::as_str)
        .map(String::from)
        .unwrap_or_else(|| st.active_project());

    match req.method.as_str() {
        // 1. System & Config
        "system.health" => {
            let cfg = load_app_config(&st.paths)?;
            let val = ValidatorEngine::new(st.paths.clone());
            let (integrity, mismatches) = val.verify_manifest();
            let pipeline = PipelineStore::new(st.paths.clone());
            let state_bytes = pipeline.load_state(&project).map(|(_, b)| b).unwrap_or(0);
            let pending_approvals = st.perms.list_pending().await.len();
            Ok(json!({
                "status": "ok",
                "active_project": cfg.server.active_project,
                "uefn_version": cfg.server.uefn_version,
                "mcp_mode": cfg.server.mcp_mode,
                "manifest_integrity": integrity,
                "manifest_mismatches": mismatches,
                "state_bytes": state_bytes,
                "max_state_bytes": 20000,
                "pending_approvals": pending_approvals
            }))
        }
        "config.get" => Ok(json!({
            "app": load_app_config(&st.paths)?,
            "permissions": load_permissions_config(&st.paths)?,
            "mcp": load_mcp_config(&st.paths)?,
            "circuit_breakers": load_circuit_breakers(&st.paths)?
        })),
        "config.update_app" => {
            let cfg: AppConfig = serde_json::from_value(p.clone())
                .map_err(|e| format!("AppConfig invalide: {e}"))?;
            save_app_config(&st.paths, &cfg)?;
            let _ = st
                .events_tx
                .send(ServerEvent::new("config.updated", json!({ "target": "app" })));
            Ok(json!({ "saved": true, "app": cfg }))
        }
        "config.update_permissions" => {
            let cfg: PermissionsConfig = serde_json::from_value(p.clone())
                .map_err(|e| format!("PermissionsConfig invalide: {e}"))?;
            save_permissions_config(&st.paths, &cfg)?;
            Ok(json!({ "saved": true, "permissions": cfg }))
        }
        "config.update_mcp" => {
            let cfg: McpServersConfig = serde_json::from_value(p.clone())
                .map_err(|e| format!("McpServersConfig invalide: {e}"))?;
            save_mcp_config(&st.paths, &cfg)?;
            Ok(json!({ "saved": true, "mcp": cfg }))
        }
        "config.update_circuit_breakers" => {
            let cfg: CircuitBreakersConfig = serde_json::from_value(p.clone())
                .map_err(|e| format!("CircuitBreakersConfig invalide: {e}"))?;
            save_circuit_breakers(&st.paths, &cfg)?;
            let _ = st.events_tx.send(ServerEvent::new(
                "circuit_breakers.updated",
                serde_json::to_value(&cfg).unwrap_or(Value::Null),
            ));
            Ok(json!({ "saved": true, "circuit_breakers": cfg }))
        }

        // 2. Projects & Pipeline
        "project.list" => {
            let ps = PipelineStore::new(st.paths.clone());
            Ok(json!({ "projects": ps.list_projects(), "active": st.active_project() }))
        }
        "project.create" => {
            let slug = p.get("slug").and_then(Value::as_str).ok_or("slug requis")?;
            let title = p.get("title").and_then(Value::as_str).unwrap_or(slug);
            let mode = p.get("mode").and_then(Value::as_str).unwrap_or("production");
            let ps = PipelineStore::new(st.paths.clone());
            let created = ps.create_project(slug, title, mode)?;
            let mut app = load_app_config(&st.paths)?;
            app.server.active_project = slug.to_string();
            save_app_config(&st.paths, &app)?;
            Ok(serde_json::to_value(created).unwrap())
        }
        "project.select" => {
            let slug = p.get("slug").and_then(Value::as_str).ok_or("slug requis")?;
            let ps = PipelineStore::new(st.paths.clone());
            let _ = ps.load_state(slug)?;
            let mut app = load_app_config(&st.paths)?;
            app.server.active_project = slug.to_string();
            save_app_config(&st.paths, &app)?;
            Ok(json!({ "active_project": slug }))
        }
        "pipeline.state" => {
            let ps = PipelineStore::new(st.paths.clone());
            let (state, bytes) = ps.load_state(&project)?;
            Ok(json!({
                "state": state,
                "state_bytes": bytes,
                "max_state_bytes": 20000,
                "cap_iterations": crate::pipeline::CAP_ITERATIONS,
                "phases": PHASES,
                "sacrifiables": SACRIFIABLES,
                "non_sacrifiables": NON_SACRIFIABLES
            }))
        }
        "pipeline.advance" => {
            let target = p
                .get("target_phase")
                .and_then(Value::as_str)
                .ok_or("target_phase requis")?;
            let ps = PipelineStore::new(st.paths.clone());
            let next = ps.advance_phase(&project, target)?;
            let _ = st.events_tx.send(ServerEvent::new(
                "state.changed",
                json!({ "project": project, "phase": next.phase }),
            ));
            Ok(serde_json::to_value(next).unwrap())
        }
        "pipeline.approve_gate" => {
            let gate = p.get("gate").and_then(Value::as_str).ok_or("gate requis")?;
            let citation = p
                .get("citation")
                .and_then(Value::as_str)
                .ok_or("citation requise")?;
            let scope = p.get("scope").and_then(Value::as_str).map(String::from);
            let ps = PipelineStore::new(st.paths.clone());
            let updated = ps.approve_gate(&project, gate, citation, scope)?;
            let _ = st.events_tx.send(ServerEvent::new(
                "gate.approved",
                json!({ "project": project, "gate": gate }),
            ));
            Ok(serde_json::to_value(updated).unwrap())
        }
        "pipeline.set_mode" => {
            let mode = p.get("mode").and_then(Value::as_str).ok_or("mode requis")?;
            let ps = PipelineStore::new(st.paths.clone());
            Ok(serde_json::to_value(ps.set_mode(&project, mode)?).unwrap())
        }
        "pipeline.lock_deliverable" => {
            let path = p.get("path").and_then(Value::as_str).ok_or("path requis")?;
            let citation = p
                .get("citation")
                .and_then(Value::as_str)
                .ok_or("citation requise")?;
            let ps = PipelineStore::new(st.paths.clone());
            Ok(serde_json::to_value(ps.lock_deliverable(&project, path, citation)?).unwrap())
        }
        "pipeline.change_request" => {
            let target = p
                .get("target")
                .and_then(Value::as_str)
                .ok_or("target requis")?;
            let reason = p
                .get("reason")
                .and_then(Value::as_str)
                .ok_or("reason requis")?;
            let citation = p.get("citation").and_then(Value::as_str);
            let ps = PipelineStore::new(st.paths.clone());
            Ok(serde_json::to_value(ps.request_change(&project, target, reason, citation)?).unwrap())
        }
        "pipeline.derogation" => {
            let sacrificed: Vec<String> = p
                .get("sacrificed")
                .and_then(Value::as_array)
                .map(|a| {
                    a.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect()
                })
                .unwrap_or_default();
            let citation = p
                .get("citation")
                .and_then(Value::as_str)
                .ok_or("citation requise")?;
            let ps = PipelineStore::new(st.paths.clone());
            Ok(serde_json::to_value(ps.record_derogation(&project, sacrificed, citation)?).unwrap())
        }
        "pipeline.events" => {
            let limit = p.get("limit").and_then(Value::as_u64).unwrap_or(50) as usize;
            let prov = p.get("provenance").and_then(Value::as_str);
            let ps = PipelineStore::new(st.paths.clone());
            Ok(json!({ "events": ps.tail_events(&project, limit, prov) }))
        }

        // 3. Plans 2D (4 layers + Section)
        "plan.list" => {
            let pl = PlannerEngine::new(st.paths.clone());
            Ok(json!({ "plans": pl.list_plans(&project) }))
        }
        "plan.get" => {
            let did = p
                .get("district_id")
                .and_then(Value::as_str)
                .ok_or("district_id requis")?;
            let pl = PlannerEngine::new(st.paths.clone());
            let plan = pl.load_plan(&project, did)?;
            let check = pl.check_plan(&plan);
            let (svg_2d, svg_section) = pl.render_svg(&plan, &[]);
            Ok(json!({ "plan": plan, "check": check, "svg_2d": svg_2d, "svg_section": svg_section }))
        }
        "plan.check" => {
            let did = p
                .get("district_id")
                .and_then(Value::as_str)
                .ok_or("district_id requis")?;
            let pl = PlannerEngine::new(st.paths.clone());
            let plan = pl.load_plan(&project, did)?;
            Ok(serde_json::to_value(pl.check_plan(&plan)).unwrap())
        }
        "plan.render_svg" => {
            let did = p
                .get("district_id")
                .and_then(Value::as_str)
                .ok_or("district_id requis")?;
            let layers: Vec<String> = p
                .get("layers")
                .and_then(Value::as_array)
                .map(|a| {
                    a.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect()
                })
                .unwrap_or_default();
            let pl = PlannerEngine::new(st.paths.clone());
            let plan = pl.load_plan(&project, did)?;
            let (svg_2d, svg_section) = pl.render_svg(&plan, &layers);
            Ok(json!({ "svg_2d": svg_2d, "svg_section": svg_section }))
        }
        "plan.upsert_item" => {
            let did = p
                .get("district_id")
                .and_then(Value::as_str)
                .ok_or("district_id requis")?;
            let layer = p.get("layer").and_then(Value::as_str).ok_or("layer requis")?;
            let item: PlanItem = serde_json::from_value(
                p.get("item").cloned().ok_or("item requis")?,
            )
            .map_err(|e| format!("PlanItem invalide: {e}"))?;
            let pl = PlannerEngine::new(st.paths.clone());
            let plan = pl.upsert_item(&project, did, layer, item)?;
            let check = pl.check_plan(&plan);
            Ok(json!({ "plan": plan, "check": check }))
        }

        // 4. Outbox
        "outbox.list" => {
            let ob = OutboxEngine::new(st.paths.clone(), st.mcp.clone());
            Ok(json!({ "jobs": ob.list_jobs(&project) }))
        }
        "outbox.submit_from_plan" => {
            let did = p
                .get("district_id")
                .and_then(Value::as_str)
                .unwrap_or("district_plaza");
            let lot_id = p.get("lot_id").and_then(Value::as_str).unwrap_or("lot_02");
            let phase = p
                .get("phase")
                .and_then(Value::as_str)
                .unwrap_or("3_GRAYBOX");
            let layers: Vec<String> = p
                .get("layers")
                .and_then(Value::as_array)
                .map(|a| {
                    a.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect()
                })
                .unwrap_or_else(|| vec!["a_scene".into(), "b_fonds".into()]);
            let ob = OutboxEngine::new(st.paths.clone(), st.mcp.clone());
            let job = ob.submit_from_plan(&project, did, &layers, lot_id, phase)?;
            let _ = st.events_tx.send(ServerEvent::new(
                "outbox.updated",
                json!({ "job_id": job.job_id, "status": job.status }),
            ));
            Ok(serde_json::to_value(job).unwrap())
        }
        "outbox.dispatch" => {
            let job_id = p
                .get("job_id")
                .and_then(Value::as_str)
                .ok_or("job_id requis")?;
            let mode = p.get("mode").and_then(Value::as_str);
            let ob = OutboxEngine::new(st.paths.clone(), st.mcp.clone());
            let rep = ob.dispatch(&project, job_id, mode).await?;
            let _ = st.events_tx.send(ServerEvent::new(
                "outbox.updated",
                json!({ "job_id": rep.job.job_id, "status": rep.job.status }),
            ));
            Ok(serde_json::to_value(rep).unwrap())
        }
        "outbox.get_raw_response" => {
            let path = p.get("path").and_then(Value::as_str).ok_or("path requis")?;
            let ob = OutboxEngine::new(st.paths.clone(), st.mcp.clone());
            ob.read_raw_response(&project, path)
        }

        // 5. 3-Level Memory
        "memory.lessons_list" => {
            let mem = MemoryStore::new(st.paths.clone());
            Ok(serde_json::to_value(mem.load_lessons()).unwrap())
        }
        "memory.lessons_add" => {
            let rule = p.get("rule").and_then(Value::as_str).ok_or("rule requis")?;
            let incident = p
                .get("incident")
                .and_then(Value::as_str)
                .ok_or("incident requis")?;
            let prov = p
                .get("provenance")
                .and_then(Value::as_str)
                .unwrap_or("human");
            let mem = MemoryStore::new(st.paths.clone());
            Ok(serde_json::to_value(mem.add_lesson(rule, incident, prov)?).unwrap())
        }
        "memory.library_search" => {
            let q = p.get("query").and_then(Value::as_str).unwrap_or("");
            let cat = p.get("category").and_then(Value::as_str);
            let only_v = p
                .get("only_verified")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            let mem = MemoryStore::new(st.paths.clone());
            let hits = mem.search_library(q, cat, only_v);
            Ok(json!({ "count": hits.len(), "entries": hits }))
        }
        "memory.library_add" => {
            let entry: LibraryEntry = serde_json::from_value(p.clone())
                .map_err(|e| format!("LibraryEntry invalide: {e}"))?;
            let mem = MemoryStore::new(st.paths.clone());
            Ok(serde_json::to_value(mem.add_library_entry(entry)?).unwrap())
        }
        "memory.library_check_staleness" => {
            let ver = p
                .get("uefn_version")
                .and_then(Value::as_str)
                .map(String::from)
                .unwrap_or_else(|| {
                    load_app_config(&st.paths)
                        .map(|c| c.server.uefn_version)
                        .unwrap_or_else(|_| "39.10".into())
                });
            let mem = MemoryStore::new(st.paths.clone());
            let flagged = mem.flag_stale_for_uefn_version(&ver)?;
            Ok(json!({ "uefn_version": ver, "flagged_suspect": flagged }))
        }

        // 6. Protected Validators & Compat
        "validators.run" => {
            let golden_only = p
                .get("golden_only")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            let val = ValidatorEngine::new(st.paths.clone());
            let rep = val.run_all(&project, golden_only);
            let _ = st.events_tx.send(ServerEvent::new(
                "validation.completed",
                json!({ "project": project, "verdict": rep.verdict, "golden_passed": rep.golden_set_passed }),
            ));
            Ok(serde_json::to_value(rep).unwrap())
        }
        "validators.status" => {
            let val = ValidatorEngine::new(st.paths.clone());
            let (integrity, mismatches) = val.verify_manifest();
            let latest = val.load_latest_report(&project);
            Ok(json!({
                "manifest_integrity": integrity,
                "manifest_mismatches": mismatches,
                "latest_report": latest
            }))
        }
        "compat.status" => {
            let cm = CompatManager::new(st.paths.clone());
            Ok(serde_json::to_value(cm.load_summary()).unwrap())
        }
        "compat.ingest_fixture" => {
            let tool = p.get("tool").and_then(Value::as_str).ok_or("tool requis")?;
            let status = p
                .get("status")
                .and_then(Value::as_str)
                .ok_or("status requis")?;
            let uefn_ver = p
                .get("uefn_version")
                .and_then(Value::as_str)
                .unwrap_or("39.10");
            let notes = p.get("notes").and_then(Value::as_str).unwrap_or("");
            let payload = p.get("payload").cloned().unwrap_or(Value::Null);
            let cm = CompatManager::new(st.paths.clone());
            Ok(serde_json::to_value(cm.ingest_fixture(tool, status, uefn_ver, notes, payload)?).unwrap())
        }

        // 7. Agent Loop, Permissions & MCP Extensions
        "agent.run" => {
            let role = p
                .get("role")
                .and_then(Value::as_str)
                .unwrap_or("orchestrateur");
            let prompt = p
                .get("prompt")
                .and_then(Value::as_str)
                .ok_or("prompt requis")?;
            let session = st.agent.run_mission(role, &project, prompt).await?;
            Ok(serde_json::to_value(session).unwrap())
        }
        "agent.history" => Ok(json!({ "sessions": st.agent.get_history().await })),
        "permissions.pending" => Ok(json!({ "pending": st.perms.list_pending().await })),
        "permissions.resolve" => {
            let aid = p
                .get("approval_id")
                .and_then(Value::as_str)
                .ok_or("approval_id requis")?;
            let approved = p
                .get("approved")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            let ok = st.perms.resolve(aid, approved).await?;
            Ok(json!({ "resolved": ok, "approval_id": aid, "approved": approved }))
        }
        "mcp.servers" => Ok(serde_json::to_value(st.mcp.list_servers()?).unwrap()),
        "mcp.ping" => {
            let srv = p
                .get("server")
                .and_then(Value::as_str)
                .unwrap_or("uefn_editor");
            st.mcp.ping(srv).await
        }

        other => Err(format!("Méthode RPC inconnue : {other}")),
    }
}
