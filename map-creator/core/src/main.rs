mod agent;
mod compat;
mod config;
mod mcp;
mod memory;
mod outbox;
mod permissions;
mod pipeline;
mod planner;
mod protocol;
mod server;
mod tools;
mod validators;

use clap::{Parser, Subcommand};
use config::{load_app_config, RootPaths};
use std::net::SocketAddr;
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "map-creator-core", version = "0.1.0")]
#[command(about = "Map Creator v3 — Rust Core, Agent Loop, Outbox, Protected Validators & JSON App Server")]
struct Cli {
    /// Explicit root path of map-creator/
    #[arg(long)]
    root: Option<PathBuf>,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Launch the JSON-RPC / WebSocket App Server + Svelte Dashboard
    Serve {
        #[arg(long)]
        host: Option<String>,
        #[arg(long)]
        port: Option<u16>,
    },
    /// Run protected validators (MANIFEST integrity -> 20-case Golden Set -> Real project rules)
    Validate {
        #[arg(long)]
        project: Option<String>,
        #[arg(long)]
        golden_only: bool,
    },
    /// HUMAN-ONLY: lock validators/ SHA-256 hashes into validators/MANIFEST.json
    LockValidators {
        #[arg(long, default_value = "human")]
        by: String,
    },
    /// Check a 4-layer district plan offline
    PlanCheck {
        #[arg(long)]
        project: Option<String>,
        #[arg(long, default_value = "district_plaza")]
        district: String,
    },
    /// Search Level-3 reusable library (0 tokens)
    LibrarySearch {
        #[arg(default_value = "")]
        query: String,
        #[arg(long)]
        category: Option<String>,
    },
    /// Show Agent PC compatibility summary
    CompatStatus,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "map_creator_core=info,tower_http=info".into()),
        )
        .init();

    let cli = Cli::parse();
    let paths = RootPaths::discover(cli.root);

    match cli.command {
        Commands::Serve { host, port } => {
            let cfg = load_app_config(&paths).expect("Impossible de charger config/app.toml");
            let bind_host = host.unwrap_or(cfg.server.host);
            let bind_port = port.unwrap_or(cfg.server.port);
            let addr: SocketAddr = format!("{bind_host}:{bind_port}")
                .parse()
                .expect("Adresse IP:Port invalide");

            let state = server::AppState::new(paths.clone());
            let app = server::build_router(state);

            tracing::info!(
                "Map Creator App Server démarré sur http://{addr} (root={})",
                paths.root.display()
            );
            let listener = tokio::net::TcpListener::bind(addr)
                .await
                .expect("Impossible d'écouter sur l'adresse");
            axum::serve(listener, app)
                .await
                .expect("Erreur serveur HTTP");
        }
        Commands::Validate {
            project,
            golden_only,
        } => {
            let slug = project.unwrap_or_else(|| {
                load_app_config(&paths)
                    .map(|c| c.server.active_project)
                    .unwrap_or_else(|_| "neo-kyoto-slice".into())
            });
            let engine = validators::ValidatorEngine::new(paths);
            let report = engine.run_all(&slug, golden_only);
            println!("{}", serde_json::to_string_pretty(&report).unwrap());
            if report.verdict != "PASS" {
                std::process::exit(1);
            }
        }
        Commands::LockValidators { by } => {
            let engine = validators::ValidatorEngine::new(paths);
            match engine.lock_validators(&by) {
                Ok(m) => {
                    println!(
                        "OK validators/MANIFEST.json verrouillé ({} fichiers, par {})",
                        m.files.len(),
                        m.locked_by
                    );
                }
                Err(e) => {
                    eprintln!("ERREUR: {e}");
                    std::process::exit(1);
                }
            }
        }
        Commands::PlanCheck { project, district } => {
            let slug = project.unwrap_or_else(|| {
                load_app_config(&paths)
                    .map(|c| c.server.active_project)
                    .unwrap_or_else(|_| "neo-kyoto-slice".into())
            });
            let pl = planner::PlannerEngine::new(paths);
            match pl.load_plan(&slug, &district) {
                Ok(plan) => {
                    let rep = pl.check_plan(&plan);
                    println!("{}", serde_json::to_string_pretty(&rep).unwrap());
                    if rep.verdict != "PASS" {
                        std::process::exit(1);
                    }
                }
                Err(e) => {
                    eprintln!("ERREUR: {e}");
                    std::process::exit(1);
                }
            }
        }
        Commands::LibrarySearch { query, category } => {
            let mem = memory::MemoryStore::new(paths);
            let hits = mem.search_library(&query, category.as_deref(), false);
            println!("{}", serde_json::to_string_pretty(&hits).unwrap());
        }
        Commands::CompatStatus => {
            let cm = compat::CompatManager::new(paths);
            println!("{}", serde_json::to_string_pretty(&cm.load_summary()).unwrap());
        }
    }
}

