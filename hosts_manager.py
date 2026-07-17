import os
import platform

# Определяем путь к файлу hosts в зависимости от ОС
if platform.system() == "Windows":
    HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
else:
    HOSTS_PATH = "/etc/hosts"

REDIRECT_IP = "127.0.0.1"
MARKER_START = "antigamecontroller\n"
MARKER_END = "end\n"


def block_websites(websites):
    """
    Блокирует список сайтов через файл hosts

    Args:
        websites: список доменов для блокировки
    """
    try:
        print(f"[DEBUG block_websites] Блокируем {len(websites)} сайтов")

        # Читаем текущий файл hosts
        if os.path.exists(HOSTS_PATH):
            with open(HOSTS_PATH, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            lines = []

        print(f"[DEBUG block_websites] Прочитано {len(lines)} строк из hosts")

        # Удаляем старый блок Anti-Game и добавляем новый в конце файла
        cleaned_lines = remove_antigame_entries(lines)

        print(
            f"[DEBUG block_websites] После очистки: {len(cleaned_lines)} строк")

        # Добавляем новые записи с явным flush
        with open(HOSTS_PATH, 'w', encoding='utf-8') as f:
            f.writelines(cleaned_lines)

            # Убедимся, что файл заканчивается переводом строки
            if cleaned_lines and not cleaned_lines[-1].endswith('\n'):
                f.write('\n')
                print("[DEBUG block_websites] Добавлен перевод строки перед маркером")

            # Добавляем маркер начала
            f.write(MARKER_START)
            print(
                f"[DEBUG block_websites] Записан MARKER_START: {repr(MARKER_START)}")

            # Добавляем блокировки
            for website in websites:
                # Блокируем основной домен
                f.write(f"{REDIRECT_IP} {website}\n")
                # Блокируем www версию
                if not website.startswith("www."):
                    f.write(f"{REDIRECT_IP} www.{website}\n")

            # Добавляем маркер конца
            f.write(MARKER_END)
            print(
                f"[DEBUG block_websites] Записан MARKER_END: {repr(MARKER_END)}")

            # Принудительная запись на диск
            f.flush()
            os.fsync(f.fileno())

        print("[DEBUG block_websites] Файл hosts обновлён и синхронизирован")

        # Очищаем DNS кэш
        flush_dns_cache()

        # Проверяем результат
        debug_print_hosts()

        print(f"✓ Заблокировано {len(websites)} сайтов")
        return True

    except PermissionError:
        print("✗ Ошибка: нет прав для редактирования файла hosts.")
        print("  Запустите программу от имени администратора!")
        return False
    except Exception as e:
        print(f"✗ Ошибка при блокировке сайтов: {e}")
        import traceback
        traceback.print_exc()
        return False


def unblock_websites(websites=None):
    """
    Разблокирует сайты, удаляя записи из файла hosts

    Args:
        websites: список доменов для разблокировки (если None, удаляются все записи Anti-Game)
    """
    try:
        print(
            f"[DEBUG hosts_manager] unblock_websites вызван с {len(websites) if websites else 0} сайтами")

        if not os.path.exists(HOSTS_PATH):
            print(f"[DEBUG hosts_manager] Файл {HOSTS_PATH} не существует")
            return True

        print(f"[DEBUG hosts_manager] Читаем {HOSTS_PATH}")

        # Читаем файл hosts
        with open(HOSTS_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        print(f"[DEBUG hosts_manager] Прочитано {len(lines)} строк")

        # Удаляем записи Anti-Game
        cleaned_lines = remove_antigame_entries(lines)

        print(
            f"[DEBUG hosts_manager] После очистки осталось {len(cleaned_lines)} строк")

        # Записываем обратно с явным flush
        with open(HOSTS_PATH, 'w', encoding='utf-8') as f:
            f.writelines(cleaned_lines)
            f.flush()  # Принудительная запись на диск
            os.fsync(f.fileno())  # Синхронизация с диском

        print("[DEBUG hosts_manager] Файл hosts обновлён и синхронизирован")

        # Очищаем DNS кэш
        flush_dns_cache()

        # Проверяем результат
        debug_print_hosts()

        print("✓ Сайты разблокированы")
        return True

    except PermissionError:
        print("✗ Ошибка: нет прав для редактирования файла hosts.")
        print("  Запустите программу от имени администратора!")
        return False
    except Exception as e:
        print(f"✗ Ошибка при разблокировке сайтов: {e}")
        import traceback
        traceback.print_exc()
        return False


def remove_antigame_entries(lines):
    """
    Удаляет все записи Anti-Game из списка строк файла hosts

    Args:
        lines: список строк файла hosts

    Returns:
        очищенный список строк
    """
    cleaned = []
    in_block = False
    removed_count = 0
    start_found = False
    end_found = False

    for i, line in enumerate(lines):
        # Сравниваем с удалением пробелов для надежности
        line_stripped = line.strip().lower()

        # Проверяем START маркер
        if line_stripped == MARKER_START.strip():
            in_block = True
            start_found = True
            print(
                f"[DEBUG remove_antigame] Найден MARKER_START на строке {i+1}")
            continue

        # Проверяем END маркер
        elif line_stripped == MARKER_END.strip():
            in_block = False
            end_found = True
            print(
                f"[DEBUG remove_antigame] Найден MARKER_END на строке {i+1}, удалено {removed_count} строк")
            continue

        # Если мы внутри блока Anti-Game
        if in_block:
            # Удаляем любые строки внутри блока, включая адреса и домены
            if line_stripped:
                removed_count += 1
                continue
            else:
                # Если это не запись блокировки, значит блок закончился без END
                # маркера
                in_block = False
                print(
                    f"[DEBUG remove_antigame] Блок закончен без END маркера на строке {i+1}")

        # Добавляем строку только если мы не в блоке
        if not in_block:
            cleaned.append(line)

    print(
        f"[DEBUG remove_antigame] START найден: {start_found}, END найден: {end_found}")
    print(f"[DEBUG remove_antigame] Всего удалено записей: {removed_count}")

    return cleaned


def flush_dns_cache():
    """
    Очищает DNS кэш системы
    """
    try:
        print("[DEBUG flush_dns] Очистка DNS кэша...")
        if platform.system() == "Windows":
            result = os.system("ipconfig /flushdns")
            print(f"[DEBUG flush_dns] ipconfig /flushdns вернул код: {result}")
            if result == 0:
                print("✓ DNS кэш успешно очищен")
            else:
                print("✗ Ошибка при очистке DNS кэша")
        elif platform.system() == "Linux":
            os.system("sudo systemd-resolve --flush-caches 2>/dev/null")
            os.system("sudo service network-manager restart 2>/dev/null")
        elif platform.system() == "Darwin":  # macOS
            os.system("sudo dscacheutil -flushcache 2>/dev/null")
            os.system("sudo killall -HUP mDNSResponder 2>/dev/null")
    except Exception as e:
        print(f"✗ Не удалось очистить DNS кэш: {e}")


def get_blocked_websites():
    """
    Возвращает список заблокированных сайтов из файла hosts

    Returns:
        список заблокированных доменов
    """
    blocked = []

    try:
        if not os.path.exists(HOSTS_PATH):
            return blocked

        with open(HOSTS_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        in_block = False
        for line in lines:
            stripped = line.strip().lower()
            if stripped == MARKER_START.strip():
                in_block = True
                continue
            elif stripped == MARKER_END.strip():
                in_block = False
                continue

            if in_block:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0] == REDIRECT_IP:
                    domain = parts[1]
                    if not domain.startswith("www.") and domain not in blocked:
                        blocked.append(domain)

        return blocked

    except Exception as e:
        print(f"Ошибка при чтении файла hosts: {e}")
        return []


def is_admin():
    """
    Проверяет, запущена ли программа с правами администратора

    Returns:
        True если есть права администратора, иначе False
    """
    try:
        if platform.system() == "Windows":
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.getuid() == 0
    except BaseException:
        return False


def debug_print_hosts():
    """
    Выводит текущее содержимое hosts файла для отладки
    """
    try:
        if not os.path.exists(HOSTS_PATH):
            print("[DEBUG] hosts файл не существует")
            return

        with open(HOSTS_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        print(f"\n[DEBUG] === Содержимое hosts файла ({len(lines)} строк) ===")
        for i, line in enumerate(
                lines[-20:], start=max(1, len(lines) - 19)):  # Последние 20 строк
            print(f"  {i:3d}: {line.rstrip()}")
        print("[DEBUG] === Конец hosts файла ===\n")
    except Exception as e:
        print(f"[DEBUG] Ошибка чтения hosts: {e}")


if __name__ == "__main__":
    # Тест модуля
    print(f"Путь к hosts: {HOSTS_PATH}")
    print(f"Права администратора: {is_admin()}")

    if is_admin():
        print("\nТекущие заблокированные сайты:")
        for site in get_blocked_websites():
            print(f"  - {site}")
    else:
        print("\nДля работы с hosts файлом требуются права администратора!")
