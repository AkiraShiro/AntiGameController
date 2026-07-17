"""
Сетевой агент Anti-Game Controller.

Работает ТОЛЬКО в локальной сети. Режим выбирается автоматически (election):

1. Каждые ELECTION_INTERVAL ноутбук шлёт UDP-broadcast
   «привет, я живой» на 255.255.255.255:DISCOVERY_PORT.
2. Если за GRACE_PERIOD никто не объявил себя host →
   этот ноутбук становится «главным» (host): поднимает встроенный
   HTTP-сервер + веб-админку на DEFAULT_PORT и шлёт в broadcast свой
   host_url.
3. Если кто-то объявил себя host → этот ноутбук становится «клиентом»:
   берёт host_url из ответа и идёт в client-mode (heartbeat + long-poll).
4. Если клиент перестал получать heartbeats от host или не видит его
   announce-пакетов — перезапускает election; если в эфире больше нет
   ни одного host, устраивается deterministic election (меньший
   agent_id побеждает).

Пользователю ничего настраивать не нужно — каждый ноутбук запускает
один и тот же exe, и кто включился первым, тот и поднял админку.
"""
import json
import os
import socket
import time
import threading
import urllib.request
import urllib.error
import uuid
from typing import Optional

import config_storage

from logger import get_logger

logger = get_logger("Agent")

# --- сетевые параметры ---
DEFAULT_PORT = 8765          # HTTP-порт (host+client)
DISCOVERY_PORT = 8766        # UDP discovery
ELECTION_INTERVAL = 5.0      # секунд между broadcast'ами
GRACE_PERIOD = 4.0           # сколько ждать, прежде чем election
MISSING_HOST_TIMEOUT = 90    # секунд без host-announce → новый election
HEARTBEAT_INTERVAL = 10      # секунд между heartbeat'ами клиента
DISCOVERY_MAGIC = "ANTIGAME_DISCOVERY_V1"


