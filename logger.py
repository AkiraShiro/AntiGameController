"""
Модуль логирования для Anti-Game Controller.
Обеспечивает единообразное логирование во все модули проекта.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime


# Глобальный флаг инициализации
_initialized = False
_log_dir = None


def _get_log_dir():
    """Возвращает путь к директории логов в AppData"""
    if os.name == 'nt':
        app_data = os.getenv('APPDATA')
        if app_data:
            log_dir = os.path.join(app_data, "AntiGameController", "logs")
        else:
            log_dir = os.path.join(
                os.path.expanduser("~"),
                "AntiGameController",
                "logs")
    else:
        log_dir = os.path.join(
            os.path.expanduser("~"),
            ".antigamecontroller",
            "logs")

    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        log_dir = os.path.dirname(os.path.abspath(__file__))

    return log_dir


def setup_logging(log_level=logging.INFO):
    """
    Настройка глобального логирования.
    Вызывается один раз при старте приложения.
    """
    global _initialized, _log_dir

    if _initialized:
        return

    _log_dir = _get_log_dir()

    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Удаляем существующие обработчики (на случай повторного вызова)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Форматтер
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Файловый обработчик с ротацией
    log_file = os.path.join(_log_dir, "antigame.log")
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # Если не удалось создать файл лога - продолжаем без него
        print(
            f"[logger] Не удалось создать файловый лог: {e}",
            file=sys.stderr)

    # Консольный обработчик (только для отладки)
    if os.getenv('ANTIGAME_DEBUG'):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    _initialized = True


def get_logger(name):
    """
    Возвращает именованный логгер.
    При первом вызове автоматически инициализирует систему логирования.

    Args:
     name: имя модуля (обычно __name__)

    Returns:
     logging.Logger
    """
    if not _initialized:
        setup_logging()

    return logging.getLogger(name)


def get_log_file_path():
    """Возвращает путь к текущему файлу лога"""
    if _log_dir is None:
        _get_log_dir()
    return os.path.join(_log_dir, "antigame.log")


# Инициализация при импорте
setup_logging()
