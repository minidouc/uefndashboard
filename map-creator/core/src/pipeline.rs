use crate::config::{now_utc, write_atomic, RootPaths};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::PathBuf;

pub const MAX_STATE_BYTES: usize = 20_000;
pub const CAP_ITERATIONS: u32 = 15;

pub const PHASES: &[PhaseMeta] = &[
    PhaseMeta {
        id: "0_QUESTIONNAIRE",
        code: "0",
        label: "Questionnaire",
        stage: "sur_papier",
        required_gates: &[],
        requires_validation_exit: false,
    },
    PhaseMeta {
        id: "1_BRIEF",
        code: "1",
        label: "Brief",
        stage: "sur_papier",
        required_gates: &[],
        requires_validation_exit: false,
    },
    PhaseMeta {
        id: "2A_TEXTE",
        code: "2A",
        label: "Le jeu en texte + salle grise",
        stage: "sur_papier",
        required_gates: &["brief"],
        requires_validation_exit: false,
    },
    PhaseMeta {
        id: "2B_IMAGES",
        code: "2B",
        label: "Images du monde",
        stage: "sur_papier",
        required_gates: &["texte"],
        requires_validation_exit: false,
    },
    PhaseMeta {
        id: "3_GRAYBOX",
        code: "3",
        label: "Pose Graybox",
        stage: "en_gris",
        required_gates: &["conception", "ecriture_uefn"],
        requires_validation_exit: true,
    },
    PhaseMeta {
        id: "4_CORRECTIONS",
        code: "4",
        label: "Playtest & Corrections",
        stage: "en_gris",
        required_gates: &[],
        requires_validation_exit: false,
    },
    PhaseMeta {
        id: "2B_PLUS_PLANCHES",
        code: "2B+",
        label: "Planches de production",
        stage: "en_vrai",
        required_gates: &["gameplay"],
        requires_validation_exit: false,
    },
    PhaseMeta {
        id: "5_VRAIS_OBJETS",
        code: "5",
        label: "Vrais objets & Interface",
        stage: "en_vrai",
        required_gates: &["planches"],
        requires_validation_exit: true,
    },
    PhaseMeta {
        id: "6_VERIFICATION",
        code: "6",
        label: "Vérification (16 critères)",
        stage: "en_vrai",
        required_gates: &[],
        requires_validation_exit: true,
    },
    PhaseMeta {
        id: "7_FINITIONS",
        code: "7",
        label: "Finitions & Ambiance",
        stage: "en_vrai",
        required_gates: &["verification"],
        requires_validation_exit: true,
    },
    PhaseMeta {
        id: "8_OPTIMISATION",
        code: "8",
        label: "Optimisation Mémoire",
        stage: "en_vrai",
        required_gates: &[],
        requires_validation_exit: true,
    },
    PhaseMeta {
        id: "9_PUBLICATION",
        code: "9",
        label: "Publication",
        stage: "en_vrai",
        required_gates: &["publication"],
        requires_validation_exit: false,
    },
];

pub const NON_SACRIFIABLES: &[&str] = &[
    "validateurs",
    "jauge_ram",
    "relecture_bornes",
    "preexistants",
    "save_par_lot",
    "source_coordonnees",
    "trace",
    "rollback",
];

pub const SACRIFIABLES: &[&str] = &[
    "spike_T6",
    "captures_multiples",
    "critique_trajectoire",
    "critique_visuelle",
    "golden_selftest_par_lot",
    "questions_cadrage",
    "planches_2b_plus",
];

pub const KNOWN_GATES: &[&str] = &[
    "brief",
    "salle_grise",
    "texte",
    "conception",
    "ecriture_uefn",
    "gameplay",
    "planches",
    "verification",
    "publication",
    "derogation",
];

pub const VALID_PROVENANCES: &[&str] = &[
    "validator",
    "editor_readback",
    "human",
    "script",
    "agent_claim",
];