#[cfg(test)]
mod integration_tests {
    use super::*;
    use crate::permissions::{Decision, PermissionEngine};
    use crate::pipeline::PipelineStore;
    use crate::protocol::RpcRequest;
    use serde_json::json;
    use tokio::sync::broadcast;

    fn repo_map_creator_root() -> RootPaths {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        RootPaths::discover(Some(manifest_dir.parent().unwrap().to_path_buf()))
    }

    #[test]
    fn test_protected_paths_hard_denied() {
        let paths = repo_map_creator_root();
        let (tx, _) = broadcast::channel(8);
        let perms = PermissionEngine::new(paths, tx);

        let r1 = perms.evaluate_action("write_file", Some("validators/MANIFEST.json"), false);
        assert_eq!(r1.decision, Decision::Deny);

        let r2 = perms.evaluate_action("write_file", Some("config/permissions.toml"), false);
        assert_eq!(r2.decision, Decision::Deny);

        let r3 = perms.evaluate_action(
            "write_file",
            Some("workspace/projects/neo-kyoto-slice/outbox/responses/raw.json"),
            false,
        );
        assert_eq!(r3.decision, Decision::Deny);

        let r4 = perms.evaluate_action(
            "write_file",
            Some("workspace/projects/neo-kyoto-slice/outbox/pending/lot_02.json"),
            false,
        );
        assert_eq!(r4.decision, Decision::Allow);

        // Readonly role (Critique) can NEVER write even to allowed folders
        let r5 = perms.evaluate_action(
            "write_file",
            Some("workspace/projects/neo-kyoto-slice/deliverables/brief.json"),
            true,
        );
        assert_eq!(r5.decision, Decision::Deny);

        // Shell deny pattern
        let r6 = perms.evaluate_action("run_shell", Some("rm -rf /"), false);
        assert_eq!(r6.decision, Decision::Deny);
    }

    #[test]
    fn test_golden_set_20_cases_all_pass() {
        let paths = repo_map_creator_root();
        let val = validators::ValidatorEngine::new(paths);
        let (results, failures) = val.run_golden_set();
        assert_eq!(results.len(), 20, "Golden set must have exactly 20 cases");
        assert!(
            failures.is_empty(),
            "Golden set failures detected: {:?}",
            failures
        );
    }

    #[test]
    fn test_non_sacrifiable_derogation_refused() {
        let paths = repo_map_creator_root();
        let ps = PipelineStore::new(paths);
        let err = ps
            .record_derogation(
                "neo-kyoto-slice",
                vec!["validateurs".into()],
                "vas vite",
            )
            .unwrap_err();
        assert!(err.contains("NON SACRIFIABLE"));
    }

    #[test]
    fn test_library_rejects_agent_claim_provenance() {
        let paths = repo_map_creator_root();
        let mem = memory::MemoryStore::new(paths);
        let entry = memory::LibraryEntry {
            id: "bad_entry".into(),
            category: "verse_module".into(),
            title: "Unverified code".into(),
            summary: "Claimed working".into(),
            tags: vec![],
            provenance: "agent_claim".into(),
            proof_ref: "".into(),
            source_project: "test".into(),
            created_at: "".into(),
            uefn_version: "39.10".into(),
            license: "MIT".into(),
            memory_kb: Some(10),
            status: "verified".into(),
            artifact_path: "none".into(),
        };
        assert!(mem.add_library_entry(entry).is_err());
    }

