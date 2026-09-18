import os
import sys
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Windows-консоль в cp1251/cp1252 не печатает Unicode (✗, ✓, кириллица в print)
# Включаем UTF-8 для stdout/stderr, чтобы дебаг-принты не роняли приложение.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class ConfigManager:
    """Менеджер конфигурации с шифрованием"""

    def __init__(self, app_name="AntiGameController"):
        self.app_name = app_name
        # Секретный ключ для шифрования (в продакшене генерируется один раз)
        self.salt = b'anti_game_salt_key_2025_secure'
        self.encryption_key = self._generate_key()
        self.cipher = Fernet(self.encryption_key)

        # Путь к зашифрованному конфигу в AppData (скрытая папка)
        self.config_dir = self._get_config_dir()
        self.config_file = os.path.join(self.config_dir, ".config.dat")

    def _generate_key(self):
        """Генерация ключа шифрования"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(
            kdf.derive(b"anti_game_master_key_do_not_share"))
        return key

    def _get_config_dir(self):
        """Получение пути к скрытой папке конфига"""
        if os.name == 'nt':  # Windows
            app_data = os.getenv('APPDATA')
            config_dir = os.path.join(app_data, self.app_name)
        else:  # Linux/Mac
            home = os.path.expanduser("~")
            config_dir = os.path.join(home, f".{self.app_name.lower()}")

        # Создаем папку если не существует
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
            # Делаем папку скрытой на Windows
            if os.name == 'nt':
                import ctypes
                FILE_ATTRIBUTE_HIDDEN = 0x02
                ctypes.windll.kernel32.SetFileAttributesW(
                    config_dir, FILE_ATTRIBUTE_HIDDEN)

        return config_dir

    def get_default_config(self, profile_name: str = "default") -> dict:
        """Конфигурация по умолчанию"""
        import hashlib
        default_password = "1234"
        password_hash = hashlib.sha256(default_password.encode()).hexdigest()

        return {
            "profile_name": profile_name,
            "password_hash": password_hash,
            "blocked_processes": [],
            "blocked_websites": [],
            "check_interval": 5,
            "auto_start": True,
            "show_notifications": True,
            "notification_message": "⚠️ Доступ запрещен!\n\nОбратитесь к преподавателю для получения доступа.",
            "enable_autostart": True,
            "enable_process_protection": True,
            "host_mode": False,
            "theme": "dark",
        }

    def load(self):
        """Загрузка и расшифровка конфига"""
        try:
            print(
                f"[DEBUG ConfigManager] Загрузка конфига из: {self.config_file}")

            # Сначала пытаемся загрузить зашифрованный конфиг
            if os.path.exists(self.config_file):
                print(f"[DEBUG ConfigManager] Найден зашифрованный конфиг")
                with open(self.config_file, 'rb') as f:
                    encrypted_data = f.read()

                decrypted_data = self.cipher.decrypt(encrypted_data)
                config = json.loads(decrypted_data.decode('utf-8'))
                config.setdefault("host_mode", False)
                print(f"[DEBUG ConfigManager] Конфиг загружен:")
                print(
                    f"  - Процессов: {len(config.get('blocked_processes', []))}")
                print(f"  - Сайтов: {len(config.get('blocked_websites', []))}")
                return config

            # Если зашифрованного нет, проверяем старый незашифрованный
            old_config_file = "config.json"
            if os.path.exists(old_config_file):
                print("Найден старый конфиг, мигрируем...")
                with open(old_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # Добавляем новые поля если их нет
                if "show_notifications" not in config:
                    config["show_notifications"] = True
                if "notification_message" not in config:
                    config["notification_message"] = "⚠️ Доступ запрещен!\n\nОбратитесь к преподавателю для получения доступа."
                if "profile_name" not in config:
                    config["profile_name"] = "default"

                # Сохраняем в зашифрованном виде
                self.save(config)

                # Удаляем старый незашифрованный файл
                try:
                    os.remove(old_config_file)
                    print("Старый конфиг удален, данные защищены.")
                except BaseException:
                    pass

                return config

            # Если ничего нет, создаем конфиг по умолчанию
            print("[DEBUG ConfigManager] Конфиг не найден, создаём по умолчанию")
            default_config = self.get_default_config()
            self.save(default_config)
            return default_config

        except Exception as e:
            print(f"✗ Ошибка загрузки конфига: {e}")
            import traceback
            traceback.print_exc()
            # В случае ошибки возвращаем конфиг по умолчанию
            return self.get_default_config()

    def save(self, config):
        """Шифрование и сохранение конфига"""
        try:
            print(
                f"[DEBUG ConfigManager] Сохранение конфига в: {self.config_file}")
            print(f"  - Процессов: {len(config.get('blocked_processes', []))}")
            print(f"  - Сайтов: {len(config.get('blocked_websites', []))}")

            # Снимаем атрибуты read-only и hidden если есть
            if os.path.exists(self.config_file) and os.name == 'nt':
                try:
                    import ctypes
                    FILE_ATTRIBUTE_NORMAL = 0x80
                    ctypes.windll.kernel32.SetFileAttributesW(
                        self.config_file, FILE_ATTRIBUTE_NORMAL)
                    print("[DEBUG ConfigManager] Сняты атрибуты файла")
                except Exception as e:
                    print(
                        f"[DEBUG ConfigManager] Не удалось снять атрибуты: {e}")

            # Преобразуем в JSON
            json_data = json.dumps(config, indent=4)

            # Шифруем
            encrypted_data = self.cipher.encrypt(json_data.encode('utf-8'))

            # Сохраняем
            with open(self.config_file, 'wb') as f:
                f.write(encrypted_data)
                f.flush()
                os.fsync(f.fileno())

            print(f"[DEBUG ConfigManager] ✓ Конфиг успешно сохранён")

            # Делаем файл скрытым на Windows
            if os.name == 'nt':
                import ctypes
                FILE_ATTRIBUTE_HIDDEN = 0x02
                ctypes.windll.kernel32.SetFileAttributesW(
                    self.config_file, FILE_ATTRIBUTE_HIDDEN)

            return True

        except Exception as e:
            print(f"✗ Ошибка сохранения конфига: {e}")
            import traceback
            traceback.print_exc()
            return False

    def export_config(self, config, file_path):
        """
        Экспорт конфига в JSON файл (только списки процессов и сайтов)

        Args:
            config: конфигурация для экспорта
            file_path: путь к файлу для сохранения

        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            # Экспортируем только списки, без пароля и других настроек
            export_data = {
                "blocked_processes": config.get("blocked_processes", []),
                "blocked_websites": config.get("blocked_websites", []),
                "notification_message": config.get("notification_message", ""),
                "check_interval": config.get("check_interval", 5),
                "export_version": "1.0",
                "app_name": self.app_name
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)

            print(f"Конфигурация экспортирована в: {file_path}")
            return True

        except Exception as e:
            print(f"Ошибка экспорта конфига: {e}")
            return False

    def import_config(self, file_path, current_config):
        """
        Импорт конфига из JSON файла

        Args:
            file_path: путь к файлу для импорта
            current_config: текущая конфигурация (для сохранения пароля)

        Returns:
            обновленная конфигурация или None в случае ошибки
        """
        try:
            # Читаем файл
            with open(file_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            # Валидация данных
            if not self._validate_import_data(import_data):
                print("Ошибка валидации импортируемых данных")
                return None

            # Создаем новый конфиг на основе текущего (сохраняем пароль и
            # настройки)
            new_config = current_config.copy()

            # Обновляем только списки процессов и сайтов
            if "blocked_processes" in import_data:
                new_config["blocked_processes"] = import_data["blocked_processes"]

            if "blocked_websites" in import_data:
                new_config["blocked_websites"] = import_data["blocked_websites"]

            if "notification_message" in import_data:
                new_config["notification_message"] = import_data["notification_message"]

            if "check_interval" in import_data:
                new_config["check_interval"] = import_data["check_interval"]

            print(f"Конфигурация импортирована из: {file_path}")
            print(f"  Процессов: {len(new_config['blocked_processes'])}")
            print(f"  Сайтов: {len(new_config['blocked_websites'])}")

            return new_config

        except json.JSONDecodeError as e:
            print(f"Ошибка чтения JSON: {e}")
            return None
        except Exception as e:
            print(f"Ошибка импорта конфига: {e}")
            return None

    def _validate_import_data(self, data):
        """
        Валидация импортируемых данных

        Args:
            data: данные для валидации

        Returns:
            True если данные корректны, False иначе
        """
        try:
            # Проверяем обязательные поля
            if not isinstance(data, dict):
                return False

            # Проверяем blocked_processes
            if "blocked_processes" in data:
                if not isinstance(data["blocked_processes"], list):
                    return False
                # Все элементы должны быть строками
                if not all(isinstance(x, str)
                           for x in data["blocked_processes"]):
                    return False

            # Проверяем blocked_websites
            if "blocked_websites" in data:
                if not isinstance(data["blocked_websites"], list):
                    return False
                # Все элементы должны быть строками
                if not all(isinstance(x, str)
                           for x in data["blocked_websites"]):
                    return False

            # Проверяем check_interval
            if "check_interval" in data:
                if not isinstance(data["check_interval"], (int, float)):
                    return False
                if data["check_interval"] < 1 or data["check_interval"] > 60:
                    return False

            # Проверяем notification_message
            if "notification_message" in data:
                if not isinstance(data["notification_message"], str):
                    return False

            return True

        except Exception as e:
            print(f"Ошибка валидации: {e}")
            return False


# Для обратной совместимости - встроенный конфиг на случай если файл удален
EMBEDDED_CONFIG = {
    "password_hash": "03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4",
    "blocked_processes": ["RobloxPlayerBeta.exe", "Minecraft.exe"],
    "blocked_websites": ["roblox.com", "minecraft.net"],
    "check_interval": 5,
    "auto_start": True,
    "show_notifications": True,
    "notification_message": "⚠️ Доступ запрещен!\n\nОбратитесь к преподавателю для получения доступа."
}
