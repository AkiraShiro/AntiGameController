"""
Автообновление через GitHub Releases.

Логика:
1. При запуске и периодически (раз в N часов) проверяем
   GET https://api.github.com/repos/{owner}/{repo}/releases/latest
2. Сравниваем тег с сохранённым в конфиге installed_version.
3. Если есть новая версия и включён auto_update -> скачиваем .exe и
   запускаем updater.bat, который:
   - дождётся, пока текущий EXE закроется
   - заменит файл на новый
   - запустит его
4. Если включён auto_update=False -> уведомление в UI, ручной апдейт.

Используется чистый stdlib (urllib.request), без внешних зависимостей.
"""
import os
import sys
import json
import time
import shutil
import tempfile
import threading
import urllib.request
import subprocess
import ssl
from logger import get_logger
from version import CURRENT_VERSION


def _hidden_startupinfo():
    """STARTUPINFO, которая скрывает дочернее консольное окно на Windows."""
    if os.name != "nt":
        return None
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        return si
    except Exception:
        return None


logger = get_logger("Updater")

CHECK_INTERVAL = 6 * 3600   # 6 часов
GITHUB_REPOSITORY = "AkiraShiro/antigamecontroller"


class AutoUpdater:
    def __init__(self, config: dict, main_window=None):
        self.config = config
        self.main = main_window
        self.running = False
        self.thread: threading.Thread | None = None

    # ----- публичный API -----

    def start(self):
        if self.running:
            return
        if not self.config.get("auto_update", True):
            logger.info("Автообновление отключено в конфиге")
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def check_now(self):
        """Принудительная проверка (для UI-кнопки)."""
        try:
            info = self._fetch_release()
            self._maybe_apply(info)
            return True, info
        except Exception as e:
            logger.error(f"Проверка обновлений не удалась: {e}")
            return False, {"error": str(e)}

    # ----- фоновый цикл -----

    def _loop(self):
        while self.running:
            try:
                info = self._fetch_release()
                self._maybe_apply(info)
            except Exception as e:
                logger.debug(f"updater tick: {e}")
            time.sleep(CHECK_INTERVAL)

    # ----- GitHub API & SSL -----

    def _get_ssl_context(self):
        """Контекст без проверки SSL (обход CERTIFICATE_VERIFY_FAILED)."""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _api_url(self) -> str:
        repo = GITHUB_REPOSITORY
        if not repo or "/" not in repo:
            raise ValueError(
                "github_repo не задан (формат: 'owner/repo')"
            )
        return f"https://api.github.com/repos/{repo}/releases/latest"

    def _fetch_release(self) -> dict:
        url = self._api_url()
        req = urllib.request.Request(url, headers={
            "User-Agent": "AntiGameController-Updater",
            "Accept": "application/vnd.github+json",
        })
        context = self._get_ssl_context()
        with urllib.request.urlopen(req, timeout=15, context=context) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data

    def _maybe_apply(self, release: dict):
        tag = (release.get("tag_name") or "").lstrip("v")
        current = self.config.get("installed_version", CURRENT_VERSION)
        if not tag:
            return

        # НОВЫЙ КОД: Функция для правильного парсинга версий
        import re
        def parse_v(version_str):
            # Извлекаем все числа из строки версии. "0.11" превратится в (0, 11)
            return tuple(map(int, re.findall(r'\d+', str(version_str))))

        # Если версия на GitHub меньше или равна текущей, то ничего не скачиваем
        if parse_v(tag) <= parse_v(current):
            logger.debug(f"Уже установлена актуальная или более новая версия (текущая: {current}, на сервере: {tag})")
            return

        logger.info(f"Доступна новая версия: {tag} (текущая {current})")
        asset = self._pick_asset(release)
        if not asset:
            logger.warning("В релизе нет подходящего .exe-ассета")
            return
        if not self.config.get("auto_update", True):
            self._notify_new_version(tag, release.get("html_url"))
            return
        self._download_and_replace(asset["browser_download_url"], tag)

    def _pick_asset(self, release: dict) -> dict | None:
        """Ищет .exe, желательно с 'AntiGame' в имени."""
        assets = release.get("assets", [])
        cands = [a for a in assets if a["name"].lower().endswith(".exe")]
        if not cands:
            return None
        for a in cands:
            if "antigame" in a["name"].lower():
                return a
        return cands[0]

    # ----- скачивание и замена -----

    def _download_and_replace(self, url: str, new_version: str):
        logger.info(f"Скачиваю обновление {new_version}...")
        
        # Сохраняем в фиксированную папку во временном хранилище
        download_dir = os.path.join(tempfile.gettempdir(), "antigame_updates")
        os.makedirs(download_dir, exist_ok=True)
        new_exe = os.path.join(download_dir, f"update_{new_version}.exe")

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AntiGameController-Updater"})
            context = self._get_ssl_context()
            
            with urllib.request.urlopen(req, context=context) as response, open(new_exe, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
                
            self._run_updater_bat(new_exe, new_version)
        except Exception as e:
            logger.error(f"Скачивание/замена не удались: {e}")

    def _run_updater_bat(self, new_exe: str, new_version: str):
        """Создаёт .bat, который заменит текущий EXE и перезапустит."""
        if getattr(sys, "frozen", False):
            current_exe = sys.executable
        else:
            current_exe = os.path.abspath(sys.argv[0])

        bat_path = os.path.join(tempfile.gettempdir(), "antigame_updater.bat")
        
        # Скрипт ждет завершения процесса, подменяет exe, запускает его и чистит за собой мусор.
        # ВАЖНО: set _MEIPASS= сбрасывает путь к старой временной папке PyInstaller.
        script = f"""@echo off
chcp 65001 > nul
set _MEIPASS=
set _MEIPASS2=
timeout /t 2 /nobreak > nul
:waitloop
tasklist /FI "IMAGENAME eq {os.path.basename(current_exe)}" 2>NUL | find /I "{os.path.basename(current_exe)}" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak > nul
    goto waitloop
)
copy /Y "{new_exe}" "{current_exe}" > nul
start "" "{current_exe}"
del /Q "{new_exe}" > nul
del /Q "{bat_path}"
"""
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(script)

        # Запоминаем версию
        self.config["installed_version"] = new_version

        logger.info(f"Запускаю updater.bat для замены на {new_version}")
        try:
            kwargs = {"shell": False, "close_fds": True}
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                kwargs["startupinfo"] = _hidden_startupinfo()
            
            # Удаляем переменные PyInstaller из передаваемого окружения
            env = os.environ.copy()
            env.pop("_MEIPASS", None)
            env.pop("_MEIPASS2", None)

            # Очищаем PATH от старой папки PyInstaller во избежание ошибки DLL
            if hasattr(sys, '_MEIPASS'):
                meipass_dir = sys._MEIPASS
                path_list = env.get("PATH", "").split(os.pathsep)
                # Оставляем только те пути, которые не совпадают со старым _MEIPASS
                path_list = [p for p in path_list if p.lower() != meipass_dir.lower()]
                env["PATH"] = os.pathsep.join(path_list)

            subprocess.Popen(["cmd", "/c", bat_path], env=env, **kwargs)
            
            # Завершаем текущее приложение, чтобы освободить .exe файл для копирования
            logger.info("Завершаем процесс для проведения обновления...")
            os._exit(0)

        except Exception as e:
            logger.error(f"Не удалось запустить updater.bat: {e}")

    # ----- UI уведомление -----

    def _notify_new_version(self, tag: str, html_url: str | None):
        """Показывает уведомление в главном окне (если есть)."""
        if not self.main:
            return
        try:
            from PyQt5.QtCore import QMetaObject, Q_ARG, Qt
            # Безопасный вызов окна из фонового потока в основной поток GUI
            QMetaObject.invokeMethod(
                self.main,
                "show_update_notification",
                Qt.QueuedConnection,
                Q_ARG(str, tag),
                Q_ARG(str, html_url or "")
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление в UI: {e}")