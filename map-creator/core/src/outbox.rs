use crate::config::{now_utc, write_atomic, RootPaths};
use crate::mcp::McpHost;
use crate::pipeline::PipelineStore;
use crate::planner::{AabbCm, PlannerEngine};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fs;
use std::path::PathBuf;
use std::sync::Arc;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutboxOperation {
    pub op_id: String,
    pub plan_item_id: String,
    pub server: String,
    pub tool: String,
    pub write: bool,
    pub arguments: Value,
    pub expected_bounds_cm: AabbCm,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutboxJob {
    pub job_id: String,
    pub project_slug: String,
    pub phase: String,
    pub lot_id: String,
    pub district_id: String,
    pub layers_included: Vec<String>,
    pub status: String, // pending | sent | validated | failed
    pub attempts: u32,
    pub max_attempts: u32,
    pub created_at: String,
    pub updated_at: String,
    pub raw_response_path: Option<String>,
    pub readback_verified: bool,
    pub error_excerpt: Option<String>,
    pub operations: Vec<OutboxOperation>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutboxDispatchReport {
    pub job: OutboxJob,
    pub readback_actor_count: usize,
    pub save_verified: bool,
    pub is_dirty_false: bool,
}

pub struct OutboxEngine {
    paths: RootPaths,
    mcp: Arc<McpHost>,
}

impl OutboxEngine {
    pub fn new(paths: RootPaths, mcp: Arc<McpHost>) -> Self {
        Self { paths, mcp }
    }

    fn status_dir(&self, slug: &str, status: &str) -> PathBuf {
        self.paths.project_dir(slug).join("outbox").join(status)
    }

    fn responses_dir(&self, slug: &str) -> PathBuf {
        self.paths.project_dir(slug).join("outbox/responses")
    }

    pub fn list_jobs(&self, slug: &str) -> Vec<OutboxJob> {
        let mut all = Vec::new();
        for status in ["pending", "sent", "validated", "failed"] {
            let dir = self.status_dir(slug, status);
            if let Ok(entries) = fs::read_dir(dir) {
                for e in entries.flatten() {
                    if e.path().extension().and_then(|s| s.to_str()) == Some("json") {
                        if let Ok(raw) = fs::read_to_string(e.path()) {
                            if let Ok(job) = serde_json::from_str::<OutboxJob>(&raw) {
                                all.push(job);
                            }
                        }
                    }
                }
            }
        }
        all.sort_by(|a, b| b.updated_at.cmp(&a.updated_at));
        all
    }

    pub fn find_job(&self, slug: &str, job_id: &str) -> Result<(OutboxJob, PathBuf), String> {
        for status in ["pending", "sent", "validated", "failed"] {
            let p = self.status_dir(slug, status).join(format!("{job_id}.json"));
            if p.exists() {
                let raw = fs::read_to_string(&p).map_err(|e| e.to_string())?;
                let job: OutboxJob = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
                return Ok((job, p));
            }
        }
        Err(format!("Job outbox introuvable : {job_id}"))
    }

    /// Compiles a checked district plan into an idempotent outbox job under `outbox/pending/`.
    /// Pre-checks the plan FIRST so a broken plan costs 0 MCP calls.
    pub fn submit_from_plan(
        &self,
        slug: &str,
        district_id: &str,
        layers: &[String],
        lot_id: &str,
        phase: &str,
    ) -> Result<OutboxJob, String> {
        let planner = PlannerEngine::new(self.paths.clone());
        let plan = planner.load_plan(slug, district_id)?;
        let check = planner.check_plan(&plan);
        if check.verdict != "PASS" {
            let excerpt: Vec<String> = check
                .issues
                .iter()
                .filter(|i| i.severity == "error")
                .take(3)
                .map(|i| format!("[{}] {}", i.rule, i.detail))
                .collect();
            return Err(format!(
                "PRECHECK_PLAN_FAIL : un plan en échec n'entre jamais dans l'outbox ({})",
                excerpt.join(" ; ")
            ));
        }

        let mut ops = Vec::new();
        for (layer_name, item) in plan.all_items_with_layer() {
            if !layers.is_empty() && !layers.iter().any(|l| l == layer_name) {
                continue;
            }
            let b = item.bounds_cm(&plan.grid);
            let tool = match item.kind.as_str() {
                "spawn" | "device" | "light" => "DeviceToolset.PlaceDevice",
                _ if item.asset_ref.starts_with("ASSET:") => "SceneTools.add_to_scene_from_asset",
                _ => "PrimitiveTools.add_cube",
            };
            ops.push(OutboxOperation {
                op_id: format!("op_{:03}", ops.len() + 1),
                plan_item_id: item.id.clone(),
                server: "uefn_editor".to_string(),
                tool: tool.to_string(),
                write: true,
                arguments: json!({
                    "label": item.id,
                    "plan_item_id": item.id,
                    "kind": item.kind,
                    "asset_ref": item.asset_ref,
                    "expected_bounds": {
                        "min": {"x": b.min[0], "y": b.min[1], "z": b.min[2]},
                        "max": {"x": b.max[0], "y": b.max[1], "z": b.max[2]}
                    }
                }),
                expected_bounds_cm: b,
            });
        }

        // Sort by z_min ascending (Lesson #32: supports placed before objects resting on them)
        ops.sort_by(|a, b| {
            a.expected_bounds_cm.min[2]
                .partial_cmp(&b.expected_bounds_cm.min[2])
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let ts = now_utc();
        let job_id = format!("{}_{}_{}", lot_id, district_id, &uuid::Uuid::new_v4().to_string()[..6]);
        let job = OutboxJob {
            job_id: job_id.clone(),
            project_slug: slug.to_string(),
            phase: phase.to_string(),
            lot_id: lot_id.to_string(),
            district_id: district_id.to_string(),
            layers_included: if layers.is_empty() {
                vec!["a_scene".into(), "b_fonds".into()]
            } else {
                layers.to_vec()
            },
            status: "pending".to_string(),
            attempts: 0,
            max_attempts: 3,
            created_at: ts.clone(),
            updated_at: ts,
            raw_response_path: None,
            readback_verified: false,
            error_excerpt: None,
            operations: ops,
        };

        let target = self.status_dir(slug, "pending").join(format!("{job_id}.json"));
        let raw = serde_json::to_string_pretty(&job).map_err(|e| e.to_string())?;
        write_atomic(&target, raw.as_bytes())?;

        let pipeline = PipelineStore::new(self.paths.clone());
        let _ = pipeline.append_event(
            slug,
            "script",
            &format!(
                "Outbox job '{}' créé en attente ({} opérations, plan vérifié PASS)",
                job_id,
                job.operations.len()
            ),
            Some(format!("outbox/pending/{job_id}.json")),
            json!({ "lot_id": lot_id, "district_id": district_id }),
        );

        Ok(job)
    }

    /// Dispatches a `pending` job through MCP, captures verbatim raw response,
    /// performs independent editor readback + save + is_dirty verification,
    /// and moves the job to `validated/` or `failed/`.
    pub async fn dispatch(
        &self,
        slug: &str,
        job_id: &str,
        mode_override: Option<&str>,
    ) -> Result<OutboxDispatchReport, String> {
        let (mut job, old_path) = self.find_job(slug, job_id)?;
        if job.status == "validated" {
            return Err(format!(
                "IDEMPOTENCE_GUARD : le job '{job_id}' est déjà validé, jamais renvoyé deux fois"
            ));
        }
        if job.attempts >= job.max_attempts {
            return Err(format!(
                "MAX_ATTEMPTS_REACHED : {job_id} a atteint {} essais — escalade auteur obligatoire",
                job.max_attempts
            ));
        }

        // 1. Move to `sent`
        job.attempts += 1;
        job.status = "sent".to_string();
        job.updated_at = now_utc();
        let sent_path = self.status_dir(slug, "sent").join(format!("{job_id}.json"));
        write_atomic(&sent_path, serde_json::to_string_pretty(&job).unwrap().as_bytes())?;
        if old_path != sent_path {
            let _ = fs::remove_file(&old_path);
        }

        // 2. Execute each operation via MCP gateway
        let mut op_responses = Vec::new();
        let mut first_error: Option<String> = None;

        for op in &job.operations {
            let res = self
                .mcp
                .call(
                    slug,
                    &op.server,
                    &op.tool,
                    op.arguments.clone(),
                    op.write,
                    mode_override,
                )
                .await;
            op_responses.push(json!({
                "op_id": op.op_id,
                "plan_item_id": op.plan_item_id,
                "tool": op.tool,
                "rc": res.rc,
                "mode": res.mode,
                "duration_ms": res.duration_ms,
                "payload": res.payload,
                "error": res.error
            }));
            if res.rc != 0 {
                first_error = Some(format!(
                    "Échec sur {} ({}): {}",
                    op.plan_item_id,
                    op.tool,
                    res.error.unwrap_or_else(|| format!("rc={}", res.rc))
                ));
                break; // Error = STOP (no blind retries)
            }
        }

        // 3. Independent grouped readback + save + is_dirty (Never trust "no error" alone!)
        let readback = self
            .mcp
            .call(slug, "uefn_editor", "SceneTools.find_actors", json!({}), false, mode_override)
            .await;
        let save_res = self
            .mcp
            .call(slug, "uefn_editor", "AssetTools.save_assets", json!({}), true, mode_override)
            .await;
        let dirty_res = self
            .mcp
            .call(slug, "uefn_editor", "AssetTools.is_dirty", json!({}), false, mode_override)
            .await;
        let bounds_res = self
            .mcp
            .call(
                slug,
                "uefn_editor",
                "ActorTools.get_actor_bounds",
                json!({"actor": {"refPath": format!("/Game/{slug}/Main.Main:PersistentLevel.LevelBounds_0")}}),
                false,
                mode_override,
            )
            .await;

        let readback_actors = readback
            .payload
            .get("returnValue")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let save_ok = save_res.rc == 0
            && save_res
                .payload
                .get("returnValue")
                .and_then(Value::as_bool)
                .unwrap_or(false);
        let dirty_false = dirty_res.rc == 0
            && dirty_res
                .payload
                .get("returnValue")
                .and_then(Value::as_bool)
                == Some(false);

        // Verify every placed item actually appears in readback
        let mut missing_readback = Vec::new();
        if first_error.is_none() {
            for op in &job.operations {
                let expected_suffix = format!("MC_{}", op.plan_item_id);
                let found = readback_actors.iter().any(|a| {
                    a.get("name").and_then(Value::as_str) == Some(expected_suffix.as_str())
                });
                if !found {
                    missing_readback.push(op.plan_item_id.clone());
                }
            }
        }

        // 4. Write immutable verbatim raw response evidence
        let raw_rel = format!("outbox/responses/{job_id}_attempt_{}.json", job.attempts);
        let raw_abs = self.responses_dir(slug).join(format!("{job_id}_attempt_{}.json", job.attempts));
        let raw_doc = json!({
            "job_id": job.job_id,
            "lot_id": job.lot_id,
            "district_id": job.district_id,
            "attempt": job.attempts,
            "ts_utc": now_utc(),
            "operations": op_responses,
            "closure": {
                "find_actors": { "rc": readback.rc, "tool": "SceneTools.find_actors", "payload": readback.payload },
                "save_assets": { "rc": save_res.rc, "tool": "AssetTools.save_assets", "payload": save_res.payload },
                "is_dirty": { "rc": dirty_res.rc, "tool": "AssetTools.is_dirty", "payload": dirty_res.payload },
                "level_bounds": { "rc": bounds_res.rc, "tool": "ActorTools.get_actor_bounds", "payload": bounds_res.payload }
            }
        });
        write_atomic(&raw_abs, serde_json::to_string_pretty(&raw_doc).unwrap().as_bytes())?;

        // 5. Classify outcome
        let all_ok = first_error.is_none()
            && missing_readback.is_empty()
            && readback.rc == 0
            && save_ok
            && dirty_false;

        job.raw_response_path = Some(raw_rel.clone());
        job.readback_verified = all_ok;
        job.updated_at = now_utc();

        if all_ok {
            job.status = "validated".to_string();
            job.error_excerpt = None;
        } else {
            job.status = "failed".to_string();
            job.error_excerpt = Some(if let Some(err) = first_error {
                err
            } else if !missing_readback.is_empty() {
                format!(
                    "Relecture éditeur incomplète : {} élément(s) absents ({:?})",
                    missing_readback.len(),
                    &missing_readback[..missing_readback.len().min(3)]
                )
            } else if !save_ok || !dirty_false {
                "Persistance non prouvée (save_assets ou is_dirty=false en échec)".to_string()
            } else {
                "Erreur relecture éditeur".to_string()
            });
        }

        let final_path = self.status_dir(slug, &job.status).join(format!("{job_id}.json"));
        write_atomic(&final_path, serde_json::to_string_pretty(&job).unwrap().as_bytes())?;
        let _ = fs::remove_file(&sent_path);

        let pipeline = PipelineStore::new(self.paths.clone());
        let _ = pipeline.append_event(
            slug,
            "editor_readback",
            &format!(
                "Outbox '{}' -> {} ({} acteurs relus, save={}, is_dirty=false:{})",
                job.job_id,
                job.status,
                readback_actors.len(),
                save_ok,
                dirty_false
            ),
            Some(raw_rel),
            json!({ "lot_id": job.lot_id, "status": job.status }),
        );

        Ok(OutboxDispatchReport {
            job,
            readback_actor_count: readback_actors.len(),
            save_verified: save_ok,
            is_dirty_false: dirty_false,
        })
    }

    pub fn read_raw_response(&self, slug: &str, rel_path: &str) -> Result<Value, String> {
        let abs = self.paths.project_dir(slug).join(rel_path);
        let raw = fs::read_to_string(&abs)
            .map_err(|e| format!("Réponse brute introuvable ({}): {e}", abs.display()))?;
        serde_json::from_str(&raw).map_err(|e| e.to_string())
    }
}
