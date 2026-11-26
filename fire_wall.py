import ctypes
import subprocess
import sys

def firewall():
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            try:
                # Убрали DEVNULL, чтобы видеть реальный ответ системы при отладке
                subprocess.run(
                    ["netsh", "advfirewall", "set", "allprofiles", "state", "off"],
                    check=True
                )
                print("Брандмауэр отключён.")
            except subprocess.CalledProcessError as e:
                print(f"Ошибка при отключении брандмауэра: {e}")
        else:
            # Перезапуск скрипта с запросом прав администратора (UAC)
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
    except:
        return False
