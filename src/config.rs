use base64::{engine::general_purpose::URL_SAFE, Engine};
use fernet::Fernet;
use pbkdf2::pbkdf2_hmac;
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use std::{fs, path::PathBuf};

const APP_NAME: &str = "AntiGameController";
const SALT: &[u8] = b"anti_game_salt_key_2025_secure";
const MASTER_KEY: &[u8] = b"anti_game_master_key_do_not_share";

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    pub profile_name: String,
    pub password_hash: String,
    pub blocked_processes: Vec<String>,
    pub blocked_websites: Vec<String>,
    pub check_interval: u64,
    pub auto_start: bool,
    pub show_notifications: bool,
    pub notification_message: String,
    pub enable_autostart: bool,
    pub enable_process_protection: bool,
    pub host_mode: bool,
    pub theme: String,
    pub auto_update: bool,
    pub installed_version: String,
    pub agent_id: String,
    pub agent_name: String,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            profile_name: "default".into(),
            password_hash: sha256("1234"),
            blocked_processes: Vec::new(),
            blocked_websites: Vec::new(),
            check_interval: 5,
            auto_start: true,
            show_notifications: true,
            notification_message: "Доступ запрещен!\n\nОбратитесь к преподавателю для получения доступа.".into(),
            enable_autostart: true,
            enable_process_protection: true,
            host_mode: false,
            theme: "dark".into(),
            auto_update: true,
            installed_version: env!("CARGO_PKG_VERSION").into(),
            agent_id: uuid::Uuid::new_v4().simple().to_string(),
            agent_name: String::new(),
        }
    }
}

pub fn sha256(value: &str) -> String {
    use sha2::Digest;
    hex::encode(sha2::Sha256::digest(value.as_bytes()))
}

pub fn app_dir() -> PathBuf {
    std::env::var_os("APPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::var_os("USERPROFILE").map(PathBuf::from).unwrap_or_default())
        .join(APP_NAME)
}

fn cipher() -> Fernet {
    let mut key = [0u8; 32];
    pbkdf2_hmac::<Sha256>(MASTER_KEY, SALT, 100_000, &mut key);
    Fernet::new(&URL_SAFE.encode(key)).expect("valid Fernet key")
}

pub fn config_path() -> PathBuf { app_dir().join(".config.dat") }

pub fn load() -> Config {
    let _ = fs::create_dir_all(app_dir());
    if let Ok(data) = fs::read(config_path()) {
        if let Ok(json) = cipher().decrypt(&String::from_utf8_lossy(&data)) {
            if let Ok(config) = serde_json::from_slice::<Config>(&json) { return config; }
        }
    }
    let config = Config::default();
    let _ = save(&config);
    config
}

pub fn save(config: &Config) -> std::io::Result<()> {
    fs::create_dir_all(app_dir())?;
    let json = serde_json::to_vec_pretty(config).map_err(std::io::Error::other)?;
    fs::write(config_path(), cipher().encrypt(&json).into_bytes())
}