"""
Встроенный сервер + веб-админка для Anti-Game Controller.
Используется, когда нет внешнего сервера: этот ПК становится
главным и предоставляет админку остальным ноутбукам в локальной сети.
"""

import os
import json
import time
import base64
import hashlib
import uuid
import threading
import sqlite3
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from logger import get_logger

logger = get_logger("NetServer")
ONLINE_TIMEOUT_SECONDS = 90

# HTML-админка
from web import html as ADMIN_HTML


class Store:
    """SQLite-backed хранилище агентов, команд и конфигов с автозакрытием соединений."""

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.lock = threading.Lock()
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.path, timeout=10.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self.lock:
            conn = self._get_conn()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS agents (
                        agent_id TEXT PRIMARY KEY,
                        agent_name TEXT,
                        hostname TEXT,
                        ip TEXT,
                        is_monitoring INTEGER,
                        auto_start INTEGER,
                        config_id TEXT,
                        client_version TEXT,
                        last_seen REAL
                    );
                    CREATE TABLE IF NOT EXISTS commands (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id TEXT,
                        command TEXT,
                        payload TEXT,
                        created_at REAL,
                        delivered_at REAL
                    );
                    CREATE TABLE IF NOT EXISTS configs (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        body TEXT,
                        created_at REAL
                    );
                    CREATE TABLE IF NOT EXISTS logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id TEXT,
                        message TEXT,
                        created_at REAL
                    );
                """)
                conn.commit()
            finally:
                conn.close()

    # --- агенты ---

    def upsert_agent(self, a: dict):
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO agents
                       (agent_id, agent_name, hostname, ip, is_monitoring,
                        auto_start, client_version, last_seen)
                       VALUES (?,?,?,?,?,?,?,?)
                       ON CONFLICT(agent_id) DO UPDATE SET
                         agent_name=excluded.agent_name,
                         hostname=excluded.hostname,
                         ip=excluded.ip,
                         is_monitoring=excluded.is_monitoring,
                         auto_start=excluded.auto_start,
                         client_version=excluded.client_version,
                         last_seen=excluded.last_seen
                    """,
                    (
                        a["agent_id"], a.get("agent_name", ""),
                        a.get("hostname", ""), a.get("ip", ""),
                        int(bool(a.get("is_monitoring"))),
                        int(bool(a.get("auto_start"))),
                        a.get("client_version", ""),
                        time.time(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def list_agents(self):
        with self.lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    """SELECT agent_id, agent_name, hostname, ip,
                              is_monitoring, auto_start, config_id,
                              client_version, last_seen
                       FROM agents
                       ORDER BY
                         CASE WHEN agent_name IS NULL OR agent_name=''
                              THEN 1 ELSE 0 END,
                         LOWER(agent_name) ASC,
                         agent_id ASC"""
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
            finally:
                conn.close()

    def list_online_agents(self):
        now = time.time()
        return [
            a for a in self.list_agents()
            if now - float(a.get("last_seen") or 0) <= ONLINE_TIMEOUT_SECONDS
        ]

    def set_agent_config(self, agent_id: str, config_id: str):
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "UPDATE agents SET config_id=? WHERE agent_id=?",
                    (config_id or None, agent_id),
                )
                conn.commit()
            finally:
                conn.close()

    def set_agent_name(self, agent_id: str, agent_name: str):
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "UPDATE agents SET agent_name=? WHERE agent_id=?",
                    ((agent_name or "").strip(), agent_id),
                )
                conn.commit()
            finally:
                conn.close()

    # --- команды ---

    def enqueue_command(self, agent_id: str, command: str,
                        payload: dict | None = None):
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO commands
                       (agent_id, command, payload, created_at)
                       VALUES (?,?,?,?)""",
                    (agent_id, command,
                     json.dumps(payload or {}),
                     time.time()),
                )
                conn.commit()
            finally:
                conn.close()

    def fetch_commands(self, agent_id: str, since: float):
        with self.lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    """SELECT id, command, payload, created_at
                       FROM commands
                       WHERE agent_id=? AND id > ? AND delivered_at IS NULL
                       ORDER BY id""",
                    (agent_id, since),
                )
                rows = cur.fetchall()
                if not rows:
                    return [], 0.0
                last_id = rows[-1][0]
                conn.execute(
                    "UPDATE commands SET delivered_at=? WHERE id <= ? AND delivered_at IS NULL",
                    (time.time(), last_id),
                )
                conn.commit()
                return (
                    [{"id": r[0], "command": r[1],
                      "payload": json.loads(r[2] or "{}"),
                      "created_at": r[3]} for r in rows],
                    last_id,
                )
            finally:
                conn.close()

    # --- конфиги ---

    def upsert_config(self, cfg: dict):
        config_id = cfg.get("id") or uuid.uuid4().hex
        name = (cfg.get("name") or "").strip() or "Без названия"
        body = cfg.get("body")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except Exception:
                body = {}
        if not isinstance(body, dict):
            body = {}
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO configs (id, name, body, created_at)
                       VALUES (?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET
                         name=excluded.name, body=excluded.body""",
                    (config_id, name, json.dumps(body), time.time()),
                )
                conn.commit()
            finally:
                conn.close()
        return config_id

    def delete_config(self, config_id: str):
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute("DELETE FROM configs WHERE id=?", (config_id,))
                conn.execute("UPDATE agents SET config_id=NULL WHERE config_id=?", (config_id,))
                conn.commit()
            finally:
                conn.close()
        return True

    def list_configs(self):
        with self.lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    "SELECT id, name, body, created_at FROM configs ORDER BY name"
                )
                cols = [d[0] for d in cur.description]
                return [
                    {**dict(zip(cols, r)), "body": json.loads(r[2] or "{}")}
                    for r in cur.fetchall()
                ]
            finally:
                conn.close()

    def get_config(self, config_id: str):
        with self.lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    "SELECT id, name, body FROM configs WHERE id=?",
                    (config_id,),
                )
                r = cur.fetchone()
                if not r:
                    return None
                return {"id": r[0], "name": r[1],
                        "body": json.loads(r[2] or "{}")}
            finally:
                conn.close()

    # --- логи ---

    def add_log(self, agent_id: str, message: str):
        with self.lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO logs (agent_id, message, created_at)
                       VALUES (?,?,?)""",
                    (agent_id, message, time.time()),
                )
                conn.commit()
            finally:
                conn.close()

    def recent_logs(self, limit: int = 100):
        with self.lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    """SELECT agent_id, message, created_at
                       FROM logs ORDER BY id DESC LIMIT ?""",
                    (limit,),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
            finally:
                conn.close()


# --------------------- HTTP-обработчик ---------------------

class _Handler(BaseHTTPRequestHandler):
    store: Store = None
    admin_password_hash: str | None = None
    server_version = "AntiGameController/1.0"

    def log_message(self, format, *args):
        logger.info(format, *args)

    def _send_json(self, status: int, body: dict):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", 0))
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def _send_unauthorized(self):
        body = b"Unauthorized"
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="AntiGameController"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _require_admin_auth(self) -> bool:
        expected_hash = self.admin_password_hash or ""
        if not expected_hash:
            return True

        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            self._send_unauthorized()
            return False

        try:
            raw = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        except Exception:
            self._send_unauthorized()
            return False

        if ":" not in raw:
            self._send_unauthorized()
            return False

        _, password = raw.split(":", 1)
        digest = hashlib.sha256((password or "").encode("utf-8")).hexdigest()
        if digest != expected_hash:
            self._send_unauthorized()
            return False

        return True

    # --- маршруты ---

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path.rstrip("/")
        qs = parse_qs(p.query)
        if path == "" or path == "/":
            if not self._require_admin_auth():
                return
            body = ADMIN_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/agents":
            if not self._require_admin_auth():
                return
            self._send_json(200, {
                "agents": self.store.list_agents(),
                "configs": self.store.list_configs(),
            })
            return
        if path == "/api/configs":
            if not self._require_admin_auth():
                return
            self._send_json(200, {"configs": self.store.list_configs()})
            return
        if path == "/api/configs/export":
            if not self._require_admin_auth():
                return
            self._send_json(200, {
                "configs": self.store.list_configs(),
                "exported_at": time.time(),
            })
            return
        if path.startswith("/api/configs/"):
            if not self._require_admin_auth():
                return
            config_id = path.split("/")[3]
            cfg = self.store.get_config(config_id)
            if not cfg:
                self._send_json(404, {"error": "not found"})
                return
            self._send_json(200, cfg)
            return
        if path.startswith("/api/agents/") and path.endswith("/commands"):
            parts = path.split("/")
            agent_id = parts[3]
            since = float((qs.get("since") or ["0"])[0])
            cmds, new_since = self.store.fetch_commands(agent_id, since)
            self._send_json(200, {
                "commands": [
                    {"command": c["command"], **c["payload"]}
                    for c in cmds
                ],
                "server_ts": new_since,
            })
            return
        if path == "/api/logs":
            if not self._require_admin_auth():
                return
            self._send_json(200, {"logs": self.store.recent_logs()})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path)
        path = p.path.rstrip("/")
        if path.startswith("/api/agents/") and path.endswith("/heartbeat"):
            agent_id = path.split("/")[3]
            body = self._read_json()
            body["agent_id"] = agent_id
            self.store.upsert_agent(body)
            self._send_json(200, {"ok": True})
            return
        if path.startswith("/api/agents/") and path.endswith("/logs"):
            agent_id = path.split("/")[3]
            body = self._read_json()
            self.store.add_log(agent_id, body.get("message", ""))
            self._send_json(200, {"ok": True})
            return
        if path.startswith("/api/agents/") and path.endswith("/command"):
            if not self._require_admin_auth():
                return
            agent_id = path.split("/")[3]
            body = self._read_json()
            cmd = body.get("command")
            payload = {k: v for k, v in body.items() if k != "command"}
            if cmd == "apply_config":
                config_id = body.get("config_id")
                if config_id:
                    cfg = self.store.get_config(config_id)
                    if cfg:
                        payload["config_id"] = config_id
                        payload["config"] = cfg.get("body", {})
                        self.store.set_agent_config(agent_id, config_id)
                        # if payload["config"].get("agent_name"):
                        #     self.store.set_agent_name(agent_id, payload["config"].get("agent_name"))
            if cmd == "rename_agent":
                agent_name = body.get("agent_name", "")
                payload["agent_name"] = agent_name
                self.store.set_agent_name(agent_id, agent_name)
            self.store.enqueue_command(agent_id, cmd, payload)
            self._send_json(200, {"ok": True, "queued": cmd})
            return
        if path == "/api/configs":
            if not self._require_admin_auth():
                return
            body = self._read_json()
            config_id = self.store.upsert_config(body)
            self._send_json(200, {"ok": True, "id": config_id})
            return
        if path.startswith("/api/configs/"):
            if not self._require_admin_auth():
                return
            config_id = path.split("/")[3]
            self.store.delete_config(config_id)
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"error": "not found"})


class _ThreadedServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_local_server(port: int, db_path: str, admin_password_hash: str | None = None):
    """Запускает локальный сервер и админку в фоне."""
    store = Store(db_path)
    _Handler.store = store
    _Handler.admin_password_hash = admin_password_hash
    try:
        srv = _ThreadedServer(("0.0.0.0", port), _Handler)
    except OSError as e:
        logger.error(f"Не удалось запустить локальный сервер: {e}")
        return None
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    ip = get_local_ip()
    logger.info(
        f"Локальная админка запущена: http://{ip}:{port}/"
    )
    return srv


def get_local_ip() -> str:
    BAD_PREFIXES = ("127.", "0.", "172.0.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.30.", "172.31.")
    for test_target in [("8.8.8.8", 80), ("1.1.1.1", 80)]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(test_target)
            ip = s.getsockname()[0]
            s.close()
            if ip and not any(ip.startswith(p) for p in BAD_PREFIXES):
                return ip
        except Exception:
            pass
    try:
        hostname = socket.gethostname()
        infos = socket.gethostbyname_ex(hostname)
        for ip in infos[2]:
            if (ip.startswith("192.168.") or ip.startswith("10.")) and ":" not in ip:
                return ip
    except Exception:
        pass
    return "127.0.0.1"