#[derive(Debug, Clone, Serialize)]
pub struct PhaseMeta {
    pub id: &'static str,
    pub code: &'static str,
    pub label: &'static str,
    pub stage: &'static str,
    pub required_gates: &'static [&'static str],
    pub requires_validation_exit: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GateRecord {
    pub ts_utc: String,
    pub citation: String,
    pub scope: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliverableLock {
    pub path: String,
    pub locked_at: String,
    pub sha256: String,
    pub human_citation: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChangeRequest {
    pub id: String,
    pub target_deliverable: String,
    pub reason: String,
    pub requested_at: String,
    pub approved: bool,
    pub human_citation: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DerogationRecord {
    pub ts_utc: String,
    pub sacrificed: Vec<String>,
    pub preserved: Vec<String>,
    pub citation: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateCounters {
    pub phase_iterations: u32,
    pub questions_total: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectState {
    #[serde(rename = "$schema")]
    pub schema: String,
    pub project_slug: String,
    pub title: String,
    pub phase: String,
    pub mode: String, // "production" | "prototype"
    pub updated_at: String,
    pub counters: StateCounters,
    pub gates: BTreeMap<String, GateRecord>,
    pub locks: BTreeMap<String, DeliverableLock>,
    pub change_requests: Vec<ChangeRequest>,
    pub lots: BTreeMap<String, String>,
    pub derogation: Option<DerogationRecord>,
    pub last_validation: Option<String>,
    pub next_action: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProvenanceEvent {
    pub ts_utc: String,
    pub provenance: String,
    pub message: String,
    pub proof: Option<String>,
    #[serde(default)]
    pub meta: Value,
}

pub struct PipelineStore {
    paths: RootPaths,
}

impl PipelineStore {
    pub fn new(paths: RootPaths) -> Self {
        Self { paths }
    }

    pub fn state_file(&self, slug: &str) -> PathBuf {
        self.paths.project_dir(slug).join("state/state.json")
    }

    pub fn events_file(&self, slug: &str) -> PathBuf {
        self.paths.project_dir(slug).join("state/events.jsonl")
    }

    pub fn list_projects(&self) -> Vec<String> {
        let dir = self.paths.projects_dir();
        let mut out = Vec::new();
        if let Ok(entries) = fs::read_dir(dir) {
            for e in entries.flatten() {
                if e.path().is_dir() && e.path().join("state/state.json").exists() {
                    if let Some(name) = e.file_name().to_str() {
                        out.push(name.to_string());
                    }
                }
            }
        }
        out.sort();
        out
    }

    pub fn create_project(
        &self,
        slug: &str,
        title: &str,
        mode: &str,
    ) -> Result<ProjectState, String> {
        if !slug
            .chars()
            .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '-')
            || slug.is_empty()
        {
            return Err("Slug invalide : utiliser uniquement minuscules, chiffres et tirets".into());
        }
        let pdir = self.paths.project_dir(slug);
        if pdir.join("state/state.json").exists() {
            return Err(format!("Le projet '{slug}' existe déjà"));
        }
        for sub in [
            "state",
            "deliverables",
            "plans",
            "outbox/pending",
            "outbox/sent",
            "outbox/responses",
            "outbox/validated",
            "outbox/failed",
            "qa/validation",
            "captures",
        ] {
            fs::create_dir_all(pdir.join(sub))
                .map_err(|e| format!("Création dossier {sub} impossible: {e}"))?;
        }
        let state = ProjectState {
            schema: "map-creator.state.v3".to_string(),
            project_slug: slug.to_string(),
            title: title.to_string(),
            phase: "0_QUESTIONNAIRE".to_string(),
            mode: if mode == "prototype" {
                "prototype".to_string()
            } else {
                "production".to_string()
            },
            updated_at: now_utc(),
            counters: StateCounters {
                phase_iterations: 0,
                questions_total: 0,
            },
            gates: BTreeMap::new(),
            locks: BTreeMap::new(),
            change_requests: Vec::new(),
            lots: BTreeMap::new(),
            derogation: None,
            last_validation: None,
            next_action: Some("Remplir le questionnaire de Phase 0".to_string()),
        };
        self.save_state(slug, &state)?;
        self.append_event(
            slug,
            "script",
            &format!("Projet '{slug}' initialisé en phase 0_QUESTIONNAIRE (mode={})", state.mode),
            None,
            Value::Null,
        )?;
        Ok(state)
    }

    pub fn load_state(&self, slug: &str) -> Result<(ProjectState, usize), String> {
        let path = self.state_file(slug);
        let raw = fs::read_to_string(&path)
            .map_err(|e| format!("État projet introuvable ({}): {e}", path.display()))?;
        let bytes = raw.len();
        let state: ProjectState = serde_json::from_str(&raw)
            .map_err(|e| format!("JSON state.json invalide: {e}"))?;
        Ok((state, bytes))
    }

    pub fn save_state(&self, slug: &str, state: &ProjectState) -> Result<usize, String> {
        let mut s = state.clone();
        s.updated_at = now_utc();
        let raw = serde_json::to_string_pretty(&s)
            .map_err(|e| format!("Erreur sérialisation state.json: {e}"))?;
        if raw.len() > MAX_STATE_BYTES {
            return Err(format!(
                "STATE_TOO_LARGE ({} o > {} o) : déplacer le détail dans events.jsonl",
                raw.len(),
                MAX_STATE_BYTES
            ));
        }
        write_atomic(&self.state_file(slug), raw.as_bytes())?;
        Ok(raw.len())
    }

    pub fn append_event(
        &self,
        slug: &str,
        provenance: &str,
        message: &str,
        proof: Option<String>,
        meta: Value,
    ) -> Result<ProvenanceEvent, String> {
        if !VALID_PROVENANCES.contains(&provenance) {
            return Err(format!(
                "Provenance inconnue '{provenance}' (attendu: {:?})",
                VALID_PROVENANCES
            ));
        }
        let evt = ProvenanceEvent {
            ts_utc: now_utc(),
            provenance: provenance.to_string(),
            message: message.to_string(),
            proof,
            meta,
        };
        let path = self.events_file(slug);
        if let Some(p) = path.parent() {
            fs::create_dir_all(p).map_err(|e| format!("Création state/ impossible: {e}"))?;
        }
        let mut f = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .map_err(|e| format!("Ouverture events.jsonl impossible: {e}"))?;
        let line = serde_json::to_string(&evt).map_err(|e| e.to_string())?;
        writeln!(f, "{line}").map_err(|e| format!("Écriture events.jsonl impossible: {e}"))?;
        Ok(evt)
    }

    pub fn tail_events(
        &self,
        slug: &str,
        limit: usize,
        provenance_filter: Option<&str>,
    ) -> Vec<ProvenanceEvent> {
        let path = self.events_file(slug);
        let Ok(raw) = fs::read_to_string(path) else {
            return Vec::new();
        };
        let mut events: Vec<ProvenanceEvent> = raw
            .lines()
            .filter_map(|l| serde_json::from_str::<ProvenanceEvent>(l).ok())
            .filter(|e| match provenance_filter {
                Some(f) if !f.is_empty() && f != "all" => e.provenance == f,
                _ => true,
            })
            .collect();
        if events.len() > limit {
            events = events.split_off(events.len() - limit);
        }
        events.reverse();
        events
    }

    pub fn approve_gate(
        &self,
        slug: &str,
        gate: &str,
        citation: &str,
        scope: Option<String>,
    ) -> Result<ProjectState, String> {
        if !KNOWN_GATES.contains(&gate) {
            return Err(format!("Porte inconnue '{gate}' (connues: {:?})", KNOWN_GATES));
        }
        if citation.trim().len() < 3 {
            return Err(
                "GATE_REFUSED : la citation exacte de l'utilisateur (min 3 caractères) est obligatoire"
                    .into(),
            );
        }
        let (mut state, _) = self.load_state(slug)?;
        state.gates.insert(
            gate.to_string(),
            GateRecord {
                ts_utc: now_utc(),
                citation: citation.trim().to_string(),
                scope: scope.clone(),
            },
        );
        self.save_state(slug, &state)?;
        self.append_event(
            slug,
            "human",
            &format!("Porte '{gate}' validée par l'auteur"),
            None,
            serde_json::json!({ "gate": gate, "citation": citation.trim(), "scope": scope }),
        )?;
        Ok(state)
    }

    pub fn advance_phase(&self, slug: &str, target_phase: &str) -> Result<ProjectState, String> {
        let (mut state, _) = self.load_state(slug)?;
        let cur_idx = phase_index(&state.phase)
            .ok_or_else(|| format!("Phase courante invalide: {}", state.phase))?;
        let dst_idx = phase_index(target_phase)
            .ok_or_else(|| format!("Phase cible inconnue: {target_phase}"))?;

        if dst_idx == cur_idx {
            return Ok(state);
        }

        // Loop 3 <-> 4 is always permitted; moving backwards is always permitted for corrections
        if dst_idx > cur_idx + 1 {
            // In prototype mode, allow jumping over 2B_IMAGES or 2B_PLUS_PLANCHES only
            let is_proto_skip = state.mode == "prototype"
                && ((state.phase == "2A_TEXTE" && target_phase == "3_GRAYBOX")
                    || (state.phase == "4_CORRECTIONS" && target_phase == "5_VRAIS_OBJETS"));
            if !is_proto_skip {
                return Err(format!(
                    "PHASE_REFUSED : impossible de sauter de '{}' directement vers '{}'",
                    state.phase, target_phase
                ));
            }
        }

        if dst_idx > cur_idx {
            let dst_meta = &PHASES[dst_idx];
            let mut missing = Vec::new();
            for g in dst_meta.required_gates {
                // In prototype mode, "conception" and "planches" gates are optional
                if state.mode == "prototype" && (*g == "conception" || *g == "planches") {
                    continue;
                }
                if !state.gates.contains_key(*g) {
                    missing.push(*g);
                }
            }
            if !missing.is_empty() {
                return Err(format!(
                    "PHASE_REFUSED : portes humaines manquantes pour '{}' : {:?}",
                    target_phase, missing
                ));
            }

            let cur_meta = &PHASES[cur_idx];
            if cur_meta.requires_validation_exit {
                let latest_path = self
                    .paths
                    .project_dir(slug)
                    .join("qa/validation/latest.json");
                let raw = fs::read_to_string(&latest_path).map_err(|_| {
                    format!(
                        "PHASE_REFUSED : rapport de validation PASS requis pour quitter '{}'",
                        state.phase
                    )
                })?;
                let report: Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
                if report.get("verdict").and_then(Value::as_str) != Some("PASS")
                    || report.get("manifest_integrity").and_then(Value::as_str) != Some("OK")
                {
                    return Err(format!(
                        "PHASE_REFUSED : le dernier rapport de validation n'est pas PASS ou les validateurs sont altérés"
                    ));
                }
            }
        }

        let prev = state.phase.clone();
        state.phase = target_phase.to_string();
        state.counters.phase_iterations = 0;
        self.save_state(slug, &state)?;
        self.append_event(
            slug,
            "script",
            &format!("Transition de phase : {prev} -> {target_phase}"),
            None,
            serde_json::json!({ "from": prev, "to": target_phase }),
        )?;
        Ok(state)
    }

    pub fn set_mode(&self, slug: &str, mode: &str) -> Result<ProjectState, String> {
        if mode != "production" && mode != "prototype" {
            return Err("Mode invalide : attendu 'production' ou 'prototype'".into());
        }
        let (mut state, _) = self.load_state(slug)?;
        state.mode = mode.to_string();
        self.save_state(slug, &state)?;
        self.append_event(
            slug,
            "human",
            &format!("Mode pipeline basculé sur '{mode}' (invariants préservés)"),
            None,
            serde_json::json!({ "mode": mode }),
        )?;
        Ok(state)
    }

    pub fn lock_deliverable(
        &self,
        slug: &str,
        rel_path: &str,
        citation: &str,
    ) -> Result<ProjectState, String> {
        if citation.trim().len() < 3 {
            return Err("Citation humaine obligatoire pour verrouiller un livrable".into());
        }
        let abs = self.paths.project_dir(slug).join(rel_path);
        let bytes = fs::read(&abs)
            .map_err(|e| format!("Livrable introuvable ({}): {e}", abs.display()))?;
        let digest = sha256_hex(&bytes);
        let (mut state, _) = self.load_state(slug)?;
        state.locks.insert(
            rel_path.to_string(),
            DeliverableLock {
                path: rel_path.to_string(),
                locked_at: now_utc(),
                sha256: digest.clone(),
                human_citation: citation.trim().to_string(),
            },
        );
        self.save_state(slug, &state)?;
        self.append_event(
            slug,
            "human",
            &format!("Livrable verrouillé : {rel_path}"),
            Some(rel_path.to_string()),
            serde_json::json!({ "sha256": digest, "citation": citation.trim() }),
        )?;
        Ok(state)
    }

    pub fn request_change(
        &self,
        slug: &str,
        target: &str,
        reason: &str,
        approve_citation: Option<&str>,
    ) -> Result<ProjectState, String> {
        let (mut state, _) = self.load_state(slug)?;
        let approved = approve_citation
            .map(|c| c.trim().len() >= 3)
            .unwrap_or(false);
        let cr_id = format!("CR-{:02}", state.change_requests.len() + 1);
        state.change_requests.push(ChangeRequest {
            id: cr_id.clone(),
            target_deliverable: target.to_string(),
            reason: reason.to_string(),
            requested_at: now_utc(),
            approved,
            human_citation: approve_citation.map(|c| c.trim().to_string()),
        });
        if approved {
            state.locks.remove(target);
        }
        self.save_state(slug, &state)?;
        self.append_event(
            slug,
            if approved { "human" } else { "script" },
            &format!(
                "Demande de changement {cr_id} sur '{target}' ({})",
                if approved { "approuvée, verrou levé" } else { "ouverte" }
            ),
            None,
            serde_json::json!({ "id": cr_id, "target": target, "reason": reason, "approved": approved }),
        )?;
        Ok(state)
    }

    pub fn record_derogation(
        &self,
        slug: &str,
        sacrificed: Vec<String>,
        citation: &str,
    ) -> Result<ProjectState, String> {
        if citation.trim().len() < 3 {
            return Err("DEROGATION_REFUSED : citation humaine obligatoire".into());
        }
        let non_sac: BTreeSet<&str> = NON_SACRIFIABLES.iter().copied().collect();
        let sac_ok: BTreeSet<&str> = SACRIFIABLES.iter().copied().collect();
        for item in &sacrificed {
            if non_sac.contains(item.as_str()) {
                return Err(format!(
                    "DEROGATION_REFUSED : '{item}' est NON SACRIFIABLE (invariant de preuve)"
                ));
            }
            if !sac_ok.contains(item.as_str()) {
                return Err(format!(
                    "DEROGATION_REFUSED : contrôle inconnu '{item}' (sacrifiables: {:?})",
                    SACRIFIABLES
                ));
            }
        }
        let (mut state, _) = self.load_state(slug)?;
        let record = DerogationRecord {
            ts_utc: now_utc(),
            sacrificed: sacrificed.clone(),
            preserved: NON_SACRIFIABLES.iter().map(|s| s.to_string()).collect(),
            citation: citation.trim().to_string(),
        };
        state.derogation = Some(record);
        state.gates.insert(
            "derogation".to_string(),
            GateRecord {
                ts_utc: now_utc(),
                citation: citation.trim().to_string(),
                scope: Some(sacrificed.join(",")),
            },
        );
        self.save_state(slug, &state)?;
        self.append_event(
            slug,
            "human",
            &format!("Dérogation enregistrée : sacrifié={:?}", sacrificed),
            None,
            serde_json::json!({ "sacrificed": sacrificed, "citation": citation.trim() }),
        )?;
        Ok(state)
    }
}

pub fn phase_index(id: &str) -> Option<usize> {
    PHASES.iter().position(|p| p.id == id)
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    let mut h = Sha256::new();
    h.update(bytes);
    hex::encode(h.finalize())
}
