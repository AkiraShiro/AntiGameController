"""
Встроенный сервер + веб-админка для Anti-Game Controller.

Используется, когда нет внешнего сервера — этот ПК становится
«главным» и предоставляет админку остальным ноутбукам в локальной сети.

Стек:
- Python http.server (без внешних зависимостей)
- HTML/CSS/JS (vanilla, без фреймворков) — шаблон ниже
- Хранение состояния: SQLite (встроенный) или in-memory dict
- Эндпоинты:
    POST /api/agents/<id>/heartbeat
    GET  /api/agents/<id>/commands?since=N
    POST /api/agents/<id>/logs
    GET  /api/agents
    POST /api/agents/<id>/command
    GET  /                         — веб-админка
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
import socketserver
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from logger import get_logger

logger = get_logger("NetServer")
ONLINE_TIMEOUT_SECONDS = 90


# --------------------- HTML-админка ---------------------

ADMIN_HTML = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Anti-Game Controller — Админка</title>
<style>
body { font-family: -apple-system, Segoe UI, sans-serif;
       background: #1e1e2e; color: #cdd6f4; margin: 0; }
header { background: #181825; padding: 14px 24px;
         border-bottom: 1px solid #313244; display: flex;
         align-items: center; justify-content: space-between; }
header h1 { margin: 0; font-size: 18px; }
main { padding: 24px; max-width: 1200px; margin: 0 auto; }
section.panel { background: #181825; border: 1px solid #313244; border-radius: 10px;
           padding: 18px; margin-bottom: 18px; }
.panel h2 { margin: 0 0 14px 0; font-size: 16px; }
.grid { display: grid; grid-template-columns: 280px 1fr; gap: 16px; }
.sidebar { display: flex; flex-direction: column; gap: 8px; }
.config-list { display: flex; flex-direction: column; gap: 8px; max-height: 320px; overflow: auto; }
.config-item { width: 100%; text-align: left; background: #11111b; color: #cdd6f4; border: 1px solid #313244; border-radius: 8px; padding: 10px 12px; cursor: pointer; }
.config-item.active { border-color: #89b4fa; box-shadow: 0 0 0 1px #89b4fa inset; }
.config-item small { display: block; color: #7f849c; margin-top: 4px; }
.editor { display: flex; flex-direction: column; gap: 10px; }
.field-row { display: grid; grid-template-columns: 120px 1fr; gap: 10px; align-items: center; }
input[type="text"], textarea { width: 100%; background: #11111b; color: #cdd6f4; border: 1px solid #313244; border-radius: 8px; padding: 10px 12px; font-size: 14px; box-sizing: border-box; }
textarea { min-height: 320px; font-family: Consolas, monospace; resize: vertical; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
table { width: 100%; border-collapse: collapse; background: #181825;
        border-radius: 8px; overflow: hidden; }
th, td { padding: 10px 14px; text-align: left;
         border-bottom: 1px solid #313244; font-size: 14px; }
th { background: #11111b; color: #a6adc8; font-weight: 600; }
tr.online td:first-child::before {
    content: ""; display: inline-block; width: 8px; height: 8px;
    background: #a6e3a1; border-radius: 50%; margin-right: 8px;
}
tr.offline td:first-child::before {
    content: ""; display: inline-block; width: 8px; height: 8px;
    background: #f38ba8; border-radius: 50%; margin-right: 8px;
}
button { background: #89b4fa; color: #11111b; border: 0;
         border-radius: 6px; padding: 6px 12px; cursor: pointer;
         font-size: 13px; margin-right: 4px; }
button.danger { background: #f38ba8; }
button.muted { background: #585b70; color: #cdd6f4; }
button:hover { filter: brightness(1.1); }
select { background: #313244; color: #cdd6f4; border: 0;
         padding: 4px 8px; border-radius: 4px; font-size: 13px; }
#toast { position: fixed; bottom: 24px; right: 24px;
         background: #313244; color: #cdd6f4; padding: 12px 20px;
         border-radius: 8px; display: none; }
.badge { display: inline-block; padding: 2px 8px;
         border-radius: 4px; font-size: 11px;
         background: #313244; color: #cdd6f4; }
.badge.active { background: #a6e3a1; color: #11111b; }
</style>
</head>
<body>
<header>
  <h1>🛡️ Anti-Game Controller — Панель управления</h1>
  <div>
    <span class="badge">Агентов: <span id="agentCount">0</span></span>
        <span class="badge">Конфигов: <span id="configCount">0</span></span>
    <button class="muted" onclick="location.reload()">⟳ Обновить</button>
  </div>
</header>
<main>
    <section class="panel">
        <h2>Конфиги</h2>
        <div class="grid">
            <div class="sidebar">
                <div class="toolbar">
                    <button type="button" onclick="newConfig()">+ Новый</button>
                    <button type="button" class="muted" onclick="loadConfigs()">Обновить список</button>
                </div>
                <div class="config-list" id="configList"></div>
            </div>
            <div class="editor">
                <div class="field-row">
                    <label for="agentName">Имя компьютера</label>
                    <input id="agentName" type="text" placeholder="Например: Класс 5А - ПК1">
                </div>
                <div class="field-row">
                    <label for="configName">Название</label>
                    <input id="configName" type="text" placeholder="Например: Класс 5А">
                </div>
                <div class="toolbar">
                    <button type="button" onclick="saveConfig()">Сохранить</button>
                    <button type="button" class="danger" onclick="deleteConfig()">Удалить</button>
                    <button type="button" class="muted" onclick="applyConfigToAllAgents()">Назначить всем ПК</button>
                    <button type="button" class="muted" onclick="exportSelectedConfig()">Экспорт JSON</button>
                    <button type="button" class="muted" onclick="exportAllConfigs()">Экспорт всех</button>
                    <label class="muted" style="display:inline-flex;align-items:center;gap:8px;cursor:pointer;">
                        <input id="configImportFile" type="file" accept=".json,application/json" style="display:none" onchange="importConfigFile(event)">
                        <span class="badge">Импорт JSON</span>
                    </label>
                </div>
                <textarea id="configBody" spellcheck="false"></textarea>
            </div>
        </div>
    </section>
  <table id="agentsTable">
    <thead>
      <tr>
        <th>Статус</th>
        <th>Имя ПК</th>
        <th>Agent ID</th>
        <th>IP</th>
        <th>Защита</th>
        <th>Конфиг</th>
        <th>Последний контакт</th>
        <th>Действия</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
</main>
<div id="toast"></div>

<script>
let selectedConfigId = "";
let cachedConfigs = [];

function defaultConfigBody() {
    return JSON.stringify({
        agent_name: "",
        blocked_processes: [],
        blocked_websites: [],
        check_interval: 5,
        auto_start: true,
        show_notifications: true,
        notification_message: "⚠️ Доступ запрещен!",
        enable_autostart: true,
        enable_process_protection: true,
        theme: "dark"
    }, null, 2);
}

function escapeAttr(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function renderConfigList() {
    const list = document.getElementById("configList");
    list.innerHTML = "";
    document.getElementById("configCount").textContent = cachedConfigs.length;
    for (const cfg of cachedConfigs) {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "config-item" + (cfg.id === selectedConfigId ? " active" : "");
        item.innerHTML = "";
        const title = document.createElement("div");
        title.textContent = cfg.name || "Без названия";
        title.style.fontWeight = "600";
        const meta = document.createElement("small");
        meta.textContent = cfg.id;
        item.appendChild(title);
        item.appendChild(meta);
        item.onclick = () => loadConfigIntoEditor(cfg.id);
        list.appendChild(item);
    }
}

async function loadConfigs() {
    const r = await fetch("/api/configs");
    const data = await r.json();
    cachedConfigs = data.configs || [];
    renderConfigList();
    if (!selectedConfigId && cachedConfigs.length) {
        await loadConfigIntoEditor(cachedConfigs[0].id);
    }
    if (!cachedConfigs.length && !document.getElementById("configBody").value.trim()) {
        document.getElementById("configName").value = "";
        document.getElementById("configBody").value = defaultConfigBody();
    }
}

async function loadConfigIntoEditor(configId) {
    const r = await fetch(`/api/configs/${configId}`);
    if (!r.ok) {
        toast("Не удалось загрузить конфиг");
        return;
    }
    const cfg = await r.json();
    selectedConfigId = cfg.id;
    document.getElementById("configName").value = cfg.name || "";
    const body = cfg.body || {};
    document.getElementById("agentName").value = body.agent_name || "";
    document.getElementById("configBody").value = JSON.stringify(body, null, 2);
    renderConfigList();
}

function newConfig() {
    selectedConfigId = "";
    document.getElementById("configName").value = "";
    document.getElementById("agentName").value = "";
    document.getElementById("configBody").value = defaultConfigBody();
    renderConfigList();
}

async function saveConfig() {
    let body;
    try {
        body = JSON.parse(document.getElementById("configBody").value || "{}");
    } catch (e) {
        toast("JSON с ошибкой: " + e.message);
        return;
    }
    body.agent_name = document.getElementById("agentName").value.trim();
    const payload = {
        name: document.getElementById("configName").value.trim() || "Без названия",
        body
    };
    if (selectedConfigId) {
        payload.id = selectedConfigId;
    }
    const r = await fetch("/api/configs", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(payload)
    });
    const data = await r.json();
    if (!r.ok) {
        toast(data.error || "Не удалось сохранить конфиг");
        return;
    }
    selectedConfigId = data.id;
    toast("Конфиг сохранён");
    await loadConfigs();
    await loadConfigIntoEditor(selectedConfigId);
}

async function deleteConfig() {
    if (!selectedConfigId) {
        toast("Сначала выберите конфиг");
        return;
    }
    if (!confirm("Удалить выбранный конфиг?")) {
        return;
    }
    await fetch(`/api/configs/${selectedConfigId}`, {method: "DELETE"});
    selectedConfigId = "";
    newConfig();
    toast("Конфиг удалён");
    await loadConfigs();
}

async function importConfigFile(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) {
        return;
    }
    const text = await file.text();
    let data;
    try {
        data = JSON.parse(text);
    } catch (e) {
        toast("Файл не является валидным JSON");
        return;
    }
    if (data && typeof data === "object" && !Array.isArray(data) && data.body && data.name) {
        document.getElementById("configName").value = data.name;
        document.getElementById("configBody").value = JSON.stringify(data.body, null, 2);
    } else {
        document.getElementById("configName").value = file.name.replace(/\.json$/i, "") || "Импортированный конфиг";
        document.getElementById("configBody").value = JSON.stringify(data, null, 2);
    }
    selectedConfigId = "";
    renderConfigList();
    toast("JSON загружен в редактор");
    event.target.value = "";
}

async function applyConfigToAllAgents() {
    if (!selectedConfigId) {
        toast("Сначала выберите и сохраните конфиг");
        return;
    }
    const r = await fetch("/api/agents");
    const data = await r.json();
    const agents = data.agents || [];
    for (const a of agents) {
        await fetch(`/api/agents/${a.agent_id}/command`, {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({command:"apply_config", config_id:selectedConfigId})
        });
    }
    toast("Конфиг отправлен на все ПК");
    setTimeout(loadAgents, 1500);
}

function downloadJson(filename, payload) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}

async function exportSelectedConfig() {
    if (!selectedConfigId) {
        toast("Сначала выберите конфиг");
        return;
    }
    const r = await fetch(`/api/configs/${selectedConfigId}`);
    if (!r.ok) {
        toast("Не удалось экспортировать конфиг");
        return;
    }
    const cfg = await r.json();
    downloadJson(`${(cfg.name || "config").replace(/[\\/:*?"<>|]+/g, "_")}.json`, cfg);
    toast("Конфиг выгружен в JSON");
}

async function exportAllConfigs() {
    const r = await fetch("/api/configs/export");
    if (!r.ok) {
        toast("Не удалось выгрузить конфиги");
        return;
    }
    const data = await r.json();
    downloadJson("antigamecontroller-configs.json", data);
    toast("Все конфиги выгружены");
}

async function loadAgents() {
  const r = await fetch("/api/agents");
  const data = await r.json();
  const tb = document.querySelector("#agentsTable tbody");
  tb.innerHTML = "";
  document.getElementById("agentCount").textContent = data.agents.length;
  for (const a of data.agents) {
    const tr = document.createElement("tr");
    tr.className = (a.last_seen && (Date.now()/1000 - a.last_seen < 90)) ? "online" : "offline";
    const lastSeen = a.last_seen ? new Date(a.last_seen * 1000).toLocaleTimeString() : "\u2014";
    const cfgOpts = (data.configs || [])
      .map(c => `<option value="${c.id}" ${c.id===a.config_id?"selected":""}>${c.name}</option>`)
      .join("");
    tr.innerHTML = `
      <td>${tr.className === "online" ? "online" : "offline"}</td>
            <td>
                <b>${a.agent_name || ""}</b>
                <input id="agentName_${a.agent_id}" type="text" value="${escapeAttr(a.agent_name || "")}" placeholder="Новое имя" style="margin-top:6px; width:100%; box-sizing:border-box;">
                <div style="margin-top:6px;">
                    <button type="button" class="muted" onclick="renameAgent('${a.agent_id}')">Сохранить имя</button>
                </div>
            </td>
      <td><code style="color:#a6adc8">${a.agent_id}</code></td>
      <td>${a.ip || ""}</td>
      <td>${a.is_monitoring ? '<span class="badge active">ВКЛ</span>' : '<span class="badge">выкл</span>'}</td>
      <td><select onchange="assignConfig('${a.agent_id}', this.value)">
            <option value="">— по умолчанию —</option>${cfgOpts}
          </select></td>
      <td>${lastSeen}</td>
      <td>
        <button onclick="cmd('${a.agent_id}','start_protection')">▶ Включить</button>
        <button class="danger" onclick="cmd('${a.agent_id}','stop_protection')">■ Выключить</button>
                <button class="danger" onclick="cmd('${a.agent_id}','shutdown_pc')">⏻ Выключить ПК</button>
      </td>`;
    tb.appendChild(tr);
  }
}
async function cmd(agentId, command) {
  await fetch(`/api/agents/${agentId}/command`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({command})
  });
  toast("Команда отправлена: " + command);
  
  // Даём агенту 1.5 секунды, чтобы он забрал команду, 
  // выполнил её и прислал новый статус, а уже потом обновляем таблицу
  setTimeout(loadAgents, 1500);
}
async function assignConfig(agentId, configId) {
  await fetch(`/api/agents/${agentId}/command`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({command:"apply_config", config_id:configId})
  });
  toast("Конфиг назначен");
}

async function renameAgent(agentId) {
    const input = document.getElementById(`agentName_${agentId}`);
    const agentName = (input && input.value || "").trim();
    if (!agentName) {
        toast("Введите имя компьютера");
        return;
    }
    await fetch(`/api/agents/${agentId}/command`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({command:"rename_agent", agent_name:agentName})
    });
    toast("Имя компьютера обновлено");
    setTimeout(loadAgents, 1500);
}
function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.style.display = "block";
  setTimeout(() => t.style.display = "none", 2200);
}
newConfig();
loadConfigs();
loadAgents();
setInterval(loadConfigs, 15000);
setInterval(loadAgents, 5000);
</script>
</body>
</html>"""