    #[tokio::test]
    async fn test_rpc_health_and_plan_check() {
        let paths = repo_map_creator_root();
        let state = server::AppState::new(paths);
        let resp = server::dispatch_rpc(
            state.clone(),
            RpcRequest {
                jsonrpc: "2.0".into(),
                id: json!(1),
                method: "system.health".into(),
                params: json!({}),
            },
        )
        .await;
        assert!(resp.error.is_none(), "RPC error: {:?}", resp.error);
        assert_eq!(resp.result.unwrap()["status"], "ok");

        let plan_resp = server::dispatch_rpc(
            state.clone(),
            RpcRequest {
                jsonrpc: "2.0".into(),
                id: json!(2),
                method: "plan.check".into(),
                params: json!({ "district_id": "district_plaza" }),
            },
        )
        .await;
        assert!(plan_resp.error.is_none());
        assert_eq!(plan_resp.result.unwrap()["verdict"], "PASS");
    }

    #[test]
    fn test_plan_checker_catches_floating_and_missing_reason() {
        let paths = repo_map_creator_root();
        let pl = planner::PlannerEngine::new(paths);
        let mut plan = pl.load_plan("neo-kyoto-slice", "district_plaza").unwrap();
        assert_eq!(pl.check_plan(&plan).verdict, "PASS");

        // Inject floating item with empty reason
        plan.layers.c_details.push(planner::PlanItem {
            id: "BAD_FLOAT".into(),
            label: "Bad Float".into(),
            kind: "prop".into(),
            pass: "reel".into(),
            reason: "".into(),
            tile_x: 10.0,
            tile_y: 10.0,
            floor_z: 3.0,
            size_tiles_x: 1.0,
            size_tiles_y: 1.0,
            height_floors: 0.5,
            yaw_deg: 0.0,
            asset_ref: "GRAYBOX:CUBE".into(),
            estimated_memory_kb: 10,
            floating_exempt: false,
        });
        let report = pl.check_plan(&plan);
        assert_eq!(report.verdict, "FAIL");
        assert!(report.issues.iter().any(|i| i.rule == "reason_required"));
        assert!(report.issues.iter().any(|i| i.rule == "zero_flottant"));
    }

    #[tokio::test]
    async fn test_agent_loop_blocks_manifest_tampering() {
        let paths = repo_map_creator_root();
        let state = server::AppState::new(paths);
        let session = state
            .agent
            .run_mission(
                "level_designer",
                "neo-kyoto-slice",
                "Tente de modifier validators/MANIFEST.json (triche)",
            )
            .await
            .unwrap();
        let write_step = session
            .steps
            .iter()
            .filter_map(|s| s.tool_exec.as_ref())
            .find(|t| t.tool == "write_file")
            .expect("write_file step should have been attempted");
        assert!(!write_step.ok, "write_file on MANIFEST.json MUST be denied");
        assert!(write_step
            .error
            .as_deref()
            .unwrap_or("")
            .contains("PERMISSION_DENIED"));
    }

    #[tokio::test]
    async fn test_mcp_blocks_forbidden_and_unproved_write() {
        let paths = repo_map_creator_root();
        let mcp = mcp::McpHost::new(paths);
        let r1 = mcp
            .call(
                "neo-kyoto-slice",
                "uefn_editor",
                "SceneTools.GetDynamicInputSchema",
                json!({}),
                false,
                Some("simulator"),
            )
            .await;
        assert_eq!(r1.rc, 4);
        assert!(r1.error.unwrap().contains("FORBIDDEN_TOOL"));

        let r2 = mcp
            .call(
                "neo-kyoto-slice",
                "uefn_editor",
                "UnknownToolset.nuke_level",
                json!({}),
                true,
                Some("simulator"),
            )
            .await;
        assert_eq!(r2.rc, 4);
        assert!(r2.error.unwrap().contains("UNKNOWN_TOOL_BLOCKED"));
    }
}
