use crate::config::Config;
use serde::Deserialize;
use std::{fs, path::PathBuf, process::Command};

#[derive(Deserialize)] struct Release { tag_name: String, assets: Vec<Asset> }
#[derive(Deserialize)] struct Asset { name: String, browser_download_url: String }

pub fn check_and_stage(config: &mut Config) -> Result<Option<String>, String> {
    let client = reqwest::blocking::Client::builder().user_agent("AntiGameController-Updater").build().map_err(|e| e.to_string())?;
    let release: Release = client.get("https://api.github.com/repos/AkiraShiro/antigamecontroller/releases/latest").send().map_err(|e| e.to_string())?.json().map_err(|e| e.to_string())?;
    let version = release.tag_name.trim_start_matches('v');
    if parse_version(version) <= parse_version(&config.installed_version) { return Ok(None); }
    let asset = release.assets.iter().find(|a| a.name.to_ascii_lowercase().contains("antigame") && a.name.ends_with(".exe")).or_else(|| release.assets.iter().find(|a| a.name.ends_with(".exe"))).ok_or("release has no .exe asset")?;
    let target = std::env::temp_dir().join(format!("AntiGameController-{version}.exe"));
    let bytes = client.get(&asset.browser_download_url).send().map_err(|e| e.to_string())?.bytes().map_err(|e| e.to_string())?;
    fs::write(&target, bytes).map_err(|e| e.to_string())?;
    config.installed_version = version.into();
    stage_replacement(target)?;
    Ok(Some(version.into()))
}

fn parse_version(value: &str) -> Vec<u64> {
    value.trim_start_matches('v').split('.').map(|part| part.parse::<u64>().unwrap_or(0)).collect()
}

fn stage_replacement(download: PathBuf) -> Result<(), String> {
    let current = std::env::current_exe().map_err(|e| e.to_string())?;
    let script = std::env::temp_dir().join("antigame_updater.cmd");
    let body = format!("@echo off\ntimeout /t 2 /nobreak >nul\ncopy /Y \"{}\" \"{}\" >nul\nstart \"\" \"{}\"\ndel /Q \"{}\"\n", download.display(), current.display(), current.display(), script.display());
    fs::write(&script, body).map_err(|e| e.to_string())?;
    Command::new("cmd").args(["/C", script.to_string_lossy().as_ref()]).spawn().map_err(|e| e.to_string())?;
    Ok(())
}