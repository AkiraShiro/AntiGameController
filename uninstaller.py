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


def uninstall():
    print("[uninstaller] Cleaning up Anti-Game Controller...")

    # Remove Windows startup hooks.
    try:
        TaskSchedulerManager(APP_NAME).delete_startup_task()
    except Exception:
        pass
    try:
        AutostartManager(APP_NAME).remove_autostart()
    except Exception:
        pass

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

    # Give deferred deletions a moment to start.
    time.sleep(0.5)
    print("[uninstaller] Done.")


if __name__ == "__main__":
    uninstall()
