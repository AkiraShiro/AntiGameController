"""
Сетевой агент Anti-Game Controller.

Работает ТОЛЬКО в локальной сети. Режим выбирается автоматически (election):
Использует гибридный поиск: Мультикаст (для работы через v2rayN) + Фоновый сканер подсети.
"""
import json
import os
import socket
import time
import threading
import urllib.request
import urllib.error
import uuid
import struct  # Нужен для работы с мультикаст-группами
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
MULTICAST_GROUP = "239.255.255.250" # Стандартный мультикаст-адрес локальной сети


def get_local_ip() -> str:
    """
    Возвращает реальный локальный IPv4-адрес, игнорируя виртуальные подсети и VPN.
    """
    BAD_PREFIXES = ("127.", "0.", "172.0.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.30.", "172.31.")
    
    # 1. Пробуем определить интерфейс по внешнему/сетевому маршруту без отправки данных
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

    # 2. Если внешней сети нет, сканируем локальные адаптеры системными средствами
    try:
        hostname = socket.gethostname()
        infos = socket.gethostbyname_ex(hostname)
        # Сначала ищем стандартные домашние/офисные подсети
        for ip in infos[2]:
            if (ip.startswith("192.168.") or ip.startswith("10.")) and ":" not in ip:
                return ip
        # Если не нашли, берем любой доступный физический
        for ip in infos[2]:
            if not any(ip.startswith(p) for p in BAD_PREFIXES) and ":" not in ip:
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

        self.agent_id = _ensure_agent_id(self.config)
        default_name = f"{get_hostname()}-{self.agent_id[-4:]}"
        self.agent_name = self.config.get("agent_name") or default_name
        self.config["agent_name"] = self.agent_name
        self.started_at = _ensure_started_at(self.config)

        self.local_ip = get_local_ip()
        self.local_port = int(self.config.get("local_port", DEFAULT_PORT))

        self.role = "idle"               
        self.host_url: Optional[str] = None
        self._server = None
        self._known_peers: dict = {}
        self._first_seen_others_ts = 0.0
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

    def start(self):
        if self.running:
            return
        self._sync_agent_name()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        logger.info(f"Agent запущен: id={self.agent_id} name='{self.agent_name}' ip={self.local_ip}")

    def stop(self):
        self.running = False
        self._stop_local_server()

    def _set_status(self, text: str):
        try:
            from PyQt5.QtCore import QTimer
            lbl = getattr(self.main, "net_status_label", None)
            if lbl is not None:
                QTimer.singleShot(0, lambda: lbl.setText(text))
        except Exception:
            pass

    def _loop(self):
        out_sock = self._make_broadcast_socket()
        in_sock = self._make_listen_socket()

        while self.running:
            try:
                now = time.time()
                self.local_ip = get_local_ip()  # Динамически обновляем текущий IP подсети

                is_host_now = (self.role == "host")
                host_url_now = f"http://{self.local_ip}:{self.local_port}/" if is_host_now else (self.host_url or "")
                
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

                if peers and self._first_seen_others_ts == 0.0:
                    self._first_seen_others_ts = now

                self._decide_role(peers, now)

                if self.role in ("host", "client") and self.host_url:
                    if now - self._last_client_tick >= HEARTBEAT_INTERVAL:
                        threading.Thread(target=self._client_tick, daemon=True).start()
                        self._last_client_tick = now

                    if not getattr(self, "_command_thread_active", False):
                        threading.Thread(target=self._command_poll_loop, daemon=True).start()

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

    def _make_broadcast_socket(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        s.settimeout(0.5)
        return s

    def _make_listen_socket(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", DISCOVERY_PORT))
        
        try:
            mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception as e:
            logger.debug(f"Не удалось подписаться на мультикаст: {e}")
            
        s.settimeout(0.5)
        return s

    def _broadcast(self, sock: socket.socket, pkt: dict):
        try:
            data = json.dumps(pkt).encode("utf-8")
            sock.sendto(data, (MULTICAST_GROUP, DISCOVERY_PORT))
        except Exception as e:
            logger.debug(f"multicast broadcast error: {e}")

    def _collect_announces(self, sock: socket.socket, timeout: float) -> list:
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
                if pkt.get("magic") == DISCOVERY_MAGIC and pkt.get("agent_id") != self.agent_id:
                    peers.append(pkt)
            except Exception:
                continue
        return peers

    def _scan_for_host(self):
        """Быстрый фоновый перебор всей локальной подсети любой конфигурации."""
        if self.host_url or self.role == "host":
            return
            
        local_ip = get_local_ip()
        if local_ip == "127.0.0.1":
            return
            
        base_net = ".".join(local_ip.split(".")[:3]) + "."

        def check_ip(ip_str):
            if self.host_url or self.role == "host":
                return
            url = f"http://{ip_str}:{self.local_port}/api/agents/{self.agent_id}/heartbeat"
            try:
                req = urllib.request.Request(url, method="POST", headers={"Connection": "close"})
                with urllib.request.urlopen(req, timeout=0.8) as r:
                    if r.getcode() == 200 and not self.host_url:
                        self.host_url = f"http://{ip_str}:{self.local_port}/"
                        self.role = "client"
                        logger.info(f"Фоновый сканер успешно обнаружил хост: {self.host_url}")
            except Exception:
                pass

        # Сканируем весь диапазон хостов подсети (от 1 до 254)
        for i in range(1, 255):
            if self.host_url or self.role == "host": 
                break
            threading.Thread(target=check_ip, args=(f"{base_net}{i}",), daemon=True).start()

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

            def started_key(p):
                sat = p.get("started_at") or 0.0
                if sat and sat > 0:
                    return (0, float(sat), p.get("agent_id") or "")
                return (1, 0.0, p.get("agent_id") or "")

            if live_hosts:
                live_hosts.sort(key=started_key)
                best = live_hosts[0]
                self._last_host_seen = now
                self._first_seen_others_ts = 0.0

                # Если мы УЖЕ выступаем хостом и виден другой хост — уступаем только если мы не были первыми
                if self.role == "host":
                    if self.agent_id == best["agent_id"]:
                        return
                    logger.info(f"Обнаружен другой хост {best['agent_name']}. Перехожу в режим клиента.")
                    self._stop_local_server()
                    self.role = "client"
                    self.host_url = best.get("host_url") or self.host_url
                    self._command_cursor = 0.0
                    self._command_thread_active = False
                    return
                
                if self.host_url != best.get("host_url"):
                    logger.info("Хост изменился. Сбрасываем курсор команд.")
                    self._command_cursor = 0.0
                    self._command_thread_active = False

                self.host_url = best.get("host_url") or self.host_url
                if self.role != "client":
                    logger.info(f"Нашёл host {best['agent_name']} → становлюсь клиентом")
                self.role = "client"
                return

            if (self.role == "client"
                    and self.host_url
                    and self._last_host_seen > 0
                    and now - self._last_host_seen > MISSING_HOST_TIMEOUT):
                logger.warning(f"Host {self.host_url} не отвечает — запускаю election")
                self.host_url = None

            # Если мы уже хост и других хостов нет — сохраняем роль без перевыборов
            if self.role == "host":
                return

            if not live_clients:
                logger.info(f"Я первый в сети → становлюсь HOST (http://{self.local_ip}:{self.local_port}/)")
                self._start_local_server()
                self.role = "host"
                self.host_url = f"http://{self.local_ip}:{self.local_port}/"
                self._first_seen_others_ts = 0.0
                return

            if self._first_seen_others_ts == 0.0:
                self._first_seen_others_ts = now
            elapsed = now - self._first_seen_others_ts
            
            if elapsed >= GRACE_PERIOD and not self.host_url:
                self._scan_for_host()
                
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
                logger.info("Election: я — новый HOST")
                self._start_local_server()
                self.role = "host"
                self.host_url = f"http://{self.local_ip}:{self.local_port}/"
                self._first_seen_others_ts = 0.0
            else:
                self.role = "client"
                self.host_url = None 

    def _start_local_server(self):
        if self._server is not None:
            return
        try:
            from network_server import start_local_server, Store
            db_path = os.path.join(os.environ.get("APPDATA", "."), "AntiGameController", "network.sqlite3")
            self._db_path = db_path
            try:
                self._local_store = Store(db_path)
            except Exception:
                self._local_store = None
            password_hash = None
            if isinstance(self.config, dict):
                password_hash = self.config.get("password_hash")
            self._server = start_local_server(self.local_port, db_path, password_hash)
            if self._server is None:
                self._server = start_local_server(self.local_port + 1, db_path, password_hash)
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

    def _client_tick(self):
        try:
            heartbeat_data = self._heartbeat()
            self._sync_configs(heartbeat_data.get("configs") if isinstance(heartbeat_data, dict) else None)
        except urllib.error.URLError as e:
            logger.warning(f"host недоступен: {e.reason}")
        except Exception as e:
            logger.exception(f"client_tick error: {e}")

        if not getattr(self, "_command_thread_active", False):
            threading.Thread(target=self._command_poll_loop, daemon=True).start()

    def _command_poll_loop(self):
        if getattr(self, "_command_thread_active", False):
            return
        self._command_thread_active = True
        consecutive_failures = 0
        
        try:
            while self.running:
                if not getattr(self, "_command_thread_active", False):
                    break
                if not (self.role in ("host", "client") and self.host_url):
                    time.sleep(1.0)
                    continue
                try:
                    if self.role == "host" and getattr(self, "_db_path", None):
                        cmds = self._fetch_local_commands()
                        consecutive_failures = 0
                    else:
                        cmds = self._poll_commands()
                        if cmds is None:
                            raise urllib.error.URLError("Ошибка сети или пустой ответ от хоста")
                        consecutive_failures = 0
                    
                    for c in cmds:
                        self._dispatch(c)
                        
                except urllib.error.URLError as e:
                    consecutive_failures += 1
                    logger.warning(f"poll commands: host недоступен; попытка {consecutive_failures}")
                    # Даем запасы на временные просадки Wi-Fi сети (5 попыток с паузой)
                    if consecutive_failures >= 5:
                        logger.warning("host не отвечает 5 попыток подряд — запускаю election")
                        self.host_url = None
                    time.sleep(3.0)
                except Exception as e:
                    logger.error(f"poll commands cycle error: {e}")
                    time.sleep(3.0)
        finally:
            self._command_thread_active = False

    def _fetch_local_commands(self):
        try:
            store = getattr(self, "_local_store", None)
            if store is None:
                from network_server import Store
                store = Store(self._db_path)
                self._local_store = store
            cmds, new_since = store.fetch_commands(self.agent_id, int(self._command_cursor or 0))
            try:
                self._command_cursor = max(float(self._command_cursor or 0.0), float(new_since or 0.0))
            except Exception:
                self._command_cursor = float(new_since or 0.0)
            return [{"command": c["command"], **c["payload"]} for c in cmds]
        except Exception as e:
            logger.debug(f"local fetch commands: {e}")
            return []

    def _poll_commands(self):
        url = f"{self.host_url}api/agents/{self.agent_id}/commands?since={self._command_cursor}"
        data = self._http_json("GET", url, timeout=35)
        if data is None:
            return []
        self._command_cursor = max(self._command_cursor, float(data.get("server_ts") or self._command_cursor))
        return data.get("commands", [])

    def _http_json(self, method: str, url: str, body=None, timeout: int = 8):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json", "Connection": "close"}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                response_data = r.read()
                if not response_data:
                    return None
                return json.loads(response_data.decode("utf-8"))
        except Exception as e:
            logger.debug(f"HTTP request error ({method} {url}): {e}")
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
            config_storage.save_config_with_id(config_id, cfg.get("name") or "Без названия", body, source="server")

        try:
            for profile in config_storage.list_profiles():
                if profile.get("source") == "server" and profile.get("id") not in server_ids:
                    config_storage.delete_profile(profile["id"])
        except Exception:
            logger.exception("sync configs cleanup")

    def _dispatch(self, cmd: dict):
        logger.info(f"Команда от host: {cmd.get('command')}")
        try:
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

    def _update_status_label(self):
        if self.role == "host":
            self._set_status(f"★ HOST (админка): http://{self.local_ip}:{self.local_port}/")
        elif self.role == "client" and self.host_url:
            self._set_status(f"Клиент → {self.host_url}")
        else:
            self._set_status(f"Ищу главного... (агентов в сети: {len(self._known_peers)})")

    def get_known_peers(self) -> list:
        return list(self._known_peers.values())

    def get_admin_url(self) -> str | None:
        if self.role == "host":
            return f"http://{self.local_ip}:{self.local_port}/"
        return self.host_url

    def get_qr_pixmap(self, size: int = 180):
        url = self.get_admin_url()
        if not url:
            return None
        try:
            import qrcode
            m = qrcode.QRCode(border=1)
            m.add_data(url)
            m.make(fit=True)
            matrix = m.modules
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
                    p.drawRect(int(x * scale), int(y * scale), max(1, int(scale) + 1), max(1, int(scale) + 1))
        p.end()
        return pix