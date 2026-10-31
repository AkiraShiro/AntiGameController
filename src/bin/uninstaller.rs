#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    let app_dir = std::env::var_os("APPDATA").map(std::path::PathBuf::from).unwrap_or_default().join("AntiGameController");
    let _ = std::process::Command::new("schtasks").args(["/Delete", "/TN", "AntiGameController_AutoStart", "/F"]).output();
    let _ = std::process::Command::new("ipconfig").arg("/flushdns").output();
    let _ = std::fs::remove_dir_all(app_dir);
}