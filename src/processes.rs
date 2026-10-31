use sysinfo::{ProcessesToUpdate, System};

pub fn kill_matching(names: &[String]) -> Vec<String> {
    let mut system = System::new_all();
    system.refresh_processes(ProcessesToUpdate::All, true);
    let names: Vec<String> = names.iter().map(|n| n.to_ascii_lowercase()).collect();
    let mut killed = Vec::new();
    for process in system.processes().values() {
        let name = process.name().to_string_lossy();
        if names.iter().any(|blocked| blocked == &name.to_ascii_lowercase()) {
            if process.kill() { killed.push(name.to_string()); }
        }
    }
    killed
}

pub fn running() -> Vec<(u32, String)> {
    let mut system = System::new_all();
    system.refresh_processes(ProcessesToUpdate::All, true);
    system.processes().iter().map(|(pid, p)| (pid.as_u32(), p.name().to_string_lossy().into_owned())).collect()
}