import os
import sys
import subprocess
import shutil
import winreg

from logger import get_logger

logger = get_logger("Autostart")

ENABLE_AUTOSTART = True


def _hidden_kwargs() -> dict:
    """Возвращает kwargs для subprocess, которые скрывают консоль на Windows."""
    if os.name != "nt":
        return {}
    kwargs = {
        "creationflags": getattr(
            subprocess, "CREATE_NO_WINDOW", 0x08000000
        ),
    }
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = si
    except Exception:
        pass
    return kwargs


def get_protected_runtime_dir(app_name="AntiGameController"):
    base_dir = os.environ.get("ProgramData") or os.environ.get("APPDATA")
    if not base_dir:
        base_dir = os.path.expanduser("~")
    runtime_dir = os.path.join(base_dir, app_name)
    os.makedirs(runtime_dir, exist_ok=True)
    return runtime_dir


def get_protected_runtime_exe_path(app_name="AntiGameController"):
    return os.path.join(get_protected_runtime_dir(app_name), f"{app_name}.exe")


def ensure_protected_runtime_copy(app_name="AntiGameController"):
    if not getattr(sys, "frozen", False):
        return os.path.abspath(sys.argv[0])

    source_exe = os.path.abspath(sys.executable)
    target_exe = get_protected_runtime_exe_path(app_name)

    try:
        source_mtime = os.path.getmtime(source_exe)
        target_mtime = os.path.getmtime(target_exe) if os.path.exists(target_exe) else 0
        if (not os.path.exists(target_exe)) or source_mtime > target_mtime:
            shutil.copy2(source_exe, target_exe)
        return target_exe
    except Exception:
        return source_exe


def _detect_current_sid():
    try:
        out = subprocess.check_output(
            ["cmd", "/c", "whoami", "/user"],
            stderr=subprocess.DEVNULL,
            text=True,
            **_hidden_kwargs(),
        )
        for line in out.splitlines():
            parts = line.strip().split()
            if parts and parts[-1].startswith("S-1-5-"):
                return parts[-1]
    except Exception:
        pass
    try:
        return os.getlogin()
    except Exception:
        return "UNKNOWN_USER"


SID_USER = _detect_current_sid()


