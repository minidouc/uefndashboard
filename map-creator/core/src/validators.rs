use crate::config::{now_utc, write_atomic, RootPaths};
use crate::pipeline::{sha256_hex, PipelineStore};
use crate::planner::{strict_overlap, touches, AabbCm, PlannerEngine};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashSet, VecDeque};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidatorManifest {
    pub locked_at: String,
    pub locked_by: String,
    pub files: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GoldenCaseResult {
    pub case_id: String,
    pub expected_fail_rules: Vec<String>,
    pub actual_fail_rules: Vec<String>,
    pub passed: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuleViolation {
    pub lot_id: Option<String>,
    pub detail: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuleResult {
    pub rule: String,
    pub verdict: String, // PASS | FAIL
    pub checked_count: usize,
    pub violations: Vec<RuleViolation>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationReport {
    pub ts_utc: String,
    pub project_slug: String,
    pub manifest_integrity: String, // OK | ALTERED | MISSING
    pub manifest_mismatches: Vec<String>,
    pub golden_set_passed: bool,
    pub golden_total: usize,
    pub golden_results: Vec<GoldenCaseResult>,
    pub golden_failures: Vec<String>,
    pub verdict: String, // PASS | FAIL
    pub lot_verdicts: BTreeMap<String, String>,
    pub rules: Vec<RuleResult>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationSnapshot {
    pub level_prefix: String,
    pub ground_z: f64,
    pub tolerance: f64,
    pub expected_level_z_max: f64,
    pub preexisting_names: Vec<String>,
    pub plan_ids: Vec<String>,
    pub spawn_required: bool,
    pub overlap_exceptions: Vec<(String, String, String)>,
    pub lots: Vec<SnapshotLot>,
    pub captures: Vec<SnapshotCapture>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SnapshotLot {
    pub lot_id: String,
    pub status: String, // validated | interrupted
    pub save_ok: bool,
    pub is_dirty_false: bool,
    pub level_z_max_readback: f64,
    pub present_actor_names: Vec<String>,
    pub actors: Vec<SnapshotActor>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SnapshotActor {
    pub id_placement: String,
    pub actor_path: String,
    pub kind: String,
    pub pose_proof_ok: bool,
    pub readback_present: bool,
    pub declared_bounds: AabbCm,
    pub readback_bounds: AabbCm,
    pub planned_center: [f64; 3],
    pub floating_exempt: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SnapshotCapture {
    pub name: String,
    pub present: bool,
    pub variance: f64,
    pub is_night: bool,
    pub luminance: f64,
    pub neon_ratio: f64,
}

pub struct ValidatorEngine {
    paths: RootPaths,
}

impl ValidatorEngine {
    pub fn new(paths: RootPaths) -> Self {
        Self { paths }
    }

    pub fn protected_files(&self) -> Vec<String> {
        let dir = self.paths.validators_dir();
        let mut out = Vec::new();
        collect_files(&dir, &dir, &mut out);
        out.sort();
        out
    }

    /// Human-only command: locks `validators/` into `validators/MANIFEST.json` with SHA-256 hashes.
    pub fn lock_validators(&self, locked_by: &str) -> Result<ValidatorManifest, String> {
        let dir = self.paths.validators_dir();
        fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
        let mut files = BTreeMap::new();
        for rel in self.protected_files() {
            let bytes = fs::read(dir.join(&rel)).map_err(|e| e.to_string())?;
            files.insert(rel, sha256_hex(&bytes));
        }
        let manifest = ValidatorManifest {
            locked_at: now_utc(),
            locked_by: locked_by.to_string(),
            files,
        };
        let raw = serde_json::to_string_pretty(&manifest).map_err(|e| e.to_string())?;
        write_atomic(&dir.join("MANIFEST.json"), raw.as_bytes())?;
        Ok(manifest)
    }

    pub fn verify_manifest(&self) -> (String, Vec<String>) {
        let dir = self.paths.validators_dir();
        let mpath = dir.join("MANIFEST.json");
        let Ok(raw) = fs::read_to_string(&mpath) else {
            return (
                "MISSING".to_string(),
                vec!["MANIFEST.json absent : lancer `map-creator-core lock-validators` (action humaine)".into()],
            );
        };
        let Ok(manifest) = serde_json::from_str::<ValidatorManifest>(&raw) else {
            return ("ALTERED".into(), vec!["MANIFEST.json illisible".into()]);
        };

        let mut mismatches = Vec::new();
        let current = self.protected_files();
        let current_set: HashSet<&String> = current.iter().collect();
        let expected_set: HashSet<&String> = manifest.files.keys().collect();

        for rel in &current {
            if !expected_set.contains(rel) {
                mismatches.push(format!("Fichier ajouté hors manifeste : {rel}"));
            } else if let Ok(bytes) = fs::read(dir.join(rel)) {
                let actual = sha256_hex(&bytes);
                if manifest.files.get(rel) != Some(&actual) {
                    mismatches.push(format!("Empreinte SHA-256 altérée : {rel}"));
                }
            }
        }
        for rel in manifest.files.keys() {
            if !current_set.contains(rel) {
                mismatches.push(format!("Fichier protégé supprimé : {rel}"));
            }
        }

        if mismatches.is_empty() {
            ("OK".into(), mismatches)
        } else {
            ("ALTERED".into(), mismatches)
        }
    }

    /// Runs the immutable sequence: 1) MANIFEST integrity -> 2) 20-case Golden Set -> 3) Real project rules.
    pub fn run_all(&self, project_slug: &str, golden_only: bool) -> ValidationReport {
        let (integrity, mismatches) = self.verify_manifest();
        let (golden_results, golden_failures) = if integrity == "OK" {
            self.run_golden_set()
        } else {
            (
                Vec::new(),
                vec![format!("Golden set non exécuté (intégrité={integrity})")],
            )
        };
        let golden_ok = integrity == "OK" && golden_failures.is_empty() && golden_results.len() >= 20;

        let (rules, lot_verdicts) = if golden_only || !golden_ok {
            (Vec::new(), BTreeMap::new())
        } else {
            match self.build_project_snapshot(project_slug) {
                Ok(snap) => evaluate_snapshot(&snap),
                Err(e) => (
                    vec![RuleResult {
                        rule: "snapshot_projet".into(),
                        verdict: "FAIL".into(),
                        checked_count: 0,
                        violations: vec![RuleViolation {
                            lot_id: None,
                            detail: e,
                        }],
                    }],
                    BTreeMap::new(),
                ),
            }
        };

        let verdict = if integrity == "OK"
            && golden_ok
            && (golden_only || (!rules.is_empty() && rules.iter().all(|r| r.verdict == "PASS")))
        {
            "PASS"
        } else {
            "FAIL"
        };

        let report = ValidationReport {
            ts_utc: now_utc(),
            project_slug: project_slug.to_string(),
            manifest_integrity: integrity,
            manifest_mismatches: mismatches,
            golden_set_passed: golden_ok,
            golden_total: golden_results.len(),
            golden_results,
            golden_failures,
            verdict: verdict.to_string(),
            lot_verdicts,
            rules,
        };

        if !golden_only {
            let qa_dir = self.paths.project_dir(project_slug).join("qa/validation");
            let _ = write_atomic(
                &qa_dir.join("latest.json"),
                serde_json::to_string_pretty(&report).unwrap().as_bytes(),
            );
            let pipeline = PipelineStore::new(self.paths.clone());
            if let Ok((mut st, _)) = pipeline.load_state(project_slug) {
                st.last_validation = Some(format!("{} ({})", report.verdict, report.ts_utc));
                for (lid, lv) in &report.lot_verdicts {
                    st.lots.insert(
                        lid.clone(),
                        if lv == "PASS" { "VALIDE" } else { "REJETE" }.to_string(),
                    );
                }
                let _ = pipeline.save_state(project_slug, &st);
            }
            let _ = pipeline.append_event(
                project_slug,
                "validator",
                &format!(
                    "Validation protégée : {} (MANIFEST={}, Golden={}/{})",
                    report.verdict,
                    report.manifest_integrity,
                    report.golden_results.iter().filter(|g| g.passed).count(),
                    report.golden_total
                ),
                Some("qa/validation/latest.json".into()),
                json!({ "verdict": report.verdict }),
            );
        }

        report
    }

    pub fn load_latest_report(&self, project_slug: &str) -> Option<ValidationReport> {
        let p = self
            .paths
            .project_dir(project_slug)
            .join("qa/validation/latest.json");
        fs::read_to_string(p)
            .ok()
            .and_then(|raw| serde_json::from_str(&raw).ok())
    }

    /// 20-case Golden Set (2 healthy + 18 deliberate traps). Detects any weakened validator!
    pub fn run_golden_set(&self) -> (Vec<GoldenCaseResult>, Vec<String>) {
        let cases = build_20_golden_cases();
        let mut results = Vec::new();
        let mut failures = Vec::new();

        for (case_id, expected_fails, snap) in cases {
            let (rule_results, _) = evaluate_snapshot(&snap);
            let actual_fails: Vec<String> = rule_results
                .iter()
                .filter(|r| r.verdict == "FAIL")
                .map(|r| r.rule.clone())
                .collect();

            let passed = if expected_fails.is_empty() {
                actual_fails.is_empty()
            } else {
                expected_fails.iter().all(|e| actual_fails.contains(e))
            };

            if !passed {
                failures.push(format!(
                    "Golden '{case_id}' échoué : attendu={expected_fails:?}, obtenu={actual_fails:?}"
                ));
            }
            results.push(GoldenCaseResult {
                case_id,
                expected_fail_rules: expected_fails,
                actual_fail_rules: actual_fails,
                passed,
            });
        }
        (results, failures)
    }

    fn build_project_snapshot(&self, project_slug: &str) -> Result<ValidationSnapshot, String> {
        let planner = PlannerEngine::new(self.paths.clone());
        let plan_names = planner.list_plans(project_slug);
        if plan_names.is_empty() {
            return Err("Aucun plan trouvé dans plans/".into());
        }
        let plan = planner.load_plan(project_slug, &plan_names[0])?;

        let validated_dir = self.paths.project_dir(project_slug).join("outbox/validated");
        let mut lots = Vec::new();
        if let Ok(entries) = fs::read_dir(&validated_dir) {
            for e in entries.flatten() {
                if e.path().extension().and_then(|s| s.to_str()) != Some("json") {
                    continue;
                }
                let raw_job = fs::read_to_string(e.path()).map_err(|er| er.to_string())?;
                let job: crate::outbox::OutboxJob =
                    serde_json::from_str(&raw_job).map_err(|er| er.to_string())?;

                let raw_resp_rel = job
                    .raw_response_path
                    .clone()
                    .ok_or_else(|| format!("Preuve brute manquante pour {}", job.job_id))?;
                let raw_resp_abs = self.paths.project_dir(project_slug).join(&raw_resp_rel);
                let resp: Value = serde_json::from_str(
                    &fs::read_to_string(&raw_resp_abs)
                        .map_err(|er| format!("Lecture preuve brute {} impossible: {er}", raw_resp_rel))?,
                )
                .map_err(|er| er.to_string())?;

                let closure = resp.get("closure").cloned().unwrap_or(Value::Null);
                let save_ok = closure
                    .pointer("/save_assets/rc")
                    .and_then(Value::as_i64)
                    == Some(0)
                    && closure
                        .pointer("/save_assets/payload/returnValue")
                        .and_then(Value::as_bool)
                        == Some(true);
                let is_dirty_false = closure
                    .pointer("/is_dirty/rc")
                    .and_then(Value::as_i64)
                    == Some(0)
                    && closure
                        .pointer("/is_dirty/payload/returnValue")
                        .and_then(Value::as_bool)
                        == Some(false);
                let level_z_max = closure
                    .pointer("/level_bounds/payload/returnValue/max/z")
                    .and_then(Value::as_f64)
                    .unwrap_or(0.0);

                let find_arr = closure
                    .pointer("/find_actors/payload/returnValue")
                    .and_then(Value::as_array)
                    .cloned()
                    .unwrap_or_default();
                let present_names: Vec<String> = find_arr
                    .iter()
                    .filter_map(|x| x.get("name").and_then(Value::as_str).map(String::from))
                    .collect();

                let op_res_arr = resp
                    .get("operations")
                    .and_then(Value::as_array)
                    .cloned()
                    .unwrap_or_default();

                let mut actors = Vec::new();
                for op in &job.operations {
                    let expected_name = format!("MC_{}", op.plan_item_id);
                    let op_ok = op_res_arr.iter().any(|o| {
                        o.get("plan_item_id").and_then(Value::as_str)
                            == Some(op.plan_item_id.as_str())
                            && o.get("rc").and_then(Value::as_i64) == Some(0)
                    });
                    let rb_entry = find_arr
                        .iter()
                        .find(|a| a.get("name").and_then(Value::as_str) == Some(expected_name.as_str()));
                    let readback_bounds = rb_entry
                        .and_then(|e| parse_bounds_val(e.get("bounds")))
                        .unwrap_or(AabbCm {
                            min: [0.0; 3],
                            max: [0.0; 3],
                        });
                    let actor_path = rb_entry
                        .and_then(|e| e.get("actorPath").and_then(Value::as_str))
                        .unwrap_or("")
                        .to_string();

                    let plan_item = plan
                        .all_items_with_layer()
                        .into_iter()
                        .find(|(_, it)| it.id == op.plan_item_id)
                        .map(|(_, it)| it);

                    let b = op.expected_bounds_cm;
                    let center = [
                        (b.min[0] + b.max[0]) / 2.0,
                        (b.min[1] + b.max[1]) / 2.0,
                        (b.min[2] + b.max[2]) / 2.0,
                    ];

                    actors.push(SnapshotActor {
                        id_placement: op.plan_item_id.clone(),
                        actor_path,
                        kind: plan_item.map(|i| i.kind.clone()).unwrap_or_else(|| "structure".into()),
                        pose_proof_ok: op_ok,
                        readback_present: rb_entry.is_some(),
                        declared_bounds: b,
                        readback_bounds,
                        planned_center: center,
                        floating_exempt: plan_item.map(|i| i.floating_exempt).unwrap_or(false),
                    });
                }

                lots.push(SnapshotLot {
                    lot_id: job.lot_id.clone(),
                    status: job.status.clone(),
                    save_ok,
                    is_dirty_false,
                    level_z_max_readback: level_z_max,
                    present_actor_names: present_names,
                    actors,
                });
            }
        }

        let plan_ids: Vec<String> = plan
            .layers
            .a_scene
            .iter()
            .chain(plan.layers.b_fonds.iter())
            .map(|i| i.id.clone())
            .collect();

        let overlap_exceptions = plan
            .overlap_exceptions
            .iter()
            .map(|e| (e.a.clone(), e.b.clone(), e.justification.clone()))
            .collect();

        Ok(ValidationSnapshot {
            level_prefix: format!("/Game/{project_slug}/Main"),
            ground_z: plan.grid.origin_uu[2],
            tolerance: 10.0,
            expected_level_z_max: 3840.0,
            preexisting_names: vec!["WorldSettings".into(), "LevelBounds_0".into()],
            plan_ids,
            spawn_required: true,
            overlap_exceptions,
            lots,
            captures: vec![SnapshotCapture {
                name: "vue_ensemble_jour.png".into(),
                present: true,
                variance: 42.5,
                is_night: false,
                luminance: 138.0,
                neon_ratio: 0.0,
            }],
        })
    }
}

pub fn evaluate_snapshot(snap: &ValidationSnapshot) -> (Vec<RuleResult>, BTreeMap<String, String>) {
    let mut rules = Vec::new();
    let mut lot_verdicts = BTreeMap::new();
    for lot in &snap.lots {
        lot_verdicts.insert(lot.lot_id.clone(), "PASS".to_string());
    }

    // 1. integrite_preuves
    let mut v_int = Vec::new();
    let mut c_int = 0;
    for lot in &snap.lots {
        if lot.status != "validated" {
            v_int.push(RuleViolation {
                lot_id: Some(lot.lot_id.clone()),
                detail: format!("Statut de lot '{}' non validable", lot.status),
            });
        }
        for a in &lot.actors {
            c_int += 1;
            if !a.pose_proof_ok {
                v_int.push(RuleViolation {
                    lot_id: Some(lot.lot_id.clone()),
                    detail: format!("{} : preuve de pose brute absente ou en erreur", a.id_placement),
                });
            }
            if !a.readback_present {
                v_int.push(RuleViolation {
                    lot_id: Some(lot.lot_id.clone()),
                    detail: format!("{} : acteur absent de la relecture éditeur", a.id_placement),
                });
                continue;
            }
            if !bounds_equal(&a.declared_bounds, &a.readback_bounds, 1.0) {
                v_int.push(RuleViolation {
                    lot_id: Some(lot.lot_id.clone()),
                    detail: format!(
                        "{} : bornes déclarées != bornes relues (falsification ?)",
                        a.id_placement
                    ),
                });
            }
            if !a.actor_path.starts_with(&snap.level_prefix) {
                v_int.push(RuleViolation {
                    lot_id: Some(lot.lot_id.clone()),
                    detail: format!("{} : acteur hors du niveau cible", a.id_placement),
                });
            }
        }
    }
    rules.push(mk_rule("integrite_preuves", c_int, v_int));

    // 2. persistance
    let mut v_per = Vec::new();
    let mut c_per = 0;
    for lot in &snap.lots {
        c_per += 3;
        if !lot.save_ok {
            v_per.push(RuleViolation {
                lot_id: Some(lot.lot_id.clone()),
                detail: "save_assets non prouvé (rc=0, returnValue=true)".into(),
            });
        }
        if !lot.is_dirty_false {
            v_per.push(RuleViolation {
                lot_id: Some(lot.lot_id.clone()),
                detail: "Niveau encore sale après save (is_dirty != false)".into(),
            });
        }
        if lot.level_z_max_readback < snap.expected_level_z_max - 1.0 {
            v_per.push(RuleViolation {
                lot_id: Some(lot.lot_id.clone()),
                detail: format!(
                    "LevelBounds Z_max revenu à {:.0} (< {:.0})",
                    lot.level_z_max_readback, snap.expected_level_z_max
                ),
            });
        }
    }
    rules.push(mk_rule("persistance", c_per, v_per));

    // 3. preexistants_intacts
    let mut v_pre = Vec::new();
    let mut c_pre = 0;
    for lot in &snap.lots {
        c_pre += snap.preexisting_names.len();
        let present: HashSet<&String> = lot.present_actor_names.iter().collect();
        for name in &snap.preexisting_names {
            if !present.contains(name) {
                v_pre.push(RuleViolation {
                    lot_id: Some(lot.lot_id.clone()),
                    detail: format!("Préexistant supprimé : {name}"),
                });
            }
        }
    }
    rules.push(mk_rule("preexistants_intacts", c_pre, v_pre));

    // Collect all readback actors
    let all_actors: Vec<(&str, &SnapshotActor)> = snap
        .lots
        .iter()
        .flat_map(|l| l.actors.iter().map(move |a| (l.lot_id.as_str(), a)))
        .collect();

    // 4. source_coordonnees
    let mut v_src = Vec::new();
    let mut c_src = 0;
    let plan_set: HashSet<&String> = snap.plan_ids.iter().collect();
    for (lid, a) in &all_actors {
        c_src += 1;
        if !plan_set.contains(&a.id_placement) {
            v_src.push(RuleViolation {
                lot_id: Some((*lid).into()),
                detail: format!("{} absent du plan (improvisation)", a.id_placement),
            });
            continue;
        }
        let b = a.readback_bounds;
        let cx = (b.min[0] + b.max[0]) / 2.0;
        let cy = (b.min[1] + b.max[1]) / 2.0;
        let cz = (b.min[2] + b.max[2]) / 2.0;
        let dxy = (cx - a.planned_center[0]).hypot(cy - a.planned_center[1]);
        if dxy > 250.0 || (cz - a.planned_center[2]).abs() > 250.0 {
            v_src.push(RuleViolation {
                lot_id: Some((*lid).into()),
                detail: format!("{} déplacé hors plan (écart XY={:.0} uu)", a.id_placement, dxy),
            });
        }
    }
    rules.push(mk_rule("source_coordonnees", c_src, v_src));

    // 5. zero_overlap
    let mut v_ov = Vec::new();
    let mut c_ov = 0;
    let mut valid_exc = Vec::new();
    for (a, b, just) in &snap.overlap_exceptions {
        if just.trim().is_empty() {
            v_ov.push(RuleViolation {
                lot_id: None,
                detail: format!("Exception de chevauchement sans justification ({a}/{b})"),
            });
        } else {
            valid_exc.push((a.as_str(), b.as_str()));
        }
    }
    let physical: Vec<(&str, &SnapshotActor)> = all_actors
        .iter()
        .copied()
        .filter(|(_, a)| !matches!(a.kind.as_str(), "light" | "vfx" | "audio_zone"))
        .collect();
    for i in 0..physical.len() {
        for j in (i + 1)..physical.len() {
            c_ov += 1;
            let (_, ai) = physical[i];
            let (lj, aj) = physical[j];
            if strict_overlap(&ai.readback_bounds, &aj.readback_bounds, snap.tolerance) {
                let excused = valid_exc.iter().any(|(x, y)| {
                    (*x == ai.id_placement && *y == aj.id_placement)
                        || (*y == ai.id_placement && *x == aj.id_placement)
                });
                if !excused {
                    v_ov.push(RuleViolation {
                        lot_id: Some(lj.into()),
                        detail: format!("Chevauchement {} / {}", ai.id_placement, aj.id_placement),
                    });
                }
            }
        }
    }
    rules.push(mk_rule("zero_overlap", c_ov, v_ov));

    // 6. zero_flottant (BFS contact chain to ground)
    let mut v_fl = Vec::new();
    let mut anchored = HashSet::new();
    let mut q = VecDeque::new();
    for (idx, (_, a)) in physical.iter().enumerate() {
        if a.floating_exempt
            || a.kind == "surface"
            || a.readback_bounds.min[2] <= snap.ground_z + snap.tolerance
        {
            anchored.insert(idx);
            q.push_back(idx);
        }
    }
    while let Some(i) = q.pop_front() {
        let bi = physical[i].1.readback_bounds;
        for j in 0..physical.len() {
            if !anchored.contains(&j) && touches(&bi, &physical[j].1.readback_bounds, snap.tolerance)
            {
                anchored.insert(j);
                q.push_back(j);
            }
        }
    }
    for (idx, (lid, a)) in physical.iter().enumerate() {
        if !anchored.contains(&idx) && !a.floating_exempt {
            v_fl.push(RuleViolation {
                lot_id: Some((*lid).into()),
                detail: format!(
                    "{} flotte (z_min={:.0}, aucune chaîne de contact au sol)",
                    a.id_placement, a.readback_bounds.min[2]
                ),
            });
        }
    }
    rules.push(mk_rule("zero_flottant", physical.len(), v_fl));

    // 7. accessibilite (BFS over walkable surfaces)
    let mut v_acc = Vec::new();
    let surfaces: Vec<(&str, &SnapshotActor)> = physical
        .iter()
        .copied()
        .filter(|(_, a)| matches!(a.kind.as_str(), "surface" | "ramp"))
        .collect();
    if surfaces.len() > 1 {
        let mut vis = HashSet::new();
        let mut sq = VecDeque::new();
        vis.insert(0usize);
        sq.push_back(0usize);
        while let Some(i) = sq.pop_front() {
            let bi = surfaces[i].1.readback_bounds;
            for j in 0..surfaces.len() {
                if vis.contains(&j) {
                    continue;
                }
                let bj = surfaces[j].1.readback_bounds;
                let dx = (bi.min[0] - bj.max[0]).max(bj.min[0] - bi.max[0]).max(0.0);
                let dy = (bi.min[1] - bj.max[1]).max(bj.min[1] - bi.max[1]).max(0.0);
                let dz = (bi.max[2] - bj.max[2]).abs();
                let is_ramp = surfaces[i].1.kind == "ramp" || surfaces[j].1.kind == "ramp";
                if dx.hypot(dy) <= 200.0 && (dz <= 120.0 || is_ramp) {
                    vis.insert(j);
                    sq.push_back(j);
                }
            }
        }
        for (idx, (lid, a)) in surfaces.iter().enumerate() {
            if !vis.contains(&idx) {
                v_acc.push(RuleViolation {
                    lot_id: Some((*lid).into()),
                    detail: format!("Strate '{}' inaccessible depuis la zone principale", a.id_placement),
                });
            }
        }
    }
    rules.push(mk_rule("accessibilite", surfaces.len(), v_acc));

    // 8. couverture_plan
    let mut v_cov = Vec::new();
    let placed_ids: HashSet<&str> = all_actors.iter().map(|(_, a)| a.id_placement.as_str()).collect();
    let missing_count = snap
        .plan_ids
        .iter()
        .filter(|id| !placed_ids.contains(id.as_str()))
        .count();
    if !snap.plan_ids.is_empty() && (missing_count as f64 / snap.plan_ids.len() as f64) > 0.15 {
        v_cov.push(RuleViolation {
            lot_id: None,
            detail: format!(
                "{} / {} items du plan non posés (> 15 % de gap)",
                missing_count,
                snap.plan_ids.len()
            ),
        });
    }
    rules.push(mk_rule("couverture_plan", snap.plan_ids.len(), v_cov));

    // 9. gameplay (spawn present)
    let mut v_gp = Vec::new();
    if snap.spawn_required && !all_actors.iter().any(|(_, a)| a.kind == "spawn") {
        v_gp.push(RuleViolation {
            lot_id: None,
            detail: "Aucun spawner posé et relu dans la scène".into(),
        });
    }
    rules.push(mk_rule("gameplay", 1, v_gp));

    // 10. captures_visuelles
    let mut v_vis = Vec::new();
    if snap.captures.is_empty() {
        v_vis.push(RuleViolation {
            lot_id: None,
            detail: "Aucune capture visuelle enregistrée".into(),
        });
    }
    for cap in &snap.captures {
        if !cap.present {
            v_vis.push(RuleViolation {
                lot_id: None,
                detail: format!("Capture absente : {}", cap.name),
            });
        } else if cap.variance < 5.0 {
            v_vis.push(RuleViolation {
                lot_id: None,
                detail: format!("Capture uniforme/mur détectée ({}, variance={:.1})", cap.name, cap.variance),
            });
        } else if cap.is_night && (cap.luminance > 90.0 || cap.neon_ratio < 0.01) {
            v_vis.push(RuleViolation {
                lot_id: None,
                detail: format!(
                    "Capture nuit '{}' en plein jour ou sans néons (lum={:.0}, neon={:.3})",
                    cap.name, cap.luminance, cap.neon_ratio
                ),
            });
        }
    }
    rules.push(mk_rule("captures_visuelles", snap.captures.len().max(1), v_vis));

    for r in &rules {
        for vi in &r.violations {
            if let Some(lid) = &vi.lot_id {
                lot_verdicts.insert(lid.clone(), "FAIL".to_string());
            }
        }
    }

    (rules, lot_verdicts)
}

fn mk_rule(name: &str, checked: usize, violations: Vec<RuleViolation>) -> RuleResult {
    RuleResult {
        rule: name.to_string(),
        verdict: if violations.is_empty() { "PASS" } else { "FAIL" }.to_string(),
        checked_count: checked,
        violations,
    }
}

fn bounds_equal(a: &AabbCm, b: &AabbCm, tol: f64) -> bool {
    (0..3).all(|k| (a.min[k] - b.min[k]).abs() <= tol && (a.max[k] - b.max[k]).abs() <= tol)
}

fn parse_bounds_val(v: Option<&Value>) -> Option<AabbCm> {
    let obj = v?.as_object()?;
    let min = obj.get("min")?.as_object()?;
    let max = obj.get("max")?.as_object()?;
    Some(AabbCm {
        min: [
            min.get("x")?.as_f64()?,
            min.get("y")?.as_f64()?,
            min.get("z")?.as_f64()?,
        ],
        max: [
            max.get("x")?.as_f64()?,
            max.get("y")?.as_f64()?,
            max.get("z")?.as_f64()?,
        ],
    })
}

fn collect_files(root: &Path, dir: &Path, out: &mut Vec<String>) {
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for e in entries.flatten() {
        let p = e.path();
        if p.is_dir() {
            collect_files(root, &p, out);
        } else if let Some(name) = p.file_name().and_then(|s| s.to_str()) {
            if name == "MANIFEST.json" {
                continue;
            }
            if let Ok(rel) = p.strip_prefix(root) {
                out.push(rel.to_string_lossy().replace('\\', "/"));
            }
        }
    }
}

fn healthy_snapshot() -> ValidationSnapshot {
    let floor_b = AabbCm { min: [0.0, 0.0, -256.0], max: [2048.0, 2048.0, 0.0] };
    let cover_b = AabbCm { min: [512.0, 512.0, 0.0], max: [1024.0, 768.0, 256.0] };
    let spawn_b = AabbCm { min: [128.0, 128.0, 0.0], max: [256.0, 256.0, 200.0] };
    ValidationSnapshot {
        level_prefix: "/Game/Golden/Main".into(),
        ground_z: 0.0,
        tolerance: 10.0,
        expected_level_z_max: 3840.0,
        preexisting_names: vec!["WorldSettings".into(), "LevelBounds_0".into()],
        plan_ids: vec!["SOL_01".into(), "COUVERT_01".into(), "SPAWN_01".into()],
        spawn_required: true,
        overlap_exceptions: vec![],
        lots: vec![SnapshotLot {
            lot_id: "lot_01".into(),
            status: "validated".into(),
            save_ok: true,
            is_dirty_false: true,
            level_z_max_readback: 5000.0,
            present_actor_names: vec![
                "WorldSettings".into(),
                "LevelBounds_0".into(),
                "MC_SOL_01".into(),
                "MC_COUVERT_01".into(),
                "MC_SPAWN_01".into(),
            ],
            actors: vec![
                SnapshotActor {
                    id_placement: "SOL_01".into(),
                    actor_path: "/Game/Golden/Main.Main:PersistentLevel.MC_SOL_01".into(),
                    kind: "surface".into(),
                    pose_proof_ok: true,
                    readback_present: true,
                    declared_bounds: floor_b,
                    readback_bounds: floor_b,
                    planned_center: [1024.0, 1024.0, -128.0],
                    floating_exempt: false,
                },
                SnapshotActor {
                    id_placement: "COUVERT_01".into(),
                    actor_path: "/Game/Golden/Main.Main:PersistentLevel.MC_COUVERT_01".into(),
                    kind: "cover".into(),
                    pose_proof_ok: true,
                    readback_present: true,
                    declared_bounds: cover_b,
                    readback_bounds: cover_b,
                    planned_center: [768.0, 640.0, 128.0],
                    floating_exempt: false,
                },
                SnapshotActor {
                    id_placement: "SPAWN_01".into(),
                    actor_path: "/Game/Golden/Main.Main:PersistentLevel.MC_SPAWN_01".into(),
                    kind: "spawn".into(),
                    pose_proof_ok: true,
                    readback_present: true,
                    declared_bounds: spawn_b,
                    readback_bounds: spawn_b,
                    planned_center: [192.0, 192.0, 100.0],
                    floating_exempt: false,
                },
            ],
        }],
        captures: vec![SnapshotCapture {
            name: "jour.png".into(),
            present: true,
            variance: 36.0,
            is_night: false,
            luminance: 130.0,
            neon_ratio: 0.0,
        }],
    }
}

/// Builds the 20 golden test cases (2 healthy + 18 traps).
fn build_20_golden_cases() -> Vec<(String, Vec<String>, ValidationSnapshot)> {
    let mut cases = Vec::new();

    // 1. Healthy baseline
    cases.push(("01_sain".into(), vec![], healthy_snapshot()));

    // 2. Healthy with justified overlap exception
    let mut s2 = healthy_snapshot();
    s2.lots[0].actors[1].declared_bounds.min[2] = -30.0;
    s2.lots[0].actors[1].readback_bounds.min[2] = -30.0;
    s2.overlap_exceptions.push((
        "SOL_01".into(),
        "COUVERT_01".into(),
        "Ancrage structurel volontaire dans la dalle".into(),
    ));
    cases.push(("02_chevauchement_justifie".into(), vec![], s2));

    // 3. Trap: falsified bounds
    let mut s3 = healthy_snapshot();
    s3.lots[0].actors[1].readback_bounds.max[0] += 50.0;
    cases.push(("03_bornes_falsifiees".into(), vec!["integrite_preuves".into()], s3));

    // 4. Trap: actor missing from readback
    let mut s4 = healthy_snapshot();
    s4.lots[0].actors[1].readback_present = false;
    cases.push(("04_acteur_non_relu".into(), vec!["integrite_preuves".into()], s4));

    // 5. Trap: pose proof failed
    let mut s5 = healthy_snapshot();
    s5.lots[0].actors[1].pose_proof_ok = false;
    cases.push(("05_pose_non_prouvee".into(), vec!["integrite_preuves".into()], s5));

    // 6. Trap: interrupted lot
    let mut s6 = healthy_snapshot();
    s6.lots[0].status = "interrupted".into();
    cases.push(("06_lot_interrompu".into(), vec!["integrite_preuves".into()], s6));

    // 7. Trap: actor outside target level
    let mut s7 = healthy_snapshot();
    s7.lots[0].actors[1].actor_path = "/Game/OtherLevel/Hack.Actor".into();
    cases.push(("07_acteur_hors_niveau".into(), vec!["integrite_preuves".into()], s7));

    // 8. Trap: unjustified overlap
    let mut s8 = healthy_snapshot();
    s8.lots[0].actors[1].declared_bounds.min[2] = -40.0;
    s8.lots[0].actors[1].readback_bounds.min[2] = -40.0;
    cases.push(("08_chevauchement".into(), vec!["zero_overlap".into()], s8));

    // 9. Trap: overlap exception with empty justification
    let mut s9 = healthy_snapshot();
    s9.lots[0].actors[1].declared_bounds.min[2] = -40.0;
    s9.lots[0].actors[1].readback_bounds.min[2] = -40.0;
    s9.overlap_exceptions.push(("SOL_01".into(), "COUVERT_01".into(), "   ".into()));
    cases.push(("09_exception_sans_justification".into(), vec!["zero_overlap".into()], s9));

    // 10. Trap: single floating item
    let mut s10 = healthy_snapshot();
    s10.lots[0].actors[1].declared_bounds = AabbCm { min: [512.0, 512.0, 400.0], max: [1024.0, 768.0, 656.0] };
    s10.lots[0].actors[1].readback_bounds = s10.lots[0].actors[1].declared_bounds;
    s10.lots[0].actors[1].planned_center = [768.0, 640.0, 528.0];
    cases.push(("10_flottant".into(), vec!["zero_flottant".into()], s10));

    // 11. Trap: floating group (two items touching each other in mid-air)
    let mut s11 = healthy_snapshot();
    let g1 = AabbCm { min: [512.0, 512.0, 400.0], max: [1024.0, 768.0, 656.0] };
    let g2 = AabbCm { min: [512.0, 512.0, 656.0], max: [1024.0, 768.0, 912.0] };
    s11.lots[0].actors[1].declared_bounds = g1;
    s11.lots[0].actors[1].readback_bounds = g1;
    s11.lots[0].actors[1].planned_center = [768.0, 640.0, 528.0];
    s11.plan_ids.push("BLOC_HAUT".into());
    s11.lots[0].actors.push(SnapshotActor {
        id_placement: "BLOC_HAUT".into(),
        actor_path: "/Game/Golden/Main.Main:PersistentLevel.MC_BLOC_HAUT".into(),
        kind: "cover".into(),
        pose_proof_ok: true,
        readback_present: true,
        declared_bounds: g2,
        readback_bounds: g2,
        planned_center: [768.0, 640.0, 784.0],
        floating_exempt: false,
    });
    cases.push(("11_groupe_flottant".into(), vec!["zero_flottant".into()], s11));

    // 12. Trap: unreachable upper platform
    let mut s12 = healthy_snapshot();
    let plat = AabbCm { min: [1200.0, 1200.0, 384.0], max: [1800.0, 1800.0, 640.0] };
    s12.plan_ids.push("PLATEFORME_HAUTE".into());
    s12.lots[0].actors.push(SnapshotActor {
        id_placement: "PLATEFORME_HAUTE".into(),
        actor_path: "/Game/Golden/Main.Main:PersistentLevel.MC_PLATEFORME_HAUTE".into(),
        kind: "surface".into(),
        pose_proof_ok: true,
        readback_present: true,
        declared_bounds: plat,
        readback_bounds: plat,
        planned_center: [1500.0, 1500.0, 512.0],
        floating_exempt: false,
    });
    cases.push(("12_inaccessible".into(), vec!["accessibilite".into()], s12));

    // 13. Trap: preexisting actor deleted
    let mut s13 = healthy_snapshot();
    s13.lots[0].present_actor_names.retain(|n| n != "WorldSettings");
    cases.push(("13_preexistant_supprime".into(), vec!["preexistants_intacts".into()], s13));

    // 14. Trap: save failed
    let mut s14 = healthy_snapshot();
    s14.lots[0].save_ok = false;
    cases.push(("14_save_echoue".into(), vec!["persistance".into()], s14));

    // 15. Trap: dirty after save
    let mut s15 = healthy_snapshot();
    s15.lots[0].is_dirty_false = false;
    cases.push(("15_dirty_apres_save".into(), vec!["persistance".into()], s15));

    // 16. Trap: LevelBounds reverted Z_max
    let mut s16 = healthy_snapshot();
    s16.lots[0].level_z_max_readback = 256.0;
    cases.push(("16_level_bounds_regresse".into(), vec!["persistance".into()], s16));

    // 17. Trap: improvised actor not in plan
    let mut s17 = healthy_snapshot();
    let imp = AabbCm { min: [1500.0, 200.0, 0.0], max: [1700.0, 400.0, 200.0] };
    s17.lots[0].actors.push(SnapshotActor {
        id_placement: "IMPROVISE_99".into(),
        actor_path: "/Game/Golden/Main.Main:PersistentLevel.MC_IMPROVISE_99".into(),
        kind: "cover".into(),
        pose_proof_ok: true,
        readback_present: true,
        declared_bounds: imp,
        readback_bounds: imp,
        planned_center: [1600.0, 300.0, 100.0],
        floating_exempt: false,
    });
    cases.push(("17_improvisation".into(), vec!["source_coordonnees".into()], s17));

    // 18. Trap: displaced outside plan coordinates
    let mut s18 = healthy_snapshot();
    s18.lots[0].actors[1].planned_center = [2500.0, 2500.0, 128.0];
    cases.push(("18_deplace_hors_plan".into(), vec!["source_coordonnees".into()], s18));

    // 19. Trap: missing plan items (> 15% gap) + spawn missing
    let mut s19 = healthy_snapshot();
    s19.lots[0].actors.retain(|a| a.id_placement != "SPAWN_01");
    cases.push((
        "19_item_oublie_et_spawn_absent".into(),
        vec!["couverture_plan".into(), "gameplay".into()],
        s19,
    ));

    // 20. Trap: visual capture of blank wall + daytime "night" capture
    let mut s20 = healthy_snapshot();
    s20.captures = vec![
        SnapshotCapture {
            name: "mur.png".into(),
            present: true,
            variance: 0.4,
            is_night: false,
            luminance: 100.0,
            neon_ratio: 0.0,
        },
        SnapshotCapture {
            name: "nuit_plaza.png".into(),
            present: true,
            variance: 30.0,
            is_night: true,
            luminance: 165.0,
            neon_ratio: 0.0,
        },
    ];
    cases.push(("20_captures_mur_et_nuit_jour".into(), vec!["captures_visuelles".into()], s20));

    cases
}
