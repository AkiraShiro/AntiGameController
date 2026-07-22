html = '''<!doctype html>
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

  // Сортировка: сначала online, затем offline
  const sortedAgents = (data.agents || []).sort((a, b) => {
    const aOnline = a.last_seen && (Date.now() / 1000 - a.last_seen < 90);
    const bOnline = b.last_seen && (Date.now() / 1000 - b.last_seen < 90);
    return bOnline - aOnline;
  });

  for (const a of sortedAgents) {
    const tr = document.createElement("tr");
    tr.className = (a.last_seen && (Date.now()/1000 - a.last_seen < 90)) ? "online" : "offline";
    const lastSeen = a.last_seen ? new Date(a.last_seen * 1000).toLocaleTimeString() : "";
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
            <option value="">по умолчанию</option>${cfgOpts}
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
</html>'''