# --------------------- Хранилище ---------------------

class Store:
    """SQLite-backed хранилище агентов, команд и конфигов."""

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.lock = threading.Lock()
        self._init_db()

    def _conn(self):
        return sqlite3.connect(self.path, timeout=10.0, check_same_thread=False)

    def _init_db(self):
        with self.lock, self._conn() as c:
            c.executescript("""
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

    # --- агенты ---

    def upsert_agent(self, a: dict):
        with self.lock, self._conn() as c:
            c.execute(
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

    def list_agents(self):
        """Returns ALL agent rows (including offline) so the UI can
        show recently seen machines while a new host is being elected.

        Сортировка стабильная по agent_name (без учёта регистра),
        а HEARTBEAT last_seen не должен влиять на позицию строки —
        иначе имена "прыгают" при каждом heartbeat и невозможно
        отредактировать имя ноутбука.
        """
        with self.lock, self._conn() as c:
            cur = c.execute(
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

    def list_online_agents(self):
        """Online-only filter - kept for backward compatibility."""
        now = time.time()
        return [
            a for a in self.list_agents()
            if now - float(a.get("last_seen") or 0) <= ONLINE_TIMEOUT_SECONDS
        ]

    def set_agent_config(self, agent_id: str, config_id: str):
        with self.lock, self._conn() as c:
            c.execute(
                "UPDATE agents SET config_id=? WHERE agent_id=?",
                (config_id or None, agent_id),
            )

    def set_agent_name(self, agent_id: str, agent_name: str):
        with self.lock, self._conn() as c:
            c.execute(
                "UPDATE agents SET agent_name=? WHERE agent_id=?",
                ((agent_name or "").strip(), agent_id),
            )

    # --- команды ---

    def enqueue_command(self, agent_id: str, command: str,
                        payload: dict | None = None):
        with self.lock, self._conn() as c:
            c.execute(
                """INSERT INTO commands
                   (agent_id, command, payload, created_at)
                   VALUES (?,?,?,?)""",
                (agent_id, command,
                 json.dumps(payload or {}),
                 time.time()),
            )

    def fetch_commands(self, agent_id: str, since: float):
        with self.lock, self._conn() as c:
            cur = c.execute(
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
            c.execute(
                "UPDATE commands SET delivered_at=? WHERE id <= ? AND delivered_at IS NULL",
                (time.time(), last_id),
            )
            return (
                [{"id": r[0], "command": r[1],
                  "payload": json.loads(r[2] or "{}"),
                  "created_at": r[3]} for r in rows],
                last_id,
            )

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
        with self.lock, self._conn() as c:
            c.execute(
                """INSERT INTO configs (id, name, body, created_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     name=excluded.name, body=excluded.body""",
                (config_id, name, json.dumps(body), time.time()),
            )
        return config_id

    def delete_config(self, config_id: str):
        with self.lock, self._conn() as c:
            c.execute("DELETE FROM configs WHERE id=?", (config_id,))
            c.execute("UPDATE agents SET config_id=NULL WHERE config_id=?", (config_id,))
        return True

    def list_configs(self):
        with self.lock, self._conn() as c:
            cur = c.execute(
                "SELECT id, name, body, created_at FROM configs ORDER BY name"
            )
            cols = [d[0] for d in cur.description]
            return [
                {**dict(zip(cols, r)), "body": json.loads(r[2] or "{}")}
                for r in cur.fetchall()
            ]

    def get_config(self, config_id: str):
        with self.lock, self._conn() as c:
            cur = c.execute(
                "SELECT id, name, body FROM configs WHERE id=?",
                (config_id,),
            )
            r = cur.fetchone()
            if not r:
                return None
            return {"id": r[0], "name": r[1],
                    "body": json.loads(r[2] or "{}")}

    # --- логи ---

    def add_log(self, agent_id: str, message: str):
        with self.lock, self._conn() as c:
            c.execute(
                """INSERT INTO logs (agent_id, message, created_at)
                   VALUES (?,?,?)""",
                (agent_id, message, time.time()),
            )

    def recent_logs(self, limit: int = 100):
        with self.lock, self._conn() as c:
            cur = c.execute(
                """SELECT agent_id, message, created_at
                   FROM logs ORDER BY id DESC LIMIT ?""",
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


# --------------------- HTTP-обработчик ---------------------

class _Handler(BaseHTTPRequestHandler):
    store: Store = None  # injected
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
                        if payload["config"].get("agent_name"):
                            self.store.set_agent_name(agent_id, payload["config"].get("agent_name"))
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
    """Запускает локальный сервер+админку в фоне."""
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
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"