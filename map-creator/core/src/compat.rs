use crate::config::{now_utc, write_atomic, RootPaths};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompatRow {
    pub tool: String,
    pub status: String, // OK | BROKEN | FORMAT_CHANGED | UNTESTED
    pub fixture: String,
    pub notes: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompatSummary {
    pub uefn_version_target: String,
    pub rows: Vec<CompatRow>,
    pub fixture_files: Vec<String>,
    pub counts: CompatCounts,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompatCounts {
    pub ok: usize,
    pub broken: usize,
    pub format_changed: usize,
    pub untested: usize,
}

pub struct CompatManager {
    paths: RootPaths,
}

impl CompatManager {
    pub fn new(paths: RootPaths) -> Self {
        Self { paths }
    }

    pub fn load_summary(&self) -> CompatSummary {
        let md_path = self.paths.compat_dir().join("COMPAT_STATUS.md");
        let raw = fs::read_to_string(&md_path).unwrap_or_default();
        let mut rows = Vec::new();
        let mut target = "39.10".to_string();

        for line in raw.lines() {
            let trimmed = line.trim();
            if let Some(rest) = trimmed.strip_prefix("Version UEFN ciblée :") {
                if let Some(v) = rest.split("**").nth(1) {
                    target = v.trim().to_string();
                }
            }
            if trimmed.starts_with('|') && !trimmed.contains("---") && !trimmed.contains("Capacité / Outil") {
                let cols: Vec<&str> = trimmed
                    .trim_matches('|')
                    .split('|')
                    .map(|c| c.trim())
                    .collect();
                if cols.len() >= 4 {
                    rows.push(CompatRow {
                        tool: cols[0].trim_matches('`').to_string(),
                        status: cols[1].to_string(),
                        fixture: cols[2].trim_matches('`').to_string(),
                        notes: cols[3].to_string(),
                    });
                }
            }
        }

        let mut fixture_files = Vec::new();
        if let Ok(entries) = fs::read_dir(self.paths.compat_dir().join("fixtures")) {
            for e in entries.flatten() {
                if let Some(name) = e.file_name().to_str() {
                    if name.ends_with(".json") {
                        fixture_files.push(name.to_string());
                    }
                }
            }
        }
        fixture_files.sort();

        let counts = CompatCounts {
            ok: rows.iter().filter(|r| r.status == "OK").count(),
            broken: rows.iter().filter(|r| r.status == "BROKEN").count(),
            format_changed: rows.iter().filter(|r| r.status == "FORMAT_CHANGED").count(),
            untested: rows.iter().filter(|r| r.status == "UNTESTED").count(),
        };

        CompatSummary {
            uefn_version_target: target,
            rows,
            fixture_files,
            counts,
        }
    }

    /// Ingests a raw JSON fixture captured by the PC Agent and updates COMPAT_STATUS.md.
    pub fn ingest_fixture(
        &self,
        tool: &str,
        status: &str,
        uefn_version: &str,
        notes: &str,
        raw_payload: Value,
    ) -> Result<CompatSummary, String> {
        if !matches!(status, "OK" | "BROKEN" | "FORMAT_CHANGED" | "UNTESTED") {
            return Err(format!("Statut compatibilité invalide : {status}"));
        }
        let safe_name = tool
            .replace('.', "_")
            .replace('/', "_")
            .to_lowercase();
        let rel_fixture = format!("fixtures/{safe_name}.json");
        let fixture_path = self.paths.compat_dir().join(&rel_fixture);
        let wrapper = serde_json::json!({
            "fixture": tool,
            "captured_at": now_utc(),
            "uefn_version": uefn_version,
            "tool": tool,
            "status": status,
            "payload": raw_payload
        });
        let fixture_bytes = serde_json::to_string_pretty(&wrapper).map_err(|e| e.to_string())?;
        write_atomic(&fixture_path, fixture_bytes.as_bytes())?;

        let mut summary = self.load_summary();
        summary.uefn_version_target = uefn_version.to_string();
        if let Some(existing) = summary.rows.iter_mut().find(|r| r.tool == tool) {
            existing.status = status.to_string();
            existing.fixture = rel_fixture;
            existing.notes = notes.to_string();
        } else {
            summary.rows.push(CompatRow {
                tool: tool.to_string(),
                status: status.to_string(),
                fixture: rel_fixture,
                notes: notes.to_string(),
            });
        }

        let mut md = format!(
            "# Statut de compatibilité UEFN (Agent PC ↔ Harnais)\n\nVersion UEFN ciblée : **{}** · Dernière synchronisation : **{}**\n\n| Capacité / Outil MCP | Statut | Preuve / Fixture | Notes terrain |\n| --- | --- | --- | --- |\n",
            summary.uefn_version_target,
            now_utc()
        );
        for r in &summary.rows {
            md.push_str(&format!(
                "| `{}` | {} | `{}` | {} |\n",
                r.tool, r.status, r.fixture, r.notes
            ));
        }
        write_atomic(&self.paths.compat_dir().join("COMPAT_STATUS.md"), md.as_bytes())?;
        Ok(self.load_summary())
    }
}
