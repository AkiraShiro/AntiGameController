"""
Автообновление через GitHub Releases.

Логика:
1. При запуске и периодически (раз в N часов) проверяем
   GET https://api.github.com/repos/{owner}/{repo}/releases/latest
2. Сравниваем тег с сохранённым в конфиге installed_version.
3. Если есть новая версия и включён auto_update → скачиваем .exe и
   запускаем updater.bat, который:
   - дождётся, пока текущий EXE закроется
   - заменит файл на новый
   - запустит его
4. Если включён auto_update=False — уведомление в UI, ручной апдейт.

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

from logger import get_logger


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
        if not self.config.get("github_repo"):
            logger.info("github_repo не задан, автообновление выключено")
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

    # ----- GitHub API -----

    def _api_url(self) -> str:
        repo = self.config.get("github_repo", "").strip()
        if not repo or "/" not in repo:
            raise ValueError(
                "github_repo не задан (формат: 'owner/repo')"
            )
        # Если указан файл .exe → скачиваем его, иначе первый asset
        return (
            f"https://api.github.com/repos/{repo}/releases/latest"
        )

    def _fetch_release(self) -> dict:
        url = self._api_url()
        req = urllib.request.Request(url, headers={
            "User-Agent": "AntiGameController-Updater",
            "Accept": "application/vnd.github+json",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data

    def _maybe_apply(self, release: dict):
        tag = (release.get("tag_name") or "").lstrip("v")
        current = self.config.get("installed_version", "1.0.0")
        if not tag:
            return
        if tag == current:
            logger.debug(f"Уже установлена актуальная версия {tag}")
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
        tmp_dir = tempfile.mkdtemp(prefix="antigame_update_")
        try:
            new_exe = os.path.join(tmp_dir, "AntiGameController.new.exe")
            urllib.request.urlretrieve(url, new_exe)
            self._run_updater_bat(new_exe, new_version)
        except Exception as e:
            logger.error(f"Скачивание/замена не удались: {e}")
        finally:
            # updater.bat сам всё почистит; если не сможет — оставим
            pass

    def _run_updater_bat(self, new_exe: str, new_version: str):
        """Создаёт .bat, который заменит текущий EXE и перезапустит."""
        if getattr(sys, "frozen", False):
            current_exe = sys.executable
        else:
            current_exe = os.path.abspath(sys.argv[0])

        bat_path = os.path.join(tempfile.gettempdir(),
                                "antigame_updater.bat")
        script = f"""@echo off
chcp 65001 > nul
timeout /t 3 /nobreak > nul
:waitloop
tasklist /FI "IMAGENAME eq {os.path.basename(current_exe)}" 2>NUL | find /I "{os.path.basename(current_exe)}" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 2 /nobreak > nul
    goto waitloop
)
copy /Y "{new_exe}" "{current_exe}" > nul
start "" "{current_exe}"
del /Q "{bat_path}"
"""
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(script)

        # Запоминаем версию, чтобы не качать повторно
        self.config["installed_version"] = new_version

        logger.info(
            f"Запускаю updater.bat для замены на {new_version}"
        )
        try:
            # Запускаем .bat полностью в фоне: на Windows
            # обязателен creationflags=CREATE_NO_WINDOW иначе
            # мигнёт чёрное окно консоли.
            kwargs = {"shell": False, "close_fds": True}
            if os.name == "nt":
                kwargs["creationflags"] = (
                    getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                )
                kwargs["startupinfo"] = _hidden_startupinfo()
            subprocess.Popen(["cmd", "/c", bat_path], **kwargs)
        except Exception as e:
            logger.error(f"Не удалось запустить updater.bat: {e}")

    # ----- UI уведомление -----

    def _notify_new_version(self, tag: str, html_url: str | None):
        """Показывает уведомление в главном окне (если есть)."""
        if not self.main:
            return
        try:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(
                self.main,
                "Доступно обновление",
                f"Новая версия: v{tag}\n\n"
                f"Автообновление отключено — обновите вручную:\n"
                f"{html_url or 'см. релизы на GitHub'}",
            )
        except Exception:
            pass