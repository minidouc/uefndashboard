use crate::config::{now_utc, write_atomic, RootPaths};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

pub const ALLOWED_LIBRARY_PROVENANCE: &[&str] = &["validator", "editor_readback", "human"];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LessonEntry {
    pub id: String,
    pub rule: String,
    pub incident: String,
    pub provenance: String,
    pub added_at: String,
    pub active: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LessonsFile {
    pub updated_at: String,
    pub lessons: Vec<LessonEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LibraryEntry {
    pub id: String,
    pub category: String, // 3d_asset | verse_module | plan_snippet | image_prompt | device_config | model_benchmark
    pub title: String,
    pub summary: String,
    pub tags: Vec<String>,
    pub provenance: String, // validator | editor_readback | human
    pub proof_ref: String,
    pub source_project: String,
    pub created_at: String,
    pub uefn_version: String,
    pub license: String,
    pub memory_kb: Option<u32>,
    pub status: String, // verified | suspect | retired
    pub artifact_path: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LibraryIndex {
    pub updated_at: String,
    pub entries: Vec<LibraryEntry>,
}

pub struct MemoryStore {
    paths: RootPaths,
}

impl MemoryStore {
    pub fn new(paths: RootPaths) -> Self {
        Self { paths }
    }

    pub fn lessons_path(&self) -> PathBuf {
        self.paths.workspace_dir().join("lessons.json")
    }

    pub fn library_index_path(&self) -> PathBuf {
        self.paths.workspace_dir().join("library/index.json")
    }

    pub fn load_lessons(&self) -> LessonsFile {
        fs::read_to_string(self.lessons_path())
            .ok()
            .and_then(|raw| serde_json::from_str(&raw).ok())
            .unwrap_or_else(|| LessonsFile {
                updated_at: now_utc(),
                lessons: Vec::new(),
            })
    }

    pub fn add_lesson(
        &self,
        rule: &str,
        incident: &str,
        provenance: &str,
    ) -> Result<LessonEntry, String> {
        if !ALLOWED_LIBRARY_PROVENANCE.contains(&provenance) {
            return Err(format!(
                "PROVENANCE_REFUSED : une leçon exige une provenance probante ({:?}), jamais '{provenance}'",
                ALLOWED_LIBRARY_PROVENANCE
            ));
        }
        if rule.trim().len() < 8 || incident.trim().len() < 4 {
            return Err("Règle et incident obligatoires pour enregistrer une leçon".into());
        }
        let mut doc = self.load_lessons();
        let entry = LessonEntry {
            id: format!("L-{:03}", doc.lessons.len() + 1),
            rule: rule.trim().to_string(),
            incident: incident.trim().to_string(),
            provenance: provenance.to_string(),
            added_at: now_utc(),
            active: true,
        };
        doc.lessons.push(entry.clone());
        doc.updated_at = now_utc();
        let raw = serde_json::to_string_pretty(&doc).map_err(|e| e.to_string())?;
        write_atomic(&self.lessons_path(), raw.as_bytes())?;
        Ok(entry)
    }

    pub fn load_library(&self) -> LibraryIndex {
        fs::read_to_string(self.library_index_path())
            .ok()
            .and_then(|raw| serde_json::from_str(&raw).ok())
            .unwrap_or_else(|| LibraryIndex {
                updated_at: now_utc(),
                entries: Vec::new(),
            })
    }

    /// Search-before-produce (0 tokens): filters by query, category, and optional compatible UEFN version.
    pub fn search_library(
        &self,
        query: &str,
        category: Option<&str>,
        only_verified: bool,
    ) -> Vec<LibraryEntry> {
        let idx = self.load_library();
        let q = query.trim().to_lowercase();
        idx.entries
            .into_iter()
            .filter(|e| {
                if only_verified && e.status != "verified" {
                    return false;
                }
                if let Some(cat) = category {
                    if !cat.is_empty() && cat != "all" && e.category != cat {
                        return false;
                    }
                }
                if q.is_empty() {
                    return true;
                }
                e.title.to_lowercase().contains(&q)
                    || e.summary.to_lowercase().contains(&q)
                    || e.id.to_lowercase().contains(&q)
                    || e.tags.iter().any(|t| t.to_lowercase().contains(&q))
            })
            .collect()
    }

    pub fn add_library_entry(&self, mut entry: LibraryEntry) -> Result<LibraryEntry, String> {
        if !ALLOWED_LIBRARY_PROVENANCE.contains(&entry.provenance.as_str()) {
            return Err(format!(
                "LIBRARY_PROVENANCE_REFUSED : seul ce qui est prouvé entre ({:?}), refus de '{}'",
                ALLOWED_LIBRARY_PROVENANCE, entry.provenance
            ));
        }
        if entry.title.trim().is_empty() || entry.license.trim().is_empty() {
            return Err("Titre et licence obligatoires pour entrer dans la bibliothèque".into());
        }
        if entry.id.trim().is_empty() {
            entry.id = format!("lib_{}", &uuid::Uuid::new_v4().to_string()[..8]);
        }
        if entry.created_at.is_empty() {
            entry.created_at = now_utc();
        }
        if entry.status.is_empty() {
            entry.status = "verified".to_string();
        }
        let mut idx = self.load_library();
        idx.entries.retain(|e| e.id != entry.id);
        idx.entries.push(entry.clone());
        idx.updated_at = now_utc();
        let raw = serde_json::to_string_pretty(&idx).map_err(|e| e.to_string())?;
        write_atomic(&self.library_index_path(), raw.as_bytes())?;
        Ok(entry)
    }

    /// Marks entries tied to an older UEFN version as `suspect` so scripts re-verify before reuse.
    pub fn flag_stale_for_uefn_version(&self, current_uefn_version: &str) -> Result<usize, String> {
        let mut idx = self.load_library();
        let mut flagged = 0usize;
        for e in &mut idx.entries {
            let version_sensitive = matches!(
                e.category.as_str(),
                "3d_asset" | "verse_module" | "device_config"
            );
            if version_sensitive && e.status == "verified" && e.uefn_version != current_uefn_version
            {
                e.status = "suspect".to_string();
                flagged += 1;
            }
        }
        idx.updated_at = now_utc();
        let raw = serde_json::to_string_pretty(&idx).map_err(|e| e.to_string())?;
        write_atomic(&self.library_index_path(), raw.as_bytes())?;
        Ok(flagged)
    }
}
