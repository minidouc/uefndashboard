use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub server: ServerConfig,
    pub grid: GridConfig,
    pub theme: ThemeConfig,
    pub shortcuts: BTreeMap<String, String>,
    pub tools: ToolsConfig,
    pub providers: BTreeMap<String, ProviderConfig>,
    pub roles: BTreeMap<String, RoleConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerConfig {
    pub host: String,
    pub port: u16,
    pub active_project: String,
    pub uefn_version: String,
    pub mcp_mode: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GridConfig {
    pub tile_size_uu: f64,
    pub floor_height_uu: f64,
    pub default_district_tiles_x: u32,
    pub default_district_tiles_y: u32,
    pub min_passage_width_uu: f64,
    pub max_step_height_uu: f64,
    pub contact_tolerance_uu: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThemeConfig {
    pub preset: String,
    pub font_sans: String,
    pub font_mono: String,
    pub radius_sm: String,
    pub radius_md: String,
    pub vars: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolsConfig {
    pub enabled: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderConfig {
    pub kind: String,
    pub endpoint: String,
    pub api_key_env: String,
    pub default_model: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoleConfig {
    pub label: String,
    pub tier: String,
    pub provider: String,
    pub model: String,
    #[serde(default)]
    pub readonly: bool,
    pub system_prompt: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermissionsConfig {
    pub defaults: BTreeMap<String, String>,
    pub protected_paths: ProtectedPathsConfig,
    pub shell: ShellPermissionConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProtectedPathsConfig {
    pub deny_write: Vec<String>,
    pub allow_write: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShellPermissionConfig {
    pub deny_patterns: Vec<String>,
    pub allow_prefixes: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct McpServersConfig {
    pub servers: BTreeMap<String, McpServerEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct McpServerEntry {
    pub label: String,
    pub enabled: bool,
    pub transport: String,
    pub endpoint: String,
    #[serde(default = "default_timeout")]
    pub timeout_secs: u64,
    #[serde(default)]
    pub cooldown_secs: u64,
    #[serde(default = "default_retries")]
    pub max_retries: u32,
    #[serde(default = "default_mode")]
    pub mode: String,
    #[serde(default)]
    pub command: Option<String>,
    #[serde(default)]
    pub args: Vec<String>,
    #[serde(default)]
    pub allowed_read_tools: Vec<String>,
    #[serde(default)]
    pub allowed_write_tools: Vec<String>,
    #[serde(default)]
    pub forbidden_tools: Vec<String>,
}

fn default_timeout() -> u64 {
    60
}
fn default_retries() -> u32 {
    3
}
fn default_mode() -> String {
    "simulator".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CircuitBreakersConfig {
    #[serde(rename = "$comment", default)]
    pub comment: Option<String>,
    pub writes_halted: bool,
    pub blocked_tools: Vec<String>,
    pub reason: Option<String>,
}

#[derive(Debug, Clone)]
pub struct RootPaths {
    pub root: PathBuf,
}

impl RootPaths {
    pub fn discover(explicit: Option<PathBuf>) -> Self {
        if let Some(p) = explicit {
            return Self { root: p };
        }
        let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
        if cwd.join("config/app.toml").exists() {
            return Self { root: cwd };
        }
        if let Some(parent) = cwd.parent() {
            if parent.join("config/app.toml").exists() {
                return Self {
                    root: parent.to_path_buf(),
                };
            }
        }
        Self { root: cwd }
    }

    pub fn config_dir(&self) -> PathBuf {
        self.root.join("config")
    }

    pub fn app_toml(&self) -> PathBuf {
        self.config_dir().join("app.toml")
    }

    pub fn permissions_toml(&self) -> PathBuf {
        self.config_dir().join("permissions.toml")
    }

    pub fn mcp_servers_toml(&self) -> PathBuf {
        self.config_dir().join("mcp_servers.toml")
    }

    pub fn circuit_breakers_json(&self) -> PathBuf {
        self.config_dir().join("circuit_breakers.json")
    }

    pub fn validators_dir(&self) -> PathBuf {
        self.root.join("validators")
    }

    pub fn compat_dir(&self) -> PathBuf {
        self.root.join("compat")
    }

    pub fn workspace_dir(&self) -> PathBuf {
        self.root.join("workspace")
    }

    pub fn projects_dir(&self) -> PathBuf {
        self.workspace_dir().join("projects")
    }

    pub fn project_dir(&self, slug: &str) -> PathBuf {
        self.projects_dir().join(slug)
    }

    pub fn ui_dist_dir(&self) -> PathBuf {
        self.root.join("ui/dist")
    }
}

pub fn load_app_config(paths: &RootPaths) -> Result<AppConfig, String> {
    let raw = fs::read_to_string(paths.app_toml())
        .map_err(|e| format!("Impossible de lire config/app.toml: {e}"))?;
    toml::from_str(&raw).map_err(|e| format!("Erreur syntaxe app.toml: {e}"))
}

pub fn save_app_config(paths: &RootPaths, cfg: &AppConfig) -> Result<(), String> {
    let raw = toml::to_string_pretty(cfg)
        .map_err(|e| format!("Erreur sérialisation app.toml: {e}"))?;
    write_atomic(&paths.app_toml(), raw.as_bytes())
}

pub fn load_permissions_config(paths: &RootPaths) -> Result<PermissionsConfig, String> {
    let raw = fs::read_to_string(paths.permissions_toml())
        .map_err(|e| format!("Impossible de lire config/permissions.toml: {e}"))?;
    toml::from_str(&raw).map_err(|e| format!("Erreur syntaxe permissions.toml: {e}"))
}

pub fn save_permissions_config(paths: &RootPaths, cfg: &PermissionsConfig) -> Result<(), String> {
    let raw = toml::to_string_pretty(cfg)
        .map_err(|e| format!("Erreur sérialisation permissions.toml: {e}"))?;
    write_atomic(&paths.permissions_toml(), raw.as_bytes())
}

pub fn load_mcp_config(paths: &RootPaths) -> Result<McpServersConfig, String> {
    let raw = fs::read_to_string(paths.mcp_servers_toml())
        .map_err(|e| format!("Impossible de lire config/mcp_servers.toml: {e}"))?;
    toml::from_str(&raw).map_err(|e| format!("Erreur syntaxe mcp_servers.toml: {e}"))
}

pub fn save_mcp_config(paths: &RootPaths, cfg: &McpServersConfig) -> Result<(), String> {
    let raw = toml::to_string_pretty(cfg)
        .map_err(|e| format!("Erreur sérialisation mcp_servers.toml: {e}"))?;
    write_atomic(&paths.mcp_servers_toml(), raw.as_bytes())
}

pub fn load_circuit_breakers(paths: &RootPaths) -> Result<CircuitBreakersConfig, String> {
    let raw = fs::read_to_string(paths.circuit_breakers_json())
        .map_err(|e| format!("Impossible de lire circuit_breakers.json: {e}"))?;
    serde_json::from_str(&raw).map_err(|e| format!("Erreur JSON circuit_breakers.json: {e}"))
}

pub fn save_circuit_breakers(
    paths: &RootPaths,
    cfg: &CircuitBreakersConfig,
) -> Result<(), String> {
    let raw = serde_json::to_string_pretty(cfg)
        .map_err(|e| format!("Erreur sérialisation circuit_breakers.json: {e}"))?;
    write_atomic(&paths.circuit_breakers_json(), raw.as_bytes())
}

pub fn write_atomic(target: &Path, content: &[u8]) -> Result<(), String> {
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent)
            .map_err(|e| format!("Création dossier {} impossible: {e}", parent.display()))?;
    }
    let tmp = target.with_extension(format!("tmp.{}", uuid::Uuid::new_v4()));
    fs::write(&tmp, content).map_err(|e| format!("Écriture temporaire impossible: {e}"))?;
    fs::rename(&tmp, target).map_err(|e| format!("Renommage atomique impossible: {e}"))
}

pub fn now_utc() -> String {
    chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true)
}
