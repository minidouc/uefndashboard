use crate::config::{write_atomic, RootPaths};
use serde::{Deserialize, Serialize};
use std::collections::{HashSet, VecDeque};
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DistrictGrid {
    pub tile_size_uu: f64,
    pub floor_height_uu: f64,
    pub tiles_x: u32,
    pub tiles_y: u32,
    pub origin_uu: [f64; 3],
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DistrictConnector {
    pub id: String,
    pub target_district: String,
    pub tile_x: f64,
    pub tile_y: f64,
    pub width_tiles: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlanItem {
    pub id: String,
    pub label: String,
    pub kind: String,
    pub pass: String, // "reel" | "jouable" | "admirable"
    pub reason: String,
    pub tile_x: f64,
    pub tile_y: f64,
    pub floor_z: f64,
    pub size_tiles_x: f64,
    pub size_tiles_y: f64,
    pub height_floors: f64,
    #[serde(default)]
    pub yaw_deg: f64,
    #[serde(default = "default_asset")]
    pub asset_ref: String,
    #[serde(default = "default_mem")]
    pub estimated_memory_kb: u32,
    #[serde(default)]
    pub floating_exempt: bool,
}

fn default_asset() -> String {
    "GRAYBOX:CUBE".to_string()
}
fn default_mem() -> u32 {
    12
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct DistrictLayers {
    pub a_scene: Vec<PlanItem>,
    pub b_fonds: Vec<PlanItem>,
    pub c_details: Vec<PlanItem>,
    pub d_effets: Vec<PlanItem>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SectionElevation {
    pub label: String,
    pub start_tile: f64,
    pub end_tile: f64,
    pub floor_z: f64,
    pub height_floors: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SectionView {
    pub axis: String,
    pub slice_tile: f64,
    pub elevations: Vec<SectionElevation>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OverlapException {
    pub a: String,
    pub b: String,
    pub justification: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DistrictPlan {
    pub district_id: String,
    pub name: String,
    #[serde(default)]
    pub role: String,
    pub grid: DistrictGrid,
    pub memory_budget_kb: u32,
    #[serde(default)]
    pub connectors: Vec<DistrictConnector>,
    pub layers: DistrictLayers,
    pub section_view: SectionView,
    #[serde(default)]
    pub overlap_exceptions: Vec<OverlapException>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct AabbCm {
    pub min: [f64; 3],
    pub max: [f64; 3],
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlanIssue {
    pub severity: String, // "error" | "warning"
    pub rule: String,
    pub item_id: Option<String>,
    pub detail: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlanCheckReport {
    pub district_id: String,
    pub verdict: String, // "PASS" | "FAIL"
    pub total_items: usize,
    pub counts_by_layer: [usize; 4],
    pub estimated_memory_kb: u32,
    pub memory_budget_kb: u32,
    pub issues: Vec<PlanIssue>,
}

impl PlanItem {
    /// Convert grid coordinates to UEFN world coordinates (centimeters / uu).
    /// Respects Lesson #12: thin surfaces expand downward, objects expand upward.
    pub fn bounds_cm(&self, grid: &DistrictGrid) -> AabbCm {
        let min_x = grid.origin_uu[0] + self.tile_x * grid.tile_size_uu;
        let min_y = grid.origin_uu[1] + self.tile_y * grid.tile_size_uu;
        let max_x = min_x + self.size_tiles_x * grid.tile_size_uu;
        let max_y = min_y + self.size_tiles_y * grid.tile_size_uu;

        let base_z = grid.origin_uu[2] + self.floor_z * grid.floor_height_uu;
        let raw_h = self.height_floors * grid.floor_height_uu;
        let (min_z, max_z) = if self.kind == "surface" {
            let h = raw_h.max(256.0);
            (base_z - h, base_z)
        } else {
            let h = raw_h.max(64.0);
            (base_z, base_z + h)
        };

        AabbCm {
            min: [min_x, min_y, min_z],
            max: [max_x, max_y, max_z],
        }
    }
}

impl DistrictPlan {
    pub fn all_items_with_layer(&self) -> Vec<(&'static str, &PlanItem)> {
        let mut out = Vec::new();
        for it in &self.layers.a_scene {
            out.push(("a_scene", it));
        }
        for it in &self.layers.b_fonds {
            out.push(("b_fonds", it));
        }
        for it in &self.layers.c_details {
            out.push(("c_details", it));
        }
        for it in &self.layers.d_effets {
            out.push(("d_effets", it));
        }
        out
    }
}

pub struct PlannerEngine {
    paths: RootPaths,
}

impl PlannerEngine {
    pub fn new(paths: RootPaths) -> Self {
        Self { paths }
    }

    pub fn plans_dir(&self, slug: &str) -> PathBuf {
        self.paths.project_dir(slug).join("plans")
    }

    pub fn list_plans(&self, slug: &str) -> Vec<String> {
        let mut out = Vec::new();
        if let Ok(entries) = fs::read_dir(self.plans_dir(slug)) {
            for e in entries.flatten() {
                let p = e.path();
                if p.extension().and_then(|s| s.to_str()) == Some("json") {
                    if let Some(stem) = p.file_stem().and_then(|s| s.to_str()) {
                        out.push(stem.to_string());
                    }
                }
            }
        }
        out.sort();
        out
    }

    pub fn load_plan(&self, slug: &str, district_id: &str) -> Result<DistrictPlan, String> {
        let p = self.plans_dir(slug).join(format!("{district_id}.json"));
        let raw = fs::read_to_string(&p)
            .map_err(|e| format!("Plan introuvable ({}): {e}", p.display()))?;
        serde_json::from_str(&raw).map_err(|e| format!("JSON plan invalide: {e}"))
    }

    pub fn save_plan(&self, slug: &str, plan: &DistrictPlan) -> Result<(), String> {
        let p = self
            .plans_dir(slug)
            .join(format!("{}.json", plan.district_id));
        let raw = serde_json::to_string_pretty(plan).map_err(|e| e.to_string())?;
        write_atomic(&p, raw.as_bytes())
    }

    pub fn upsert_item(
        &self,
        slug: &str,
        district_id: &str,
        layer: &str,
        item: PlanItem,
    ) -> Result<DistrictPlan, String> {
        let mut plan = self.load_plan(slug, district_id)?;
        let vec = match layer {
            "a_scene" => &mut plan.layers.a_scene,
            "b_fonds" => &mut plan.layers.b_fonds,
            "c_details" => &mut plan.layers.c_details,
            "d_effets" => &mut plan.layers.d_effets,
            _ => return Err(format!("Couche inconnue '{layer}'")),
        };
        if let Some(pos) = vec.iter().position(|x| x.id == item.id) {
            vec[pos] = item;
        } else {
            vec.push(item);
        }
        self.save_plan(slug, &plan)?;
        Ok(plan)
    }

    /// Runs full pre-editor geometry, design-reason, accessibility, and memory checks.
    pub fn check_plan(&self, plan: &DistrictPlan) -> PlanCheckReport {
        let items = plan.all_items_with_layer();
        let mut issues = Vec::new();
        let eps = 10.0;
        let mut seen_ids = HashSet::new();
        let mut total_mem: u32 = 0;

        for (layer, it) in &items {
            total_mem += it.estimated_memory_kb;
            if !seen_ids.insert(it.id.clone()) {
                issues.push(PlanIssue {
                    severity: "error".into(),
                    rule: "unique_id".into(),
                    item_id: Some(it.id.clone()),
                    detail: format!("Identifiant dupliqué '{}'", it.id),
                });
            }
            if it.reason.trim().len() < 5 {
                issues.push(PlanIssue {
                    severity: "error".into(),
                    rule: "reason_required".into(),
                    item_id: Some(it.id.clone()),
                    detail: format!("Objet '{}' sans raison explicite (couche {layer})", it.id),
                });
            }
            if it.tile_x < 0.0
                || it.tile_y < 0.0
                || it.tile_x + it.size_tiles_x > plan.grid.tiles_x as f64 + 0.01
                || it.tile_y + it.size_tiles_y > plan.grid.tiles_y as f64 + 0.01
            {
                if *layer != "b_fonds" {
                    issues.push(PlanIssue {
                        severity: "error".into(),
                        rule: "grid_bounds".into(),
                        item_id: Some(it.id.clone()),
                        detail: format!(
                            "'{}' dépasse les bornes du quartier ({}x{} tuiles)",
                            it.id, plan.grid.tiles_x, plan.grid.tiles_y
                        ),
                    });
                }
            }
        }

        // Memory budget check
        if total_mem > plan.memory_budget_kb {
            issues.push(PlanIssue {
                severity: "error".into(),
                rule: "memory_budget".into(),
                item_id: None,
                detail: format!(
                    "Budget mémoire dépassé : {} Ko > {} Ko",
                    total_mem, plan.memory_budget_kb
                ),
            });
        }

        // Check spawn presence in layer a_scene
        let has_spawn = plan.layers.a_scene.iter().any(|it| it.kind == "spawn");
        if !has_spawn {
            issues.push(PlanIssue {
                severity: "error".into(),
                rule: "spawn_required".into(),
                item_id: None,
                detail: "Aucun point d'apparition (kind='spawn') dans la couche a_scene".into(),
            });
        }

        // Physical items (exclude non-colliding VFX/audio/lights from strict solid overlap)
        let solids: Vec<(&PlanItem, AabbCm)> = items
            .iter()
            .filter(|(_, it)| !matches!(it.kind.as_str(), "light" | "vfx" | "audio_zone"))
            .map(|(_, it)| (*it, it.bounds_cm(&plan.grid)))
            .collect();

        // Overlap check
        for i in 0..solids.len() {
            for j in (i + 1)..solids.len() {
                let (ai, bi) = &solids[i];
                let (aj, bj) = &solids[j];
                if strict_overlap(bi, bj, eps) {
                    let excused = plan.overlap_exceptions.iter().any(|ex| {
                        !ex.justification.trim().is_empty()
                            && ((ex.a == ai.id && ex.b == aj.id)
                                || (ex.b == ai.id && ex.a == aj.id))
                    });
                    if !excused {
                        issues.push(PlanIssue {
                            severity: "error".into(),
                            rule: "zero_overlap".into(),
                            item_id: Some(aj.id.clone()),
                            detail: format!(
                                "Chevauchement non justifié entre '{}' et '{}'",
                                ai.id, aj.id
                            ),
                        });
                    }
                }
            }
        }

        // Floating check via BFS contact graph to ground (z <= origin_z + eps)
        let ground_z = plan.grid.origin_uu[2];
        let mut anchored = HashSet::new();
        let mut queue = VecDeque::new();
        for (idx, (it, b)) in solids.iter().enumerate() {
            if it.floating_exempt || it.kind == "surface" || b.min[2] <= ground_z + eps {
                anchored.insert(idx);
                queue.push_back(idx);
            }
        }
        while let Some(i) = queue.pop_front() {
            let (_, bi) = &solids[i];
            for j in 0..solids.len() {
                if !anchored.contains(&j) && touches(bi, &solids[j].1, eps) {
                    anchored.insert(j);
                    queue.push_back(j);
                }
            }
        }
        for (idx, (it, b)) in solids.iter().enumerate() {
            if !anchored.contains(&idx) && !it.floating_exempt {
                issues.push(PlanIssue {
                    severity: "error".into(),
                    rule: "zero_flottant".into(),
                    item_id: Some(it.id.clone()),
                    detail: format!(
                        "'{}' flotte à z_min={:.0} uu sans contact jusqu'au sol",
                        it.id, b.min[2]
                    ),
                });
            }
        }

        // Accessibility check: walkable surfaces should be reachable from spawn surface
        let surfaces: Vec<(&PlanItem, AabbCm)> = plan
            .layers
            .a_scene
            .iter()
            .filter(|it| matches!(it.kind.as_str(), "surface" | "ramp"))
            .map(|it| (it, it.bounds_cm(&plan.grid)))
            .collect();
        if surfaces.len() > 1 {
            let mut visited = HashSet::new();
            let mut q = VecDeque::new();
            visited.insert(0usize);
            q.push_back(0usize);
            while let Some(i) = q.pop_front() {
                let (_, bi) = &surfaces[i];
                for j in 0..surfaces.len() {
                    if visited.contains(&j) {
                        continue;
                    }
                    let (sj, bj) = &surfaces[j];
                    let xy_gap = horizontal_gap(bi, bj);
                    let z_diff = (bi.max[2] - bj.max[2]).abs();
                    let is_ramp = surfaces[i].0.kind == "ramp" || sj.kind == "ramp";
                    if xy_gap <= 200.0 && (z_diff <= 120.0 || is_ramp) {
                        visited.insert(j);
                        q.push_back(j);
                    }
                }
            }
            for (idx, (s, _)) in surfaces.iter().enumerate() {
                if !visited.contains(&idx) {
                    issues.push(PlanIssue {
                        severity: "warning".into(),
                        rule: "accessibilite".into(),
                        item_id: Some(s.id.clone()),
                        detail: format!(
                            "Surface '{}' potentiellement inaccessible (>120 uu de marche sans rampe)",
                            s.id
                        ),
                    });
                }
            }
        }

        let has_error = issues.iter().any(|i| i.severity == "error");
        PlanCheckReport {
            district_id: plan.district_id.clone(),
            verdict: if has_error { "FAIL" } else { "PASS" }.to_string(),
            total_items: items.len(),
            counts_by_layer: [
                plan.layers.a_scene.len(),
                plan.layers.b_fonds.len(),
                plan.layers.c_details.len(),
                plan.layers.d_effets.len(),
            ],
            estimated_memory_kb: total_mem,
            memory_budget_kb: plan.memory_budget_kb,
            issues,
        }
    }

    /// Generates a crisp architectural SVG of the 2D plan and its elevation section.
    pub fn render_svg(&self, plan: &DistrictPlan, visible_layers: &[String]) -> (String, String) {
        let cell = 28.0_f64;
        let pad = 44.0_f64;
        let w = plan.grid.tiles_x as f64 * cell + pad * 2.0;
        let h = plan.grid.tiles_y as f64 * cell + pad * 2.0;
        let show = |l: &str| visible_layers.is_empty() || visible_layers.iter().any(|x| x == l);

        let mut svg = format!(
            r#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" class="mc-blueprint-svg">"#
        );
        svg.push_str(r##"<rect width="100%" height="100%" fill="#FAF8F4"/>"##);

        // Subtle architectural grid
        for x in 0..=plan.grid.tiles_x {
            let px = pad + x as f64 * cell;
            let stroke = if x % 4 == 0 { "#D3CCC0" } else { "#ECE7DD" };
            svg.push_str(&format!(
                r#"<line x1="{px}" y1="{pad}" x2="{px}" y2="{}" stroke="{stroke}" stroke-width="1"/>"#,
                h - pad
            ));
            if x % 4 == 0 {
                svg.push_str(&format!(
                    r##"<text x="{px}" y="{}" font-size="10" fill="#777" text-anchor="middle" font-family="monospace">{x}</text>"##,
                    pad - 10.0
                ));
            }
        }
        for y in 0..=plan.grid.tiles_y {
            let py = pad + y as f64 * cell;
            let stroke = if y % 4 == 0 { "#D3CCC0" } else { "#ECE7DD" };
            svg.push_str(&format!(
                r#"<line x1="{pad}" y1="{py}" x2="{}" y2="{py}" stroke="{stroke}" stroke-width="1"/>"#,
                w - pad
            ));
            if y % 4 == 0 {
                svg.push_str(&format!(
                    r##"<text x="{}" y="{}" font-size="10" fill="#777" text-anchor="end" font-family="monospace">{y}</text>"##,
                    pad - 8.0,
                    py + 3.0
                ));
            }
        }

        // Draw layers in painter's order: b_fonds -> a_scene -> c_details -> d_effets
        let ordered: [(&str, &Vec<PlanItem>, &str, &str); 4] = [
            ("b_fonds", &plan.layers.b_fonds, "rgba(108,117,125,0.22)", "#6C757D"),
            ("a_scene", &plan.layers.a_scene, "rgba(30,96,145,0.20)", "#1E6091"),
            ("c_details", &plan.layers.c_details, "rgba(217,119,6,0.25)", "#D97706"),
            ("d_effets", &plan.layers.d_effets, "rgba(15,118,110,0.22)", "#0F766E"),
        ];

        for (layer_id, list, fill, stroke) in ordered {
            if !show(layer_id) {
                continue;
            }
            for it in list {
                let x = pad + it.tile_x * cell;
                let y = pad + it.tile_y * cell;
                let rw = (it.size_tiles_x * cell).max(10.0);
                let rh = (it.size_tiles_y * cell).max(10.0);
                let dash = if layer_id == "d_effets" {
                    r#" stroke-dasharray="4 3""#
                } else {
                    ""
                };
                svg.push_str(&format!(
                    r##"<g data-item-id="{}" data-layer="{layer_id}"><rect x="{x}" y="{y}" width="{rw}" height="{rh}" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.6"{dash}/><text x="{}" y="{}" font-size="10" fill="#17191C" font-family="sans-serif" font-weight="600">{}</text></g>"##,
                    escape_xml(&it.id),
                    x + 4.0,
                    y + 13.0,
                    escape_xml(&it.label)
                ));
            }
        }

        // Section slice guide line
        let slice_y = pad + plan.section_view.slice_tile * cell;
        svg.push_str(&format!(
            r##"<line x1="{pad}" y1="{slice_y}" x2="{}" y2="{slice_y}" stroke="#C84B28" stroke-width="1.5" stroke-dasharray="6 4"/>"##,
            w - pad
        ));
        svg.push_str(&format!(
            r##"<text x="{}" y="{}" font-size="10" fill="#C84B28" font-family="monospace">COUPE A-A'</text>"##,
            pad + 4.0,
            slice_y - 4.0
        ));
        svg.push_str("</svg>");

        // Elevation / Section SVG
        let sw = plan.grid.tiles_x as f64 * cell + pad * 2.0;
        let sh = 240.0_f64;
        let ground_y = sh - 46.0;
        let floor_px = 34.0;
        let mut sec = format!(
            r#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {sw} {sh}" width="{sw}" height="{sh}" class="mc-section-svg">"#
        );
        sec.push_str(r##"<rect width="100%" height="100%" fill="#FAF8F4"/>"##);
        sec.push_str(&format!(
            r##"<line x1="{pad}" y1="{ground_y}" x2="{}" y2="{ground_y}" stroke="#17191C" stroke-width="2"/>"##,
            sw - pad
        ));
        for f in 0..=4 {
            let fy = ground_y - f as f64 * floor_px;
            sec.push_str(&format!(
                r##"<line x1="{pad}" y1="{fy}" x2="{}" y2="{fy}" stroke="#E5DFD5" stroke-width="1"/>"##,
                sw - pad
            ));
            sec.push_str(&format!(
                r##"<text x="{}" y="{}" font-size="10" fill="#777" text-anchor="end" font-family="monospace">+{f}F</text>"##,
                pad - 8.0,
                fy + 3.0
            ));
        }
        for el in &plan.section_view.elevations {
            let x = pad + el.start_tile * cell;
            let rw = ((el.end_tile - el.start_tile) * cell).max(16.0);
            let rh = (el.height_floors * floor_px).max(12.0);
            let y = ground_y - (el.floor_z + el.height_floors) * floor_px;
            sec.push_str(&format!(
                r##"<rect x="{x}" y="{y}" width="{rw}" height="{rh}" rx="2" fill="rgba(200,75,40,0.18)" stroke="#C84B28" stroke-width="1.5"/><text x="{}" y="{}" font-size="10" fill="#17191C" font-family="sans-serif">{}</text>"##,
                x + 4.0,
                y + 13.0,
                escape_xml(&el.label)
            ));
        }
        sec.push_str("</svg>");
        (svg, sec)
    }
}

pub fn strict_overlap(a: &AabbCm, b: &AabbCm, eps: f64) -> bool {
    (a.min[0] + eps < b.max[0] && b.min[0] + eps < a.max[0])
        && (a.min[1] + eps < b.max[1] && b.min[1] + eps < a.max[1])
        && (a.min[2] + eps < b.max[2] && b.min[2] + eps < a.max[2])
}

pub fn touches(a: &AabbCm, b: &AabbCm, eps: f64) -> bool {
    (a.min[0] - eps <= b.max[0] && b.min[0] - eps <= a.max[0])
        && (a.min[1] - eps <= b.max[1] && b.min[1] - eps <= a.max[1])
        && (a.min[2] - eps <= b.max[2] && b.min[2] - eps <= a.max[2])
}

fn horizontal_gap(a: &AabbCm, b: &AabbCm) -> f64 {
    let dx = (a.min[0] - b.max[0]).max(b.min[0] - a.max[0]).max(0.0);
    let dy = (a.min[1] - b.max[1]).max(b.min[1] - a.max[1]).max(0.0);
    dx.hypot(dy)
}

fn escape_xml(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}