def get_local_ip() -> str:
    """
    Возвращает локальный IPv4-адрес, видимый в LAN, БЕЗ обращения к интернету.

    Сначала пробуем узнать адрес через UDP-сокет, привязанный к discovery-порту
    (это работает без выхода в сеть). Если не вышло — перебираем
    интерфейсы через socket.gethostbyname_ex(gethostname()) и фильтруем
    127.0.0.1. Так host_url всегда указывает на реальный LAN-адрес, даже
    если у машины нет интернета.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", DISCOVERY_PORT))
        try:
            s.connect(("192.0.2.1", 1))  # TEST-NET-1: гарантированно не маршрутизируется
            ip = s.getsockname()[0]
            if ip and not ip.startswith("0."):
                return ip
        finally:
            try:
                s.close()
            except Exception:
                pass
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        infos = socket.gethostbyname_ex(hostname)
        for ip in infos[2]:
            if not ip.startswith("127.") and ":" not in ip:
                return ip
    except Exception:
        pass

    return "127.0.0.1"


def get_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def _ensure_agent_id(config: dict) -> str:
    aid = config.get("agent_id")
    if not aid:
        aid = uuid.uuid4().hex[:12]
        config["agent_id"] = aid
    return aid


def _ensure_started_at(config: dict) -> float:
    """Стабильный timestamp первого запуска агента.

    Используется в election: чем меньше started_at, тем раньше
    ноутбук включился → тот и остаётся хостом до собственного
    отключения. Это делает выбор хоста детерминированным и не
    зависящим от случайного uuid.
    """
    sat = config.get("started_at")
    if not isinstance(sat, (int, float)) or sat <= 0:
        sat = time.time()
        config["started_at"] = sat
    return float(sat)


def _make_announce(is_host: bool, host_url: str,
                   agent_id: str, agent_name: str,
                   started_at: float) -> dict:
    return {
        "magic": DISCOVERY_MAGIC,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "hostname": get_hostname(),
        "ip": get_local_ip(),
        "is_host": is_host,
        "host_url": host_url,
        "started_at": float(started_at or 0.0),
        "ts": time.time(),
    }


class NetworkAgent:
    """Election-агент: любой ноутбук может стать host/client автоматически."""

    def __init__(self, main_window):
        self.main = main_window
        self.config = main_window.config
        self.running = False
        self.thread: Optional[threading.Thread] = None

        # уникальный ID и имя
        self.agent_id = _ensure_agent_id(self.config)
        default_name = f"{get_hostname()}-{self.agent_id[-4:]}"
        self.agent_name = self.config.get("agent_name") or default_name
        self.config["agent_name"] = self.agent_name
        # Стабильный timestamp первого запуска — используется
        # в election: первый включившийся ноутбук остаётся хостом
        # до своего отключения.
        self.started_at = _ensure_started_at(self.config)

        self.local_ip = get_local_ip()
        self.local_port = int(self.config.get("local_port", DEFAULT_PORT))

        # динамическое состояние
        self.role = "idle"               # "host" | "client" | "idle"
        self.host_url: Optional[str] = None
        self._server = None
        self._known_peers: dict = {}
        self._first_seen_others_ts: float = 0.0
        self._election_lock = threading.Lock()
        self._last_client_tick = 0.0
        self._last_host_seen = 0.0
        self._command_cursor = 0.0

    def _sync_agent_name(self):
        name = (self.config.get("agent_name") or "").strip()
        if not name:
            name = f"{get_hostname()}-{self.agent_id[-4:]}"
        self.agent_name = name
        self.config["agent_name"] = name
        return name

    # ---------- запуск/остановка ----------

    def start(self):
        if self.running:
            return
        self._sync_agent_name()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        logger.info(
            f"Agent запущен: id={self.agent_id} name='{self.agent_name}' "
            f"ip={self.local_ip}"
        )

    def stop(self):
        self.running = False
        self._stop_local_server()

    # ---------- UI ----------

    def _set_status(self, text: str):
        try:
            from PyQt5.QtCore import QTimer
            lbl = getattr(self.main, "net_status_label", None)
            if lbl is not None:
                QTimer.singleShot(0, lambda: lbl.setText(text))
        except Exception:
            pass

    # ---------- главный цикл ----------

    def _loop(self):
        out_sock = self._make_broadcast_socket()
        in_sock = self._make_listen_socket()

        while self.running:
            try:
                now = time.time()

                is_host_now = (self.role == "host")
                host_url_now = (
                    f"http://{self.local_ip}:{self.local_port}/"
                    if is_host_now else (self.host_url or "")
                )
                pkt = _make_announce(
                    is_host=is_host_now,
                    host_url=host_url_now,
                    agent_id=self.agent_id,
                    agent_name=self._sync_agent_name(),
                    started_at=self.started_at,
                )
                self._broadcast(out_sock, pkt)

                peers = self._collect_announces(in_sock, timeout=2.0)
                for p in peers:
                    self._known_peers[p["agent_id"]] = p

                # заметка: видели кого-то?
                if peers and self._first_seen_others_ts == 0.0:
                    self._first_seen_others_ts = now

                self._decide_role(peers, now)

                # если мы host или client и есть host_url — запускаем клиентский тик
                if self.role in ("host", "client") and self.host_url:
                    if now - self._last_client_tick >= HEARTBEAT_INTERVAL: # Heartbeat каждые 10 с для быстрого отображения в админке
                        threading.Thread(target=self._client_tick, daemon=True).start()
                        self._last_client_tick = now

                    # Подхватываем команду polling, если он умер (например,
                    # временно теряли host_url) — иначе команды перестают
                    # приходить после первого сетевого blip.
                    if not getattr(self, "_command_thread_active", False):
                        threading.Thread(
                            target=self._command_poll_loop, daemon=True
                        ).start()

                self._update_status_label()

                time.sleep(ELECTION_INTERVAL)

            except Exception as e:
                logger.exception(f"agent loop: {e}")
                time.sleep(2.0)

        out_sock.close()
        try:
            in_sock.close()
        except Exception:
            pass
        self._stop_local_server()

    # ---------- сокеты ----------

    def _make_broadcast_socket(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.settimeout(0.5)
        return s

    def _make_listen_socket(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", DISCOVERY_PORT))
        s.settimeout(0.5)
        return s

    def _broadcast(self, sock: socket.socket, pkt: dict):
        try:
            data = json.dumps(pkt).encode("utf-8")
            sock.sendto(data, ("255.255.255.255", DISCOVERY_PORT))
        except Exception as e:
            logger.debug(f"broadcast error: {e}")

    def _collect_announces(self, sock: socket.socket,
                           timeout: float) -> list:
        peers: list = []
        end = time.time() + timeout
        while time.time() < end and self.running:
            try:
                data, _addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                pkt = json.loads(data.decode("utf-8"))
                if (pkt.get("magic") == DISCOVERY_MAGIC
                        and pkt.get("agent_id") != self.agent_id):
                    peers.append(pkt)
            except Exception:
                continue
        return peers

    # ---------- election ----------

    def _decide_role(self, peers: list, now: float):
        with self._election_lock:
            live_hosts = [
                p for p in peers
                if p.get("is_host")
                and now - p.get("ts", 0) < MISSING_HOST_TIMEOUT
            ]
            live_clients = [
                p for p in peers
                if (not p.get("is_host"))
                and now - p.get("ts", 0) < MISSING_HOST_TIMEOUT
            ]

            # Функция сравнения для election: побеждает ноутбук,
            # который включился РАНЬШЕ всех (наименьший started_at).
            # Если started_at отсутствует у одного из пиров — для
            # совместимости со старыми версиями падаем на agent_id.
            def started_key(p):
                sat = p.get("started_at") or 0.0
                if sat and sat > 0:
                    return (0, float(sat), p.get("agent_id") or "")
                return (1, 0.0, p.get("agent_id") or "")

            # 1) видели host → я клиент (или остаюсь host, если я
            # включился раньше всех видимых host'ов).
            # ВАЖНО: "первый зашёл — хост до отключения" выполняется
            # здесь: если у меня started_at меньше, чем у любого чужого
            # host, я НЕ уступаю — даже если у меня "случайный"
            # agent_id получился больше.
            if live_hosts:
                live_hosts.sort(key=started_key)
                best = live_hosts[0]
                self._last_host_seen = now
                # Host нашёлся — election отменяется, таймер сбрасываем
                self._first_seen_others_ts = 0.0

                if self.role == "host":
                    # Сравниваем по started_at: если я включился раньше —
                    # остаюсь хостом, никому не уступаю.
                    best_sat = best.get("started_at") or 0.0
                    if self.agent_id == best["agent_id"]:
                        # свой собственный announce в эфире — игнор.
                        return
                    if (not best_sat) or self.started_at < best_sat:
                        # я включился раньше — остаюсь хостом.
                        return
                    logger.info(
                        f"Уступаю host {best['agent_name']} "
                        f"({best['agent_id']}) — он включился раньше"
                    )
                    self._stop_local_server()
                    self.role = "client"
                    self.host_url = best.get("host_url") or self.host_url
                    self._command_cursor = 0.0
                    self._command_thread_active = False

                    return
                
                if self.host_url != best.get("host_url"):
                    logger.info("Хост изменился. Сбрасываем курсор команд для синхронизации.")
                    self._command_cursor = 0.0
                    self._command_thread_active = False

                # я клиент (или idle) → переключаюсь на нового host
                self.host_url = best.get("host_url") or self.host_url
                if self.role != "client":
                    logger.info(
                        f"Нашёл host {best['agent_name']} "
                        f"({best['agent_id']}) → становлюсь клиентом"
                    )
                self.role = "client"
                return

            # 2) host'ов нет. Если старый host_url был и его давно
            # не видели — сбрасываем: это может быть выключенный хост.
            if (self.role == "client"
                    and self.host_url
                    and self._last_host_seen > 0
                    and now - self._last_host_seen > MISSING_HOST_TIMEOUT):
                logger.warning(
                    f"Host {self.host_url} не отвечает "
                    f"{int(now - self._last_host_seen)}с — запускаю "
                    f"election"
                )
                self.host_url = None

            # 3) host'ов нет — может, я уже host
            if self.role == "host":
                # Если я уже host и нет live_hosts — продолжаю быть host'ом.
                return

            # 4) вообще никого нет → я первый включился
            if not live_clients:
                logger.info(
                    f"Я первый в сети → становлюсь HOST "
                    f"(http://{self.local_ip}:{self.local_port}/)"
                )
                self._start_local_server()
                self.role = "host"
                self.host_url = (
                    f"http://{self.local_ip}:{self.local_port}/"
                )
                self._first_seen_others_ts = 0.0
                return

            # 5) есть клиенты, но host ещё не объявился →
            # ждём GRACE_PERIOD, потом deterministic election
            # по started_at: побеждает тот, кто включился раньше.
            # ВАЖНО: ставим таймер ТОЛЬКО если он ещё не запущен —
            # иначе он сбрасывается каждый тик и election не наступает
            # никогда.
            if self._first_seen_others_ts == 0.0:
                self._first_seen_others_ts = now
            elapsed = now - self._first_seen_others_ts
            if elapsed < GRACE_PERIOD:
                return
            candidates = live_clients + [{
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "started_at": self.started_at,
            }]
            candidates.sort(key=started_key)
            winner = candidates[0]
            winner_id = winner["agent_id"]
            if winner_id == self.agent_id:
                logger.info(
                    "Election: я — новый HOST "
                    "(включился раньше всех остальных)"
                )
                self._start_local_server()
                self.role = "host"
                self.host_url = (
                    f"http://{self.local_ip}:{self.local_port}/"
                )
                self._first_seen_others_ts = 0.0
            else:
                self.role = "client"
                self.host_url = None  # ждём announce победителя

    # ---------- host: встроенный HTTP-сервер ----------

    def _start_local_server(self):
        if self._server is not None:
            return
        try:
            from network_server import start_local_server, Store
            db_path = os.path.join(
                os.environ.get("APPDATA", "."),
                "AntiGameController", "network.sqlite3",
            )
            self._db_path = db_path
            # Держим один локальный Store рядом с сервером — так
            # _fetch_local_commands не плодит новые соединения на
            # каждом тике и не упирается в блокировки SQLite при
            # параллельной записи из HTTP-обработчиков.
            try:
                self._local_store = Store(db_path)
            except Exception:
                self._local_store = None
            password_hash = None
            if isinstance(self.config, dict):
                password_hash = self.config.get("password_hash")
            self._server = start_local_server(
                self.local_port,
                db_path,
                password_hash,
            )
            if self._server is None:
                self._server = start_local_server(
                    self.local_port + 1,
                    db_path,
                    password_hash,
                )
                if self._server:
                    self.local_port = self.local_port + 1
        except Exception as e:
            logger.exception(f"start_local_server: {e}")

    def _stop_local_server(self):
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None

    # ---------- client: heartbeat + long-poll ----------

    def _client_tick(self):
        # Отправляем только heartbeat — он должен проходить быстро
        try:
            heartbeat_data = self._heartbeat()
            self._sync_configs(heartbeat_data.get("configs") if isinstance(heartbeat_data, dict) else None)
        except urllib.error.URLError as e:
            logger.warning(f"host недоступен: {e.reason}")
            self.host_url = None
        except Exception as e:
            logger.exception(f"client_tick (heartbeat) error: {e}")

        # Запускаем фоновый сбор команд, если он еще не активен
        if not getattr(self, "_command_thread_active", False):
            threading.Thread(target=self._command_poll_loop, daemon=True).start()

    def _command_poll_loop(self):
        """
        Непрерывный long-poll команд от host. Не завершается из-за
        временных ошибок сети — спит и пробует снова, пока работает агент
        и есть host_url. Управляется флагом _command_thread_active только
        чтобы не плодить дублирующие потоки.

        Сбрасываем host_url только после нескольких подряд ошибок — один
        таймаут может быть просто долгим ответом host'а.
        """
        if getattr(self, "_command_thread_active", False):
            return
        self._command_thread_active = True
        consecutive_failures = 0
        
        try:
            while self.running:
                # Если поток опроса активен, но роль сбросилась или хост пропал — 
                # выходим из цикла, чтобы не гонять пустые итерации. Флаг сбросится в finally.
                if not getattr(self, "_command_thread_active", False):
                    logger.info("Поток опроса команд принудительно остановлен (сброшен флаг активности).")
                    break

                if not (self.role in ("host", "client") and self.host_url):
                    time.sleep(1.0)
                    continue
                
                try:
                    # На хосте читаем команды напрямую из SQLite
                    if self.role == "host" and getattr(self, "_db_path", None):
                        cmds = self._fetch_local_commands()
                        consecutive_failures = 0
                    else:
                        # В режиме клиента запрашиваем команды по сети
                        cmds = self._poll_commands()
                        
                        # Если cmds вернул None (сетевой сбой в новом _http_json), имитируем URLError
                        if cmds is None:
                            raise urllib.error.URLError("Ошибка сети или пустой ответ от хоста")
                        
                        consecutive_failures = 0
                    
                    # Выполняем полученные команды
                    for c in cmds:
                        self._dispatch(c)
                        
                except urllib.error.URLError as e:
                    consecutive_failures += 1
                    logger.warning(
                        f"poll commands: host недоступен "
                        f"({e.reason}); попытка {consecutive_failures}"
                    )
                    if consecutive_failures >= 3:
                        logger.warning(
                            "host не отвечает 3 попытки подряд — "
                            "запускаю election"
                        )
                        self.host_url = None
                    time.sleep(2.0)
                except Exception as e:
                    logger.error(f"poll commands cycle error: {e}")
                    time.sleep(2.0)
        finally:
            self._command_thread_active = False

    def _fetch_local_commands(self):
        """Прямое чтение очереди команд из SQLite (только для host)."""
        try:
            store = getattr(self, "_local_store", None)
            if store is None:
                from network_server import Store
                store = Store(self._db_path)
                self._local_store = store
            cmds, new_since = store.fetch_commands(
                self.agent_id, int(self._command_cursor or 0)
            )
            # cursor — float (для совместимости с HTTP-веткой),
            # но SQLite id — INTEGER; в local-ветке обновляем
            # как число.
            try:
                self._command_cursor = max(
                    float(self._command_cursor or 0.0),
                    float(new_since or 0.0),
                )
            except Exception:
                self._command_cursor = float(new_since or 0.0)
            return [
                {"command": c["command"], **c["payload"]}
                for c in cmds
            ]
        except Exception as e:
            logger.debug(f"local fetch commands: {e}")
            return []

    def _poll_commands(self):
        url = (
            f"{self.host_url}api/agents/{self.agent_id}/commands"
            f"?since={self._command_cursor}"
        )
        # Для long-poll используем таймаут чуть больше, чем сердцебиение
        # клиента (30 c), чтобы соединение не рвалось раньше времени.
        data = self._http_json("GET", url, timeout=35)
        self._command_cursor = max(
            self._command_cursor,
            float(data.get("server_ts") or self._command_cursor),
        )
        return data.get("commands", [])

    def _http_json(self, method: str, url: str, body=None, timeout: int = 8):
        data = (json.dumps(body).encode("utf-8")
                if body is not None else None)
        
        # 'Connection': 'close' заставляет ОС сразу закрывать сокет, 
        # предотвращая залипание старых соединений при смене хоста
        headers = {
            "Content-Type": "application/json",
            "Connection": "close"
        }
        
        req = urllib.request.Request(
            url, data=data, headers=headers, method=method
        )
        
        try:
            # timeout передаем строго и в urlopen
            with urllib.request.urlopen(req, timeout=timeout) as r:
                response_data = r.read()
                if not response_data:
                    return None
                return json.loads(response_data.decode("utf-8"))
                
        except urllib.error.HTTPError as e:
            # Ошибки самого HTTP-протокола (например, 404 или 500)
            logger.warning(f"HTTP Error {e.code} при запросе {method} {url}: {e.reason}")
            return None
        except urllib.error.URLError as e:
            # Ошибки сети: хост недоступен, таймаут, нет сети
            logger.debug(f"Сеть недоступна (URLError) при {method} {url}: {e.reason}")
            return None
        except Exception as e:
            # Любые другие непредвиденные ошибки (например, битый JSON в ответе)
            logger.error(f"Непредвиденная ошибка при запросе {method} {url}: {e}")
            return None

    def _heartbeat(self):
        url = f"{self.host_url}api/agents/{self.agent_id}/heartbeat"
        return self._http_json("POST", url, {
            "agent_id": self.agent_id,
            "agent_name": self._sync_agent_name(),
            "hostname": get_hostname(),
            "ip": self.local_ip,
            "is_monitoring": getattr(self.main, "is_monitoring", False),
            "auto_start": self.config.get("auto_start", True),
            "client_version": "1.0.0",
        })

    def _sync_configs(self, configs):
        if not isinstance(configs, list):
            return
        server_ids = set()
        for cfg in configs:
            if not isinstance(cfg, dict):
                continue
            config_id = (cfg.get("id") or "").strip()
            if not config_id:
                continue
            server_ids.add(config_id)
            body = cfg.get("body") or {}
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except Exception:
                    body = {}
            if not isinstance(body, dict):
                body = {}
            config_storage.save_config_with_id(
                config_id,
                cfg.get("name") or "Без названия",
                body,
                source="server",
            )

        # Удаляем только старые серверные копии, локальные пользовательские профили не трогаем.
        try:
            for profile in config_storage.list_profiles():
                if profile.get("source") == "server" and profile.get("id") not in server_ids:
                    config_storage.delete_profile(profile["id"])
        except Exception:
            logger.exception("sync configs cleanup")

    def _dispatch(self, cmd: dict):
        logger.info(f"Команда от host: {cmd.get('command')}")
        try:
            # Если ваш main.on_server_command ожидает старую структуру типа {"command": "...", "payload": {...}}
            # Передайте её в правильном формате:
            standardized_cmd = {
                "command": cmd.get("command"),
                "payload": {k: v for k, v in cmd.items() if k != "command"}
            }
            self.main.on_server_command(standardized_cmd)
        except Exception:
            logger.exception("on_server_command")

    def apply_agent_name(self, new_name: str):
        name = (new_name or "").strip()
        if not name:
            return self._sync_agent_name()
        self.agent_name = name
        self.config["agent_name"] = name
        return name

    # ---------- UI ----------

    def _update_status_label(self):
        if self.role == "host":
            self._set_status(
                f"★ HOST (админка): "
                f"http://{self.local_ip}:{self.local_port}/"
            )
        elif self.role == "client" and self.host_url:
            self._set_status(f"Клиент → {self.host_url}")
        else:
            self._set_status(
                f"Ищу главного... (агентов в сети: "
                f"{len(self._known_peers)})"
            )

    # ---------- публичные геттеры ----------

    def get_known_peers(self) -> list:
        return list(self._known_peers.values())

    # ---------- удобства для UI ----------

    def get_admin_url(self) -> str | None:
        """URL админки: если я host — мой, иначе host_url главного."""
        if self.role == "host":
            return f"http://{self.local_ip}:{self.local_port}/"
        return self.host_url

    def get_qr_pixmap(self, size: int = 180):
        """Генерирует QR-код админки как QPixmap (через QPainter, без Pillow).

        Если qrcode недоступен или URL нет — возвращает None.
        """
        url = self.get_admin_url()
        if not url:
            return None
        try:
            import qrcode
            m = qrcode.QRCode(border=1)
            m.add_data(url)
            m.make(fit=True)
            matrix = m.modules  # 2D list of bool
        except Exception:
            return None

        from PyQt5.QtGui import QPixmap, QPainter, QColor
        n = len(matrix)
        pix = QPixmap(size, size)
        pix.fill(QColor("white"))
        p = QPainter(pix)
        p.setPen(QColor("black"))
        p.setBrush(QColor("black"))
        scale = size / (n + 0.0)
        for y, row in enumerate(matrix):
            for x, on in enumerate(row):
                if on:
                    p.drawRect(int(x * scale), int(y * scale),
                               max(1, int(scale) + 1),
                               max(1, int(scale) + 1))
        p.end()
        return pix
