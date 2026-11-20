"""Anti-Game Controller uninstaller.

Cleans up Windows autostart entries, hosts markers, config storage and the
protected runtime copy used by the packaged app.
"""
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path

from autostart_manager import TaskSchedulerManager, AutostartManager, get_protected_runtime_dir
from hosts_manager import unblock_websites
from config_manager import ConfigManager

APP_NAME = "AntiGameController"


def _appdata_root() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / APP_NAME


def _runtime_root() -> Path:
    return Path(get_protected_runtime_dir(APP_NAME))


def _programdata_root() -> Path:
    base = os.environ.get("ProgramData") or os.environ.get("ALLUSERSPROFILE")
    if not base:
        return _runtime_root()
    return Path(base) / APP_NAME


def _remove_path(path: Path):
    if not path.exists():
        return
    if path.is_file() or path.is_symlink():
        try:
            path.unlink()
        except Exception:
            pass
        return
    try:
        shutil.rmtree(path)
    except Exception:
        pass


def _schedule_delete(path: Path):
    if not path.exists():
        return
    quoted = str(path)
    cmd = (
        f'cmd /c "ping 127.0.0.1 -n 2 >nul & '
        f'if exist \"{quoted}\" rmdir /s /q \"{quoted}\""'
    )
    try:
        kwargs = {"shell": True}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(
                subprocess, "CREATE_NO_WINDOW", 0x08000000
            )
        subprocess.Popen(cmd, **kwargs)
    except Exception:
        pass


def _remove_task(task_name: str):
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        )
    except Exception:
        pass


def _remove_firewall_rule():
    try:
        subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "delete", "rule",
                "name=AntiGameController Private Network",
            ],
            capture_output=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        )
    except Exception:
        pass


def _remove_temp_watchdog_copies():
    temp_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".")
    watchdog_dir = temp_root / APP_NAME
    _remove_path(watchdog_dir)

    try:
        for item in temp_root.glob("AGC_*.exe"):
            try:
                item.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _create_uninstall_marker():
    temp_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".")
    marker_dir = temp_root / APP_NAME
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker = marker_dir / "uninstall.pending"
    marker.write_text("uninstall", encoding="ascii")
    return marker


def _schedule_remove_uninstall_marker(marker: Path):
    if not marker.exists():
        return
    quoted = str(marker)
    cmd = (
        f'cmd /c "ping 127.0.0.1 -n 6 >nul & '
        f'del /F /Q \"{quoted}\" >nul 2>&1"'
    )
    try:
        subprocess.Popen(
            cmd,
            shell=True,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        )
    except Exception:
        pass


def _stop_app_and_watchdog():
    try:
        import psutil
    except Exception:
        return

    current_pid = os.getpid()
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            pid = int(proc.info["pid"])
            name = str(proc.info.get("name") or "").lower()
            exe = str(proc.info.get("exe") or "").lower()
            if pid == current_pid:
                continue
            is_app = name == "antigamecontroller.exe"
            is_watchdog = name.startswith("agc_") and name.endswith(".exe")
            is_related_exe = "\\antigamecontroller\\" in exe.replace("/", "\\").lower()
            if is_app or is_watchdog or is_related_exe:
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    try:
        psutil.wait_procs(psutil.process_iter(["pid", "name", "exe"]), timeout=3)
    except Exception:
        pass

    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            pid = int(proc.info["pid"])
            name = str(proc.info.get("name") or "").lower()
            exe = str(proc.info.get("exe") or "").lower()
            if pid == current_pid:
                continue
            if name == "antigamecontroller.exe" or (
                name.startswith("agc_") and name.endswith(".exe")
            ) or "\\antigamecontroller\\" in exe.replace("/", "\\").lower():
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass


def uninstall():
    print("[uninstaller] Cleaning up Anti-Game Controller...")

    uninstall_marker = _create_uninstall_marker()

    # Remove Windows startup hooks.
    _remove_task(f"{APP_NAME}_AutoStart")
    _remove_task(f"{APP_NAME}_OnLogon")
    try:
        TaskSchedulerManager(APP_NAME).delete_startup_task(
            f"{APP_NAME}_OnLogon"
        )
    except Exception:
        pass
    try:
        AutostartManager(APP_NAME).remove_autostart()
    except Exception:
        pass
    _remove_firewall_rule()
    _remove_temp_watchdog_copies()
    uninstall_marker = _create_uninstall_marker()
    _stop_app_and_watchdog()

    # Remove hosts markers and restore the file.
    try:
        unblock_websites()
    except Exception:
        pass

    # Remove app data/config storage.
    cfg = ConfigManager(APP_NAME)
    _remove_path(Path(cfg.config_file))
    _remove_path(Path(cfg.config_dir))
    _remove_path(_appdata_root() / "store")
    _remove_path(_appdata_root() / "network.sqlite3")
    _remove_path(_appdata_root() / "app.lock")
    _remove_path(_appdata_root() / ".profiles.idx")

    # Remove the protected runtime copy if present.
    runtime_root = _runtime_root()
    if getattr(sys, "frozen", False):
        current_exe = Path(sys.executable)
        if current_exe.parent == runtime_root:
            _schedule_delete(runtime_root)
        else:
            _remove_path(runtime_root)
    else:
        _remove_path(runtime_root)

    programdata_root = _programdata_root()
    if programdata_root != runtime_root:
        _remove_path(programdata_root)

    _schedule_remove_uninstall_marker(uninstall_marker)
    # Give deferred deletions a moment to start.
    time.sleep(0.5)
    print("[uninstaller] Done.")


if __name__ == "__main__":
    uninstall()
