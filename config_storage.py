"""
Скрытое хранилище конфигов в AppData.
Каждый импортированный/экспортированный конфиг сохраняется в отдельный файл
с UUID-именем без расширения в скрытой подпапке AppData.

Удалить эти файлы обычному пользователю сложнее, чем config.json рядом с EXE.
"""
import os
import json
import uuid
import ctypes

APP_NAME = "AntiGameController"


def _set_hidden(path: str) -> None:
    """Делает файл/папку скрытым в Windows"""
    if os.name == "nt":
        try:
            ctypes.windll.kernel32.SetFileAttributesW(path, 0x02)
        except Exception:
            pass


def _storage_root() -> str:
    """Возвращает путь к скрытой папке хранилища конфигов"""
    if os.name == "nt":
        app_data = os.getenv("APPDATA") or os.path.expanduser("~")
        root = os.path.join(app_data, APP_NAME, "store")
    else:
        root = os.path.join(
            os.path.expanduser("~"), f".{APP_NAME.lower()}", "store"
        )

    if not os.path.exists(root):
        os.makedirs(root, exist_ok=True)
        _set_hidden(root)

    # Гарантируем, что скрытый атрибут стоит (на случай если папку создали извне)
    _set_hidden(root)

    return root


def _visible_index_path() -> str:
    """
    Видимый (но скрытый) файл-индекс рядом с .config.dat
    Здесь хранятся человекочитаемые имена и UUID.
    """
    if os.name == "nt":
        app_data = os.getenv("APPDATA") or os.path.expanduser("~")
        d = os.path.join(app_data, APP_NAME)
    else:
        d = os.path.join(os.path.expanduser("~"), f".{APP_NAME.lower()}")

    os.makedirs(d, exist_ok=True)
    return os.path.join(d, ".profiles.idx")


def _load_index() -> dict:
    """Загружает индекс профилей: {uuid: {name, created}}"""
    p = _visible_index_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_index(index: dict) -> bool:
    """Сохраняет индекс профилей"""
    p = _visible_index_path()
    try:
        # Снимаем hidden для записи
        if os.name == "nt" and os.path.exists(p):
            try:
                ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
            except Exception:
                pass
        with open(p, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        if os.name == "nt":
            _set_hidden(p)
        return True
    except Exception as e:
        print(f"[config_storage] Ошибка сохранения индекса: {e}")
        return False


def _write_profile(profile_id: str, profile_name: str, config: dict, source: str) -> str:
    root = _storage_root()
    target = os.path.join(root, profile_id)

    with open(target, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    if os.name == "nt":
        _set_hidden(target)

    index = _load_index()
    index[profile_id] = {
        "name": profile_name,
        "created": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "source": source,
    }
    _save_index(index)
    return profile_id


def save_config(profile_name: str, config: dict) -> str:
    """
    Сохраняет конфиг в хранилище под UUID.
    Возвращает UUID сохранённого профиля.
    """
    root = _storage_root()
    profile_id = uuid.uuid4().hex

    try:
        _write_profile(profile_id, profile_name, config, "local")
        return profile_id
    except Exception as e:
        print(f"[config_storage] Ошибка сохранения конфига '{profile_name}': {e}")
        return ""


def save_config_with_id(profile_id: str, profile_name: str, config: dict, source: str = "server") -> str:
    """Сохраняет конфиг с заданным UUID, не меняя его при повторной синхронизации."""
    try:
        return _write_profile(profile_id, profile_name, config, source)
    except Exception as e:
        print(f"[config_storage] Ошибка сохранения конфига '{profile_name}' ({profile_id}): {e}")
        return ""


def load_config(profile_id: str) -> dict | None:
    """Загружает конфиг по UUID. Возвращает None если не найден."""
    root = _storage_root()
    target = os.path.join(root, profile_id)
    if not os.path.exists(target):
        return None
    try:
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[config_storage] Ошибка чтения профиля {profile_id}: {e}")
        return None


def list_profiles() -> list[dict]:
    """
    Возвращает список профилей: [{"id": ..., "name": ..., "created": ...}, ...]
    Сортировка: новые сверху.
    """
    index = _load_index()
    items = []
    root = _storage_root()
    for pid, info in index.items():
        # Фильтруем битые записи (файл удалили)
        if os.path.exists(os.path.join(root, pid)):
            items.append({"id": pid, **info})
    items.sort(key=lambda x: x.get("created", ""), reverse=True)
    return items


def delete_profile(profile_id: str) -> bool:
    """Удаляет профиль конфига по UUID"""
    root = _storage_root()
    target = os.path.join(root, profile_id)
    try:
        if os.path.exists(target):
            # Снимаем hidden, чтобы можно было удалить
            if os.name == "nt":
                try:
                    ctypes.windll.kernel32.SetFileAttributesW(target, 0x80)
                except Exception:
                    pass
            os.remove(target)
        index = _load_index()
        index.pop(profile_id, None)
        _save_index(index)
        return True
    except Exception as e:
        print(f"[config_storage] Ошибка удаления профиля: {e}")
        return False


def export_to_clipboard_or_file(config: dict, file_path: str | None = None) -> str:
    """
    Экспортирует конфиг (без password_hash) в указанный файл или
    возвращает строку, если file_path=None.
    """
    safe = {k: v for k, v in config.items() if k != "password_hash"}
    safe["_exported_by"] = "AntiGameController"
    safe["_export_version"] = "2.0"
    payload = json.dumps(safe, ensure_ascii=False, indent=4)

    if file_path:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(payload)
            return file_path
        except Exception as e:
            print(f"[config_storage] Ошибка экспорта в файл: {e}")
            return ""
    return payload


def import_from_payload(payload: str | dict) -> dict | None:
    """Импортирует конфиг из строки JSON или уже распарсенного dict."""
    try:
        if isinstance(payload, str):
            data = json.loads(payload)
        else:
            data = payload

        if not isinstance(data, dict):
            return None

        # Запрещённые/нерелевантные поля при импорте
        safe = {
            "blocked_processes": data.get("blocked_processes", []),
            "blocked_websites": data.get("blocked_websites", []),
            "check_interval": data.get("check_interval", 5),
            "show_notifications": data.get("show_notifications", True),
            "notification_message": data.get(
                "notification_message",
                "⚠️ Доступ запрещен!\n\nОбратитесь к преподавателю для получения доступа.",
            ),
            "auto_start": data.get("auto_start", True),
            "enable_autostart": data.get("enable_autostart", True),
            "enable_process_protection": data.get("enable_process_protection", True),
            "theme": data.get("theme", "dark"),
        }
        # Базовая валидация списков
        if not isinstance(safe["blocked_processes"], list):
            safe["blocked_processes"] = []
        if not isinstance(safe["blocked_websites"], list):
            safe["blocked_websites"] = []
        safe["blocked_processes"] = [
            str(x) for x in safe["blocked_processes"] if isinstance(x, (str, int))
        ]
        safe["blocked_websites"] = [
            str(x) for x in safe["blocked_websites"] if isinstance(x, (str, int))
        ]
        return safe
    except Exception as e:
        print(f"[config_storage] Ошибка импорта: {e}")
        return None


def get_storage_root() -> str:
    """Для отображения пути в UI"""
    return _storage_root()
