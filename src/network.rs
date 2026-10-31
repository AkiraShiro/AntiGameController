use crate::{config::Config, hosts, processes};
use base64::Engine;
use serde_json::json;
use std::{net::{Ipv4Addr, SocketAddrV4, UdpSocket}, sync::{Arc, Mutex}, thread, time::{Duration, SystemTime, UNIX_EPOCH}};
use tiny_http::{Header, Method, Response, Server};

pub const HTTP_PORT: u16 = 8765;
pub const DISCOVERY_PORT: u16 = 8766;
const MAGIC: &str = "ANTIGAME_DISCOVERY_V1";

pub fn start(config: Arc<Mutex<Config>>) {
    let advertised = config.clone();
    thread::spawn(move || discovery_loop(advertised));
    thread::spawn(move || http_loop(config));
}

fn discovery_loop(config: Arc<Mutex<Config>>) {
    let socket = match UdpSocket::bind((Ipv4Addr::UNSPECIFIED, DISCOVERY_PORT)) { Ok(s) => s, Err(_) => return };
    let _ = socket.set_broadcast(true);
    let mut buffer = [0u8; 2048];
    loop {
        let cfg = config.lock().unwrap().clone();
        let packet = json!({"magic": MAGIC, "agent_id": cfg.agent_id, "agent_name": cfg.agent_name, "hostname": hostname::get().ok().and_then(|v| v.into_string().ok()), "is_host": true, "host_mode": cfg.host_mode, "host_url": format!("http://127.0.0.1:{HTTP_PORT}/"), "ts": now()});
        let _ = socket.send_to(packet.to_string().as_bytes(), SocketAddrV4::new(Ipv4Addr::BROADCAST, DISCOVERY_PORT));
        let _ = socket.set_read_timeout(Some(Duration::from_millis(100)));
        let _ = socket.recv_from(&mut buffer);
        thread::sleep(Duration::from_secs(5));
    }
}

fn http_loop(config: Arc<Mutex<Config>>) {
    let server = match Server::http((Ipv4Addr::UNSPECIFIED, HTTP_PORT)) { Ok(s) => s, Err(_) => return };
    for mut request in server.incoming_requests() {
        let cfg = config.clone();
        thread::spawn(move || {
            let path = request.url().split('?').next().unwrap_or("/").to_owned();
            if path.starts_with("/api/") && !authorized(&request, &cfg) { let _ = request.respond(Response::from_string("Unauthorized").with_status_code(401)); return; }
            let response = match (request.method(), path.as_str()) {
                (&Method::Get, "/") => Response::from_string(ADMIN_HTML),
                (&Method::Get, "/api/status") => Response::from_string(json!({"ok": true, "agent_id": cfg.lock().unwrap().agent_id}).to_string()),
                (&Method::Get, "/api/config") => Response::from_string(serde_json::to_string(&*cfg.lock().unwrap()).unwrap_or_else(|_| "{}".into())),
                (&Method::Get, "/api/agents") => Response::from_string(json!({"agents": [{"agent_id": cfg.lock().unwrap().agent_id, "online": true}], "configs": []}).to_string()),
                (&Method::Get, "/api/configs/export") => Response::from_string(serde_json::to_string(&*cfg.lock().unwrap()).unwrap_or_else(|_| "{}".into())),
                (&Method::Post, "/api/protect") => { let c = cfg.lock().unwrap().clone(); let _ = hosts::block(&c.blocked_websites); let _ = processes::kill_matching(&c.blocked_processes); Response::from_string("ok") }
                (&Method::Post, "/api/unprotect") => { let _ = hosts::unblock(); Response::from_string("ok") }
                _ => Response::from_string("AntiGame Controller").with_status_code(404),
            };
            let response = response.with_header(Header::from_bytes("Access-Control-Allow-Origin", "*").unwrap());
            let _ = request.respond(response);
        });
    }
}

const ADMIN_HTML: &str = r#"<!doctype html><meta charset="utf-8"><title>AntiGame Controller</title><style>body{font:16px sans-serif;max-width:760px;margin:40px auto;background:#111;color:#eee}button{padding:10px;margin:4px}</style><h1>AntiGame Controller</h1><p id=s>Loading...</p><button onclick="fetch('/api/protect',{method:'POST'}).then(refresh)">Protect</button><button onclick="fetch('/api/unprotect',{method:'POST'}).then(refresh)">Unprotect</button><script>function refresh(){fetch('/api/status').then(r=>r.json()).then(x=>s.textContent=JSON.stringify(x))}refresh()</script>"#;

fn authorized(request: &tiny_http::Request, config: &Arc<Mutex<Config>>) -> bool {
    let expected = config.lock().unwrap().password_hash.clone();
    let Some(header) = request.headers().iter().find(|header| header.field.equiv("Authorization")) else { return false };
    let encoded = header.value.as_str().strip_prefix("Basic ").unwrap_or("");
    let Some(decoded) = base64::engine::general_purpose::STANDARD.decode(encoded).ok().and_then(|bytes| String::from_utf8(bytes).ok()) else { return false };
    let password = decoded.split_once(':').map(|(_, value)| value).unwrap_or("");
    crate::config::sha256(password) == expected
}

fn now() -> f64 { SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs_f64() }