class TaskSchedulerManager:
    def __init__(self, app_name="AntiGameController"):
        self.app_name = app_name
        self.task_name = f"{app_name}_AutoStart"

    def _get_target_command(self):
        """Возвращает команду для schtasks /TR.

        schtasks /TR интерпретирует аргументы по пробелам, поэтому путь
        ОБЯЗАТЕЛЬНО оборачивается в двойные кавычки. Без кавычек путь
        вида `C:\\Program Files\\App\\app.exe` запускается как
        `C:\\Program` с аргументом `Files\\App\\app.exe` — задача
        мгновенно падает с ошибкой и планировщик её не перезапускает.
        """
        if getattr(sys, "frozen", False):
            target = ensure_protected_runtime_copy(self.app_name)
            # /TR любит экранированные кавычки внутри значения
            return f'"{target}"'
        return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'

    def is_task_exists(self):
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", self.task_name],
                capture_output=True,
                text=True,
                timeout=10,
                **_hidden_kwargs(),
            )
            return result.returncode == 0
        except Exception:
            return False

    def create_startup_task(self):
        if not ENABLE_AUTOSTART:
            return False
        try:
            self.delete_startup_task()

            target = self._get_target_command()

            # Берём XML-путь: он надёжнее CLI, потому что позволяет задать
            # несколько триггеров (ONSTART + MINUTE повтор) одной задачей,
            # а ещё корректно экранирует пути с пробелами.
            #
            # Не используем /RU <user> потому что schtasks при включённом
            # UAC требует пароль текущего пользователя. Запускаем от SYSTEM
            # (по умолчанию, когда /RU не задан) — SYSTEM-процессу не нужен
            # пароль и он спокойно стартует при любом состоянии сессии.
            # GUI PyQt-программа под SYSTEM запустится без отображения окна
            # на desktop интерактивной сессии, поэтому дополнительно
            # используем ONLOGON-триггер, который срабатывает при входе
            # пользователя и работает в его сессии.
            task_name_secondary = f"{self.app_name}_OnLogon"
            self.delete_startup_task(task_name_secondary)

            xml = self._build_task_xml(target, task_name_secondary)
            xml_path = os.path.join(
                get_protected_runtime_dir(self.app_name),
                "task_logon.xml",
            )
            with open(xml_path, "w", encoding="utf-16") as f:
                f.write(xml)

            # Создаём primary task (каждые 5 минут).
            cmd_primary = [
                "schtasks", "/Create",
                "/TN", self.task_name,
                "/SC", "MINUTE",
                "/MO", "1",         # 1 минута — быстрее реакция на падение
                "/RL", "HIGHEST",
                "/F",
                "/TR", target,
            ]
            r1 = subprocess.run(
                cmd_primary,
                capture_output=True, text=True, timeout=30,
                **_hidden_kwargs(),
            )

            # Создаём secondary task через XML — ONLOGON + повтор каждые 5 минут,
            # чтобы при входе пользователя программа сразу запускалась в его
            # сессии, и каждые 5 минут проверялась.
            cmd_secondary = [
                "schtasks", "/Create",
                "/TN", task_name_secondary,
                "/XML", xml_path,
                "/F",
            ]
            r2 = subprocess.run(
                cmd_secondary,
                capture_output=True, text=True, timeout=30,
                **_hidden_kwargs(),
            )

            try:
                os.remove(xml_path)
            except OSError:
                pass

            if r1.returncode != 0:
                logger.error(
                    "schtasks primary failed: rc=%s stderr=%s",
                    r1.returncode, (r1.stderr or "")[:300],
                )
            if r2.returncode != 0:
                logger.error(
                    "schtasks ONLOGON failed: rc=%s stderr=%s",
                    r2.returncode, (r2.stderr or "")[:300],
                )
            return r1.returncode == 0 or r2.returncode == 0
        except Exception:
            logger.exception("create_startup_task")
            return False

    def _build_task_xml(self, target: str, task_name: str) -> str:
        """XML-описание задачи с двумя триггерами:
        1) запуск при входе пользователя (ONLOGON),
        2) повтор каждые 5 минут (чтобы подхватить падение).
        """
        # schtasks требует XML в UTF-16 LE с BOM. Триггеры:
        #   LogonTrigger    — при входе любого пользователя.
        #   TimeTrigger     — повтор каждые 5 минут от начала суток.
        return (
            '<?xml version="1.0" encoding="UTF-16"?>\r\n'
            '<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\r\n'
            '  <RegistrationInfo>\r\n'
            f'    <Description>{self.app_name} autostart</Description>\r\n'
            '  </RegistrationInfo>\r\n'
            '  <Triggers>\r\n'
            '    <LogonTrigger>\r\n'
            '      <Enabled>true</Enabled>\r\n'
            '    </LogonTrigger>\r\n'
            '    <TimeTrigger>\r\n'
            '      <Enabled>true</Enabled>\r\n'
            '      <Repetition>\r\n'
            '        <Interval>PT5M</Interval>\r\n'
            '        <StopAtDurationEnd>false</StopAtDurationEnd>\r\n'
            '      </Repetition>\r\n'
            '    </TimeTrigger>\r\n'
            '  </Triggers>\r\n'
            '  <Principals>\r\n'
            '    <Principal id="Author">\r\n'
            '      <Group>S-1-5-4</Group>\r\n'
            '      <RunLevel>HighestAvailable</RunLevel>\r\n'
            '    </Principal>\r\n'
            '  </Principals>\r\n'
            '  <Settings>\r\n'
            '    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\r\n'
            '    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\r\n'
            '    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\r\n'
            '    <AllowHardTerminate>true</AllowHardTerminate>\r\n'
            '    <StartWhenAvailable>true</StartWhenAvailable>\r\n'
            '    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>\r\n'
            '    <IdleSettings>\r\n'
            '      <StopOnIdleEnd>false</StopOnIdleEnd>\r\n'
            '      <RestartOnIdle>false</RestartOnIdle>\r\n'
            '    </IdleSettings>\r\n'
            '    <AllowStartOnDemand>true</AllowStartOnDemand>\r\n'
            '    <Enabled>true</Enabled>\r\n'
            '    <Hidden>false</Hidden>\r\n'
            '    <RunOnlyIfIdle>false</RunOnlyIfIdle>\r\n'
            '    <WakeToRun>false</WakeToRun>\r\n'
            '    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>\r\n'
            '    <Priority>5</Priority>\r\n'
            '  </Settings>\r\n'
            '  <Actions>\r\n'
            '    <Exec>\r\n'
            f'      <Command>{target}</Command>\r\n'
            '    </Exec>\r\n'
            '  </Actions>\r\n'
            '</Task>\r\n'
        )

    def delete_startup_task(self, task_name: str | None = None):
        tn = task_name or self.task_name
        try:
            result = subprocess.run(
                ["schtasks", "/Delete", "/TN", tn, "/F"],
                capture_output=True,
                text=True,
                timeout=10,
                **_hidden_kwargs(),
            )
            return result.returncode == 0 or True
        except Exception:
            return False

    def run_task_now(self):
        try:
            result = subprocess.run(
                ["schtasks", "/Run", "/TN", self.task_name],
                capture_output=True,
                text=True,
                timeout=10,
                **_hidden_kwargs(),
            )
            return result.returncode == 0
        except Exception:
            return False


class AutostartManager:
    def __init__(self, app_name="AntiGameController"):
        self.app_name = app_name
        self.registry_key = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def _get_target_command(self):
        if getattr(sys, "frozen", False):
            return ensure_protected_runtime_copy(self.app_name)
        return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'

    def set_autostart(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.registry_key,
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, self._get_target_command())
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def remove_autostart(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.registry_key,
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.DeleteValue(key, self.app_name)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def is_autostart_enabled(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.registry_key,
                0,
                winreg.KEY_READ,
            )
            winreg.QueryValueEx(key, self.app_name)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False