use std::{fs, io, path::Path};

const START: &str = "antigamecontroller";
const END: &str = "end";

pub fn hosts_path() -> &'static Path {
    Path::new(r"C:\Windows\System32\drivers\etc\hosts")
}

fn remove_block(lines: &[String]) -> Vec<String> {
    let mut output = Vec::new();
    let mut inside = false;
    for line in lines {
        let marker = line.trim().to_ascii_lowercase();
        if marker == START { inside = true; continue; }
        if marker == END { inside = false; continue; }
        if !inside { output.push(line.clone()); }
    }
    output
}

pub fn block(websites: &[String]) -> io::Result<()> {
    let text = fs::read_to_string(hosts_path()).unwrap_or_default();
    let mut lines: Vec<String> = remove_block(&text.lines().map(str::to_owned).collect::<Vec<_>>());
    lines.push(START.into());
    for site in websites.iter().map(|s| s.trim()).filter(|s| !s.is_empty()) {
        lines.push(format!("127.0.0.1 {site}"));
        if !site.starts_with("www.") { lines.push(format!("127.0.0.1 www.{site}")); }
    }
    lines.push(END.into());
    fs::write(hosts_path(), lines.join("\r\n") + "\r\n")?;
    flush_dns();
    Ok(())
}

pub fn unblock() -> io::Result<()> {
    let text = fs::read_to_string(hosts_path()).unwrap_or_default();
    fs::write(hosts_path(), remove_block(&text.lines().map(str::to_owned).collect::<Vec<_>>()).join("\r\n") + "\r\n")?;
    flush_dns();
    Ok(())
}

fn flush_dns() {
    let _ = std::process::Command::new("ipconfig").arg("/flushdns").output();
}