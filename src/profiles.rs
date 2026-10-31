use crate::config::app_dir;
use chrono::Local;
use serde::{Deserialize, Serialize};
use std::{fs, path::PathBuf};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ProfileInfo { pub id: String, pub name: String, pub created: String, pub source: String }

fn root() -> PathBuf { app_dir().join("store") }
fn index_path() -> PathBuf { app_dir().join(".profiles.idx") }

fn index() -> Vec<ProfileInfo> {
    serde_json::from_slice(&fs::read(index_path()).unwrap_or_default()).unwrap_or_default()
}

fn save_index(items: &[ProfileInfo]) -> std::io::Result<()> {
    fs::create_dir_all(app_dir())?;
    fs::write(index_path(), serde_json::to_vec_pretty(items).map_err(std::io::Error::other)?)
}

pub fn save(name: &str, config: &crate::config::Config) -> std::io::Result<String> {
    fs::create_dir_all(root())?;
    let id = uuid::Uuid::new_v4().simple().to_string();
    fs::write(root().join(&id), serde_json::to_vec_pretty(config).map_err(std::io::Error::other)?)?;
    let mut items = index();
    items.push(ProfileInfo { id: id.clone(), name: name.into(), created: Local::now().to_rfc3339(), source: "local".into() });
    save_index(&items)?;
    Ok(id)
}

pub fn list() -> Vec<ProfileInfo> { let mut v = index(); v.retain(|p| root().join(&p.id).exists()); v.sort_by(|a,b| b.created.cmp(&a.created)); v }

pub fn load(id: &str) -> Option<crate::config::Config> { serde_json::from_slice(&fs::read(root().join(id)).ok()?).ok() }

pub fn delete(id: &str) -> std::io::Result<()> {
    let _ = fs::remove_file(root().join(id));
    save_index(&index().into_iter().filter(|p| p.id != id).collect::<Vec<_>>())
}

pub fn export_json(config: &crate::config::Config) -> Result<String, serde_json::Error> {
    let mut value = serde_json::to_value(config)?;
    if let Some(object) = value.as_object_mut() {
        object.remove("password_hash");
        object.remove("agent_id");
        object.insert("_exported_by".into(), serde_json::json!("AntiGameController"));
        object.insert("_export_version".into(), serde_json::json!("2.0"));
    }
    serde_json::to_string_pretty(&value)
}

pub fn import_json(payload: &str) -> Result<crate::config::Config, String> {
    serde_json::from_str(payload).map_err(|error| error.to_string())
}