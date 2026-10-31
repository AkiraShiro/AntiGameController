use std::process::Command;

pub fn ensure(enabled: bool) -> bool {
    if !enabled { return remove(); }
    let exe = match std::env::current_exe() { Ok(path) => path, Err(_) => return false };
    let task = "AntiGameController_AutoStart";
    Command::new("schtasks").args(["/Create", "/TN", task, "/SC", "ONLOGON", "/RL", "HIGHEST", "/F", "/TR"])
        .arg(format!("\"{}\"", exe.display())).output().map(|r| r.status.success()).unwrap_or(false)
}

pub fn remove() -> bool {
    Command::new("schtasks").args(["/Delete", "/TN", "AntiGameController_AutoStart", "/F"]).output().map(|r| r.status.success()).unwrap_or(false)
}