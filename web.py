html = '''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anti-Game Controller — Админка</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg-base: #07070a;
  --bg-surface: #0f0e17;
  --bg-card: #151421;
  --bg-input: #0a0910;
  
  --neon-pink: #ff007f;
  --neon-pink-glow: rgba(255, 0, 127, 0.4);
  --neon-pink-dim: rgba(255, 0, 127, 0.15);
  
  --neon-cyan: #00f0ff;
  --neon-green: #00ff88;
  --neon-red: #ff3366;
  
  --text-main: #f1f1f5;
  --text-muted: #88869f;
  --border-color: rgba(255, 0, 127, 0.2);
  --border-subtle: rgba(255, 255, 255, 0.07);
  
  --radius-lg: 16px;
  --radius-md: 10px;
  --radius-sm: 6px;
}

* {
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background-color: var(--bg-base);
  color: var(--text-main);
  margin: 0;
  padding: 0;
  min-height: 100vh;
  background-image: 
    radial-gradient(circle at 15% 15%, rgba(255, 0, 127, 0.08) 0%, transparent 40%),
    radial-gradient(circle at 85% 85%, rgba(0, 240, 255, 0.05) 0%, transparent 40%);
  background-attachment: fixed;
}

/* Header Styles */
header {
  background: rgba(15, 14, 23, 0.8);
  backdrop-filter: blur(12px);
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), 0 1px 0 var(--neon-pink-glow);
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

header h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #fff;
  text-shadow: 0 0 10px var(--neon-pink-glow);
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-main);
  cursor: pointer;
  user-select: none;
  background: rgba(255, 255, 255, 0.04);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
  transition: all 0.2s ease;
}

.checkbox-label:hover {
  border-color: var(--neon-pink);
  background: var(--neon-pink-dim);
}

.checkbox-label input {
  cursor: pointer;
  accent-color: var(--neon-pink);
}

/* Main Layout */
main {
  padding: 24px 16px;
  max-width: 1300px;
  margin: 0 auto;
}

/* Collapsible Panel Card */
section.panel {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  margin-bottom: 24px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 0 0 1px rgba(255, 255, 255, 0.03);
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
}

section.panel::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--neon-pink), transparent);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.panel-title-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
}

.panel h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.toggle-btn {
  font-size: 12px;
  color: var(--neon-pink);
  background: transparent;
  border: none;
  padding: 4px 8px;
  cursor: pointer;
  text-shadow: 0 0 5px var(--neon-pink-glow);
}

.panel-content {
  display: none;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--border-subtle);
}

section.panel.open .panel-content {
  display: block;
}

/* Config Selector Bar */
.config-select-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  width: 100%;
  background: var(--bg-surface);
  padding: 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  flex-wrap: wrap;
}

.select-wrapper {
  position: relative;
  flex: 1;
  min-width: 200px;
}

.select-wrapper select {
  width: 100%;
  appearance: none;
  background: var(--bg-input);
  color: #fff;
  border: 1px solid var(--border-color);
  padding: 10px 16px;
  padding-right: 36px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  outline: none;
  cursor: pointer;
  box-shadow: 0 0 10px rgba(0,0,0,0.5);
  transition: all 0.2s ease;
}

.select-wrapper select:focus {
  border-color: var(--neon-pink);
  box-shadow: 0 0 12px var(--neon-pink-glow);
}

.select-wrapper::after {
  content: "▼";
  font-size: 10px;
  color: var(--neon-pink);
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
}

/* Form Controls & Inputs */
.editor-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}

.field-group {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.field-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-row label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--text-muted);
  font-weight: 600;
}

input[type="text"], textarea {
  width: 100%;
  background: var(--bg-input);
  color: var(--text-main);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  font-size: 14px;
  outline: none;
  transition: all 0.2s ease;
}

input[type="text"]:focus, textarea:focus {
  border-color: var(--neon-pink);
  box-shadow: 0 0 10px var(--neon-pink-glow);
}

textarea {
  min-height: 240px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
}

/* Toolbars & Buttons */
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

button, .btn-label {
  background: var(--neon-pink-dim);
  color: #fff;
  border: 1px solid var(--neon-pink);
  border-radius: var(--radius-sm);
  padding: 9px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s ease;
  text-shadow: 0 0 5px var(--neon-pink-glow);
  box-shadow: 0 0 10px rgba(255, 0, 127, 0.1);
}

button:hover, .btn-label:hover {
  background: var(--neon-pink);
  color: #000;
  box-shadow: 0 0 15px var(--neon-pink-glow);
  text-shadow: none;
  transform: translateY(-1px);
}

button:active, .btn-label:active {
  transform: translateY(0);
}

button.danger {
  background: rgba(255, 51, 102, 0.15);
  border-color: var(--neon-red);
  color: #ff85a2;
  text-shadow: 0 0 5px rgba(255, 51, 102, 0.5);
}

button.danger:hover {
  background: var(--neon-red);
  color: #fff;
  box-shadow: 0 0 15px rgba(255, 51, 102, 0.6);
}

button.muted {
  background: rgba(255, 255, 255, 0.04);
  border-color: var(--border-subtle);
  color: var(--text-muted);
  text-shadow: none;
  box-shadow: none;
}

button.muted:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.3);
}

/* Status Badges */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
  border: 1px solid var(--border-subtle);
}

.badge.active {
  background: rgba(0, 255, 136, 0.1);
  color: var(--neon-green);
  border-color: rgba(0, 255, 136, 0.3);
  box-shadow: 0 0 10px rgba(0, 255, 136, 0.2);
}

/* Tables Section */
.table-container {
  width: 100%;
  overflow-x: auto;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

th, td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-subtle);
  font-size: 14px;
}

th {
  background: var(--bg-surface);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 1px;
  white-space: nowrap;
}

tr:last-child td {
  border-bottom: none;
}

tr:hover td {
  background: rgba(255, 255, 255, 0.015);
}

/* Status Indicators */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
}

.status-pill::before {
  content: "";
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

tr.online .status-pill {
  color: var(--neon-green);
}
tr.online .status-pill::before {
  background: var(--neon-green);
  box-shadow: 0 0 8px var(--neon-green);
}

tr.offline .status-pill {
  color: var(--neon-red);
}
tr.offline .status-pill::before {
  background: var(--neon-red);
  box-shadow: 0 0 8px var(--neon-red);
}

/* Control Buttons Block */
.table-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.table-actions button {
  padding: 6px 10px;
  font-size: 12px;
}

/* Toast Notifications */
#toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: var(--bg-card);
  color: #fff;
  border: 1px solid var(--neon-pink);
  padding: 14px 24px;
  border-radius: var(--radius-md);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8), 0 0 15px var(--neon-pink-glow);
  display: none;
  z-index: 1000;
  font-weight: 500;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from { transform: translateY(100px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.json-status {
  font-size: 11px;
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.json-status.valid { color: var(--neon-green); }
.json-status.invalid { color: var(--neon-red); }

/* Mobile Optimizations - Direct Access to Action Buttons */
@media (max-width: 768px) {
  header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .header-controls {
    width: 100%;
    justify-content: space-between;
  }
  
  section.panel {
    padding: 16px;
  }
  
  .config-select-bar {
    flex-direction: column;
    align-items: stretch;
  }
  
  .toolbar button, .toolbar .btn-label {
    flex: 1 1 calc(50% - 10px);
  }

  /* Transform table into card layout for mobile screen so actions are on front */
  table, thead, tbody, th, td, tr {
    display: block;
  }

  thead {
    display: none;
  }

  tr {
    border-bottom: 1px solid var(--border-color);
    padding: 12px;
    background: var(--bg-card);
    margin-bottom: 12px;
    border-radius: var(--radius-md);
  }

  td {
    padding: 6px 0;
    border: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  td::before {
    content: attr(data-label);
    font-size: 11px;
    text-transform: uppercase;
    color: var(--text-muted);
    font-weight: 600;
  }

  td.actions-cell {
    flex-direction: column;
    align-items: stretch;
    padding-top: 10px;
    margin-top: 6px;
    border-top: 1px dashed var(--border-subtle);
  }

  td.actions-cell::before {
    margin-bottom: 8px;
  }

  .table-actions {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }

  .table-actions button {
    width: 100%;
    padding: 10px 6px;
  }
}
</style>
</head>
<body>

<header>
  <h1>🛡️ Anti-Game Controller</h1>
  <div class="header-controls">
    <label class="checkbox-label">
      <input type="checkbox" id="onlyOnlineCheck" onchange="toggleOnlyOnline(this.checked)">
      Только Online
    </label>
    <span class="badge">Агентов: <span id="agentCount" style="color:#fff; margin-left:4px;">0</span></span>
    <span class="badge">Конфигов: <span id="configCount" style="color:#fff; margin-left:4px;">0</span></span>
    <button type="button" class="muted" onclick="location.reload()">⟳ Обновить</button>
  </div>
</header>

<main>
  <!-- Collapsible Section -->
  <section class="panel" id="configPanel">
    <div class="panel-header" onclick="toggleConfigPanel()">
      <div class="panel-title-wrapper">
        <h2>Управление Конфигурациями</h2>
      </div>
      <button type="button" class="toggle-btn" id="togglePanelBtn">[ Развернуть ]</button>
    </div>

    <div class="panel-content">
      <!-- Top Dropdown & Actions Bar -->
      <div class="config-select-bar">
        <div class="select-wrapper">
          <select id="configSelect" onchange="onConfigDropdownChange(this.value)">
            <option value="">-- Выберите конфиг --</option>
          </select>
        </div>
        <button type="button" onclick="newConfig()">+ Новый</button>
        <button type="button" class="muted" onclick="loadConfigs()">↻ Обновить список</button>
      </div>

      <div class="editor-grid">
        <div class="field-group">
          <div class="field-row">
            <label for="configName">Название конфига</label>
            <input id="configName" type="text" placeholder="Например: Класс 5А">
          </div>
          <div class="field-row">
            <label for="agentName">Имя компьютера по умолчанию</label>
            <input id="agentName" type="text" placeholder="Например: Класс 5А - ПК1">
          </div>
        </div>

        <div class="field-row">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <label for="configBody">Параметры (JSON)</label>
            <div id="jsonStatus" class="json-status valid">✓ Валидный JSON</div>
          </div>
          <textarea id="configBody" spellcheck="false" oninput="validateJsonLive()"></textarea>
        </div>

        <div class="toolbar">
          <button type="button" onclick="saveConfig()">💾 Сохранить</button>
          <button type="button" class="danger" onclick="deleteConfig()">🗑️ Удалить</button>
          <button type="button" class="muted" onclick="applyConfigToAllAgents()">⚡ Назначить всем ПК</button>
          <button type="button" class="muted" onclick="exportSelectedConfig()">📤 Экспорт JSON</button>
          <button type="button" class="muted" onclick="exportAllConfigs()">📦 Экспорт всех</button>
          
          <label class="btn-label muted">
            <input id="configImportFile" type="file" accept=".json,application/json" style="display:none" onchange="importConfigFile(event)">
            📥 Импорт JSON
          </label>
        </div>
      </div>
    </div>
  </section>

  <div class="table-container">
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
  </div>
</main>

<div id="toast"></div>

<script>
let selectedConfigId = "";
let cachedConfigs = [];

// Cookie Helpers
function setCookie(name, value, days = 365) {
    const expires = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/`;
}

function getCookie(name) {
    return document.cookie.split('; ').reduce((acc, curr) => {
        const [key, val] = curr.split('=');
        return key === name ? decodeURIComponent(val || '') : acc;
    }, '');
}

function initOnlineFilter() {
    const saved = getCookie("only_online_filter");
    const checkbox = document.getElementById("onlyOnlineCheck");
    if (checkbox) {
        checkbox.checked = saved === "true";
    }
}

function toggleOnlyOnline(checked) {
    setCookie("only_online_filter", checked);
    loadAgents();
}

function toggleConfigPanel() {
    const panel = document.getElementById("configPanel");
    const btn = document.getElementById("togglePanelBtn");
    panel.classList.toggle("open");
    if (panel.classList.contains("open")) {
        btn.textContent = "[ Свернуть ]";
    } else {
        btn.textContent = "[ Развернуть ]";
    }
}

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

function validateJsonLive() {
    const val = document.getElementById("configBody").value;
    const statusEl = document.getElementById("jsonStatus");
    try {
        JSON.parse(val);
        statusEl.textContent = "✓ Валидный JSON";
        statusEl.className = "json-status valid";
        return true;
    } catch (e) {
        statusEl.textContent = "✕ Ошибка в JSON";
        statusEl.className = "json-status invalid";
        return false;
    }
}

function renderConfigDropdown() {
    const select = document.getElementById("configSelect");
    select.innerHTML = '<option value="">-- Выберите конфиг --</option>';
    document.getElementById("configCount").textContent = cachedConfigs.length;
    
    for (const cfg of cachedConfigs) {
        const opt = document.createElement("option");
        opt.value = cfg.id;
        opt.textContent = `${cfg.name || "Без названия"} (${cfg.id})`;
        if (cfg.id === selectedConfigId) {
            opt.selected = true;
        }
        select.appendChild(opt);
    }
}

function onConfigDropdownChange(val) {
    if (val) {
        loadConfigIntoEditor(val);
    } else {
        newConfig();
    }
}

async function loadConfigs() {
    try {
        const r = await fetch("/api/configs");
        const data = await r.json();
        cachedConfigs = data.configs || [];
        renderConfigDropdown();
        
        if (!selectedConfigId && cachedConfigs.length) {
            await loadConfigIntoEditor(cachedConfigs[0].id);
        }
        if (!cachedConfigs.length && !document.getElementById("configBody").value.trim()) {
            document.getElementById("configName").value = "";
            document.getElementById("configBody").value = defaultConfigBody();
            validateJsonLive();
        }
    } catch (e) {
        toast("Ошибка связи с сервером");
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
    validateJsonLive();
    renderConfigDropdown();
}

function newConfig() {
    selectedConfigId = "";
    document.getElementById("configName").value = "";
    document.getElementById("agentName").value = "";
    document.getElementById("configBody").value = defaultConfigBody();
    validateJsonLive();
    renderConfigDropdown();
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
    if (!file) return;
    
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
    validateJsonLive();
    renderConfigDropdown();
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
  // Защита от сброса имени: если фокус на инпуте редактирования имени — пропускаем перерисовку DOM
  if (document.activeElement && document.activeElement.id && document.activeElement.id.startsWith("agentName_")) {
    return;
  }

  try {
    const r = await fetch("/api/agents");
    const data = await r.json();
    const tb = document.querySelector("#agentsTable tbody");
    tb.innerHTML = "";

    const onlyOnline = document.getElementById("onlyOnlineCheck") ? document.getElementById("onlyOnlineCheck").checked : false;

    const sortedAgents = (data.agents || []).sort((a, b) => {
      const aOnline = a.last_seen && (Date.now() / 1000 - a.last_seen < 90);
      const bOnline = b.last_seen && (Date.now() / 1000 - b.last_seen < 90);
      return bOnline - aOnline;
    });

    let renderedCount = 0;

    for (const a of sortedAgents) {
      const isOnline = a.last_seen && (Date.now()/1000 - a.last_seen < 90);
      
      if (onlyOnline && !isOnline) {
        continue;
      }
      renderedCount++;

      const tr = document.createElement("tr");
      tr.className = isOnline ? "online" : "offline";
      const lastSeen = a.last_seen ? new Date(a.last_seen * 1000).toLocaleTimeString() : "Нет данных";
      
      const cfgOpts = (data.configs || [])
        .map(c => `<option value="${c.id}" ${c.id===a.config_id?"selected":""}>${c.name}</option>`)
        .join("");
        
      tr.innerHTML = `
        <td data-label="Статус"><span class="status-pill">${isOnline ? "online" : "offline"}</span></td>
        <td data-label="Имя ПК">
          <b>${escapeAttr(a.agent_name || "Без имени")}</b>
          <div style="display:flex; gap:4px; margin-top:6px;">
            <input id="agentName_${a.agent_id}" type="text" value="${escapeAttr(a.agent_name || "")}" placeholder="Новое имя" style="padding:4px 8px; font-size:12px;">
            <button type="button" class="muted" style="padding:4px 8px;" onclick="renameAgent('${a.agent_id}')">✓</button>
          </div>
        </td>
        <td data-label="Agent ID"><code style="color:var(--neon-pink); font-family:'JetBrains Mono', monospace;">${a.agent_id}</code></td>
        <td data-label="IP">${a.ip || "-"}</td>
        <td data-label="Защита">${a.is_monitoring ? '<span class="badge active">ВКЛ</span>' : '<span class="badge">ВЫКЛ</span>'}</td>
        <td data-label="Конфиг">
          <div class="select-wrapper" style="min-width:140px;">
            <select onchange="assignConfig('${a.agent_id}', this.value)" style="padding:6px 10px; font-size:12px;">
              <option value="">По умолчанию</option>${cfgOpts}
            </select>
          </div>
        </td>
        <td data-label="Контакт">${lastSeen}</td>
        <td data-label="Управление" class="actions-cell">
          <div class="table-actions">
            <button onclick="cmd('${a.agent_id}','start_protection')">▶ Включить</button>
            <button class="danger" onclick="cmd('${a.agent_id}','stop_protection')">■ Выключить</button>
            <button class="danger" onclick="cmd('${a.agent_id}','lockscreen_on')">🔒 Блок</button>
            <button class="danger" onclick="cmd('${a.agent_id}','lockscreen_off')">🔓 Разблок</button>
            <button class="danger" onclick="cmd('${a.agent_id}','shutdown_pc')">⏻ Выкл ПК</button>
          </div>
        </td>`;
      tb.appendChild(tr);
    }
    document.getElementById("agentCount").textContent = renderedCount;
  } catch (e) {
    console.error(e);
  }
}

async function cmd(agentId, command) {
  await fetch(`/api/agents/${agentId}/command`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({command})
  });
  toast("Команда отправлена: " + command);
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
    
    if (input) input.blur(); // Снимаем фокус с поля, разрешая продолжить автообновление
    setTimeout(loadAgents, 1500);
}

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg; 
  t.style.display = "block";
  setTimeout(() => t.style.display = "none", 2500);
}

// Initialization
initOnlineFilter();
newConfig();
loadConfigs();
loadAgents();
setInterval(loadConfigs, 15000);
setInterval(loadAgents, 5000);
</script>
</body>
</html>'''