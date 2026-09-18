"""
Anti-Game Controller - главный модуль приложения.
GUI на PyQt5 для управления блокировкой игр и сайтов.

Возможности:
- Пароль на критичные действия (закрытие, остановка, импорт, удаление, смена)
- QScrollArea для настроек
- Импорт/экспорт конфигов через скрытое хранилище AppData (UUID-имена)
- Drag&drop конфига в окно
- Сетевой агент + удалённое управление через сервер (HTTP long-poll)
- Планировщик задач: автозапуск + рестарт каждые 5 минут
"""
import sys
import os
import threading
import time
import hashlib
import subprocess
import msvcrt
from version import CURRENT_VERSION
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QListWidget, QPushButton, QLineEdit, QLabel,
    QSpinBox, QCheckBox, QGroupBox, QMessageBox, QDialog,
    QDialogButtonBox, QSystemTrayIcon, QMenu, QAction,
    QTextEdit, QStatusBar, QFormLayout, QComboBox,
    QScrollArea, QInputDialog, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QIcon, QTextCursor

from logger import get_logger, get_log_file_path
from config_manager import ConfigManager
from process_manager import kill_processes, get_running_processes
from hosts_manager import block_websites, unblock_websites, is_admin
from autostart_manager import TaskSchedulerManager, AutostartManager
from styles import DARK_THEME, LIGHT_THEME
from network_agent import NetworkAgent
from auto_updater import AutoUpdater
from pynput.keyboard import Key, Controller
import winreg

import config_storage

logger = get_logger("Main")

_single_instance_lock_handle = None
_single_instance_lock_path = None


def _hidden_subprocess_kwargs() -> dict:
    """
    Возвращает kwargs для subprocess.run/Popen, которые прячут консольное окно
    на Windows (create_new_console/CREATE_NO_WINDOW). Без этого дочерний
    cmd/PowerShell на мгновение «мигает» чёрным окном.
    """
    if os.name == "nt":
        return {
            "creationflags": subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0x08000000,
        }
    return {}


def run_hidden(*args, **kwargs):
    """subprocess.run, который на Windows не создаёт консольное окно."""
    kwargs.update(_hidden_subprocess_kwargs())
    return subprocess.run(*args, **kwargs)


def popen_hidden(*args, **kwargs):
    """subprocess.Popen, который на Windows не создаёт консольное окно."""
    kwargs.update(_hidden_subprocess_kwargs())
    return subprocess.Popen(*args, **kwargs)


def _acquire_single_instance_lock() -> bool:
    """Не даёт запускать второй GUI-инстанс приложения."""
    global _single_instance_lock_handle, _single_instance_lock_path
    lock_dir = os.path.join(os.environ.get("APPDATA", "."), "AntiGameController")
    os.makedirs(lock_dir, exist_ok=True)
    _single_instance_lock_path = os.path.join(lock_dir, "app.lock")
    try:
        _single_instance_lock_handle = os.open(
            _single_instance_lock_path,
            os.O_RDWR | os.O_CREAT,
        )
        msvcrt.locking(_single_instance_lock_handle, msvcrt.LK_NBLCK, 1)
    except OSError:
        if _single_instance_lock_handle is not None:
            try:
                os.close(_single_instance_lock_handle)
            except Exception:
                pass
            _single_instance_lock_handle = None
        return False
    return True


# ----------------- Диалоги -----------------

class PasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Требуется пароль")
        self.setModal(True)
        self.setFixedSize(360, 180)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Введите пароль для закрытия приложения:")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.returnPressed.connect(self.accept)
        layout.addWidget(self.password_input)

        hint = QLabel("По умолчанию: 1234")
        hint.setStyleSheet("color: #6c7086; font-size: 9pt;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_password(self):
        return self.password_input.text()


class ChangePasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Смена пароля")
        self.setModal(True)
        self.setFixedSize(360, 280)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Смена пароля")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        layout.addWidget(QLabel("Текущий пароль:"))
        self.old_password = QLineEdit()
        self.old_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.old_password)

        layout.addWidget(QLabel("Новый пароль:"))
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.new_password)

        layout.addWidget(QLabel("Подтверждение:"))
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.confirm_password)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return (
            self.old_password.text(),
            self.new_password.text(),
            self.confirm_password.text(),
        )


class ChangeProfileDialog(QDialog):
    """Выбор профиля для загрузки/удаления/экспорта."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Профили конфигурации")
        self.setModal(True)
        self.resize(620, 400)
        self.selected_id: str | None = None
        self.action: str = "load"
        self.init_ui()
        self.refresh()

    def init_ui(self):
        v = QVBoxLayout(self)
        v.addWidget(QLabel(f"Хранилище: {config_storage.get_storage_root()}"))

        self.list_widget = QListWidget()
        v.addWidget(self.list_widget)

        row = QHBoxLayout()
        load_btn = QPushButton("Загрузить как активный")
        load_btn.clicked.connect(lambda: self._finish("load"))
        row.addWidget(load_btn)
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(lambda: self._finish("delete"))
        row.addWidget(del_btn)
        exp_btn = QPushButton("Экспорт в файл...")
        exp_btn.clicked.connect(lambda: self._finish("export"))
        row.addWidget(exp_btn)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        v.addLayout(row)

        refresh = QPushButton("Обновить список")
        refresh.clicked.connect(self.refresh)
        v.addWidget(refresh)

    def refresh(self):
        self.list_widget.clear()
        for p in config_storage.list_profiles():
            label = (
                f"{p.get('name', '(без имени)')} — "
                f"{p.get('created', '')} [{p['id'][:8]}]"
            )
            self.list_widget.addItem(f"{p['id']}||{label}")

    def _finish(self, action: str):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Выбор", "Сначала выберите профиль")
            return
        self.selected_id = item.text().split("||", 1)[0]
        self.action = action
        self.accept()


# -------------- Локскрин --------------

class LockScreen(QWidget):

    def __init__(self):
        super().__init__()
        self.pressed_keys = set()
        self.allow_exit = False  # Флаг разрешения на закрытие

        # Инициализация контроллера клавиатуры pynput
        self.keyboard_controller = Controller()

        # Настройка таймера для симуляции клика Esc
        self.esc_timer = QTimer(self)
        self.esc_timer.setInterval(100)  # Интервал в миллисекундах (100 мс = 10 раз в сек)
        self.esc_timer.timeout.connect(self.press_esc_key)

        self.init_ui()

        # Запускаем таймер после инициализации окна
        self.esc_timer.start()

    def init_ui(self):
        # Комплекс флагов:
        flags = (
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowType_Mask
        )
        self.setWindowFlags(flags)

        self.showFullScreen()
        self.activateWindow()

        # Визуальный интерфейс
        layout = QVBoxLayout()
        label = QLabel("Фокус внимания", self)  # G+Space to exit
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 28px; color: #ffffff; font-weight: bold;")
        layout.addWidget(label)

        self.setLayout(layout)
        self.setStyleSheet("background-color: #0d0d0d;")

        # Включаем перехват потери фокуса
        self.installEventFilter(self)

    # Функция отправки нажатия Esc
    def press_esc_key(self):
        self.keyboard_controller.press(Key.esc)
        self.keyboard_controller.release(Key.esc)

    # 1. Защита от Alt+F4 и стандартного закрытия
    def closeEvent(self, event):
        if self.allow_exit:
            # Обязательно останавливаем таймер при выходе
            self.esc_timer.stop()
            event.accept()
        else:
            event.ignore()

    # 2. Обработка нажатий G + Space
    def keyPressEvent(self, event):
        self.pressed_keys.add(event.key())

        if Qt.Key_G in self.pressed_keys and Qt.Key_Space in self.pressed_keys:
            self.allow_exit = True
            self.close()

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self.pressed_keys.discard(event.key())
        super().keyReleaseEvent(event)

    # 3. Защита от Alt+Tab
    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                self.showNormal()
                self.showFullScreen()
        super().changeEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.WindowDeactivate:
            self.activateWindow()
            self.raise_()
            return True
        return super().eventFilter(obj, event)





# ----------------- Главное окно -----------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._exit_requested = False
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self.lockscreen = None
        self.task_scheduler = TaskSchedulerManager()
        self.autostart = AutostartManager()

        self.is_monitoring = False
        self.monitor_thread = None
        self.tray_icon = None

        # Сетевой агент (отправляет heartbeat, принимает команды)
        self.network_agent: NetworkAgent | None = None

        self.setAcceptDrops(True)

        self.setWindowTitle("Anti-Game Controller")
        self.setMinimumSize(940, 700)

        self.init_ui()
        self.apply_theme()
        self.init_tray()
        self.load_lists_to_ui()
        self.refresh_profiles_list()
        self.update_status()

        # Автостарт защиты при запуске (если включён)
        if self.config.get("auto_start", True):
            QTimer.singleShot(800, self.start_protection)

        # Создание задачи планировщика (если включено)
        if self.config.get("enable_autostart", True):
            try:
                self.task_scheduler.create_startup_task()
                self.autostart.set_autostart()
            except Exception:
                logger.exception("Не удалось создать задачу планировщика")

        self._integrity_guard_running = True
        self._integrity_guard_thread = threading.Thread(
            target=self._integrity_guard_loop,
            daemon=True,
        )
        self._integrity_guard_thread.start()

        # Запуск сетевого агента
        self._start_network_agent()

        # Таймер обновления QR-кода админки (раз в 5с)
        self._qr_timer = QTimer(self)
        self._qr_timer.setInterval(5000)
        self._qr_timer.timeout.connect(self._refresh_admin_qr)
        self._qr_timer.start()
        # первичное обновление — сразу
        QTimer.singleShot(500, self._refresh_admin_qr)

        # Запуск автообновления через GitHub Releases
        try:
            self.auto_updater = AutoUpdater(self.config, self)
            self.auto_updater.start()
        except Exception:
            logger.exception("Не удалось запустить автообновление")

        logger.info(
            f"Приложение запущено, профиль: {self.config.get('profile_name', 'default')}"
        )

    # ------------- UI init -------------

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        header = QHBoxLayout()
        title = QLabel(f"Anti-Game Controller v{CURRENT_VERSION}")
        title.setObjectName("titleLabel")
        header.addWidget(title)

        self.profile_label = QLabel(
            f"Профиль: {self.config.get('profile_name', 'default')}"
        )
        self.profile_label.setStyleSheet("color: #a6adc8;")
        header.addStretch()
        header.addWidget(self.profile_label)
        self.status_label = QLabel("Неактивно")
        self.status_label.setObjectName("statusLabel")
        header.addWidget(self.status_label)
        main_layout.addLayout(header)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.create_processes_tab()
        self.create_websites_tab()
        self.create_settings_tab()
        self.create_logs_tab()
        self.create_profiles_tab()

        control = QHBoxLayout()
        self.start_btn = QPushButton("Запустить защиту")
        self.start_btn.setObjectName("startButton")
        self.start_btn.clicked.connect(self.start_protection)
        control.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Остановить защиту")
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.clicked.connect(self.stop_protection)
        self.stop_btn.setEnabled(False)
        control.addWidget(self.stop_btn)

        control.addStretch()

        self.apply_btn = QPushButton("Применить изменения")
        self.apply_btn.clicked.connect(self.apply_changes)
        control.addWidget(self.apply_btn)
        main_layout.addLayout(control)

        self.statusBar().showMessage("Готов к работе")

    def lockscreen_on(self):
        self.lockscreen = LockScreen()

    def lockscreen_off(self):
        try:
            if self.lockscreen is not None:
                self.lockscreen.allow_exit = True
                self.lockscreen.close()
                self.lockscreen = None
        except:
            pass



    def create_processes_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel("Список процессов для блокировки (имена .exe):")
        info.setObjectName("titleLabel")
        layout.addWidget(info)

        self.process_list = QListWidget()
        layout.addWidget(self.process_list)

        add_layout = QHBoxLayout()
        self.process_input = QLineEdit()
        self.process_input.setPlaceholderText(
            "Имя процесса (например: RobloxPlayerBeta.exe)"
        )
        self.process_input.returnPressed.connect(self.add_process)
        add_layout.addWidget(self.process_input)

        add_btn = QPushButton("Добавить")
        add_btn.setObjectName("addButton")
        add_btn.clicked.connect(self.add_process)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)

        btn_layout = QHBoxLayout()
        del_btn = QPushButton("Удалить выбранное (под паролем)")
        del_btn.setObjectName("deleteButton")
        del_btn.clicked.connect(self.delete_process)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.tabs.addTab(tab, "Процессы")

    def create_websites_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel("Список сайтов для блокировки (через hosts):")
        info.setObjectName("titleLabel")
        layout.addWidget(info)

        self.website_list = QListWidget()
        layout.addWidget(self.website_list)

        add_layout = QHBoxLayout()
        self.website_input = QLineEdit()
        self.website_input.setPlaceholderText("Домен (например: roblox.com)")
        self.website_input.returnPressed.connect(self.add_website)
        add_layout.addWidget(self.website_input)

        add_btn = QPushButton("Добавить")
        add_btn.setObjectName("addButton")
        add_btn.clicked.connect(self.add_website)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)

        btn_layout = QHBoxLayout()
        del_btn = QPushButton("Удалить выбранное (под паролем)")
        del_btn.setObjectName("deleteButton")
        del_btn.clicked.connect(self.delete_website)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.tabs.addTab(tab, "Сайты")

    def create_settings_tab(self):
        """Настройки обёрнуты в QScrollArea чтобы элементы не слипались."""
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer_layout.addWidget(scroll)

        tab = QWidget()
        scroll.setWidget(tab)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        interval_group = QGroupBox("Интервал проверки (секунд)")
        il = QHBoxLayout(interval_group)
        self.interval_spin = QSpinBox()
        self.interval_spin.setMinimum(1)
        self.interval_spin.setMaximum(60)
        self.interval_spin.setValue(self.config.get("check_interval", 5))
        il.addWidget(QLabel("Проверять каждые:"))
        il.addWidget(self.interval_spin)
        il.addWidget(QLabel("сек."))
        il.addStretch()
        layout.addWidget(interval_group)

        notif_group = QGroupBox("Уведомления")
        nl = QVBoxLayout(notif_group)
        self.show_notif_check = QCheckBox(
            "Показывать уведомление при закрытии игры"
        )
        self.show_notif_check.setChecked(
            self.config.get("show_notifications", True)
        )
        nl.addWidget(self.show_notif_check)
        nl.addWidget(QLabel("Текст уведомления:"))
        self.notif_text = QTextEdit()
        self.notif_text.setMaximumHeight(100)
        self.notif_text.setPlainText(
            self.config.get("notification_message", "Доступ запрещен!")
        )
        nl.addWidget(self.notif_text)
        layout.addWidget(notif_group)

        auto_group = QGroupBox("Автозапуск и защита")
        al = QVBoxLayout(auto_group)
        self.autostart_check = QCheckBox(
            "Запускать при входе в Windows (через планировщик задач)"
        )
        self.autostart_check.setChecked(
            self.config.get("enable_autostart", True)
        )
        al.addWidget(self.autostart_check)
        self.protection_check = QCheckBox(
            "Защищать процесс AntiGameController от завершения (Task Manager)"
        )
        self.protection_check.setChecked(
            self.config.get("enable_process_protection", True)
        )
        al.addWidget(self.protection_check)
        layout.addWidget(auto_group)

        # ---- Локальная сеть (автовыбор главного) ----
        net_group = QGroupBox("Локальная сеть (авто)")
        nl = QFormLayout(net_group)

        self.agent_id_edit = QLineEdit(self.config.get("agent_name", ""))
        self.agent_id_edit.setPlaceholderText(
            "Имя ноутбука (например: Дети-Ноут1)"
        )
        nl.addRow("Имя этого ПК:", self.agent_id_edit)

        self.auto_update_check = QCheckBox(
            "Автообновление через GitHub Releases"
        )
        self.auto_update_check.setChecked(
            self.config.get("auto_update", True)
        )
        nl.addRow("", self.auto_update_check)

        self.host_mode_check = QCheckBox(
            "Сделать этот ПК главным (HOST)"
        )
        self.host_mode_check.setChecked(self.config.get("host_mode", False))
        nl.addRow("Роль в сети:", self.host_mode_check)

        self.net_status_label = QLabel(
            "Запускается… (если этот ноутбук первый в сети, "
            "он сам станет главным — в его админке будут все остальные)"
        )
        self.net_status_label.setWordWrap(True)
        nl.addRow("Статус:", self.net_status_label)

        apply_net_btn = QPushButton("Применить и перезапустить агента")
        apply_net_btn.clicked.connect(self.apply_network_settings)
        nl.addRow("", apply_net_btn)

        check_update_btn = QPushButton("Проверить обновления сейчас")
        check_update_btn.clicked.connect(
            lambda: self._check_updates_now()
        )
        nl.addRow("", check_update_btn)

        open_admin_btn = QPushButton("Открыть админку в браузере")
        open_admin_btn.clicked.connect(self._open_admin_in_browser)
        nl.addRow("", open_admin_btn)

        self.force_host_btn = QPushButton("Сделать этот ПК главным (Хост)")
        self.force_host_btn.clicked.connect(self.force_host_action)
        nl.addRow("", self.force_host_btn)


        # QR-код для телефона/планшета
        self.qr_label = QLabel()
        self.qr_label.setFixedSize(180, 180)
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setStyleSheet(
            "QLabel { background: white; border: 1px solid #313244; }"
        )
        self.qr_label.setText("(QR появится\nкогда я — host)")
        nl.addRow("QR для телефона:", self.qr_label)

        layout.addWidget(net_group)


        theme_group = QGroupBox("Оформление")
        tl = QHBoxLayout(theme_group)
        tl.addWidget(QLabel("Тема:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Темная", "Светлая"])
        current_theme = self.config.get("theme", "dark")
        self.theme_combo.setCurrentIndex(0 if current_theme == "dark" else 1)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        tl.addWidget(self.theme_combo)
        tl.addStretch()
        layout.addWidget(theme_group)

        sec_group = QGroupBox("Безопасность")
        sl = QVBoxLayout(sec_group)
        change_pwd_btn = QPushButton("Сменить пароль")
        change_pwd_btn.clicked.connect(self.change_password)
        sl.addWidget(change_pwd_btn)
        info = QLabel(
            "Защита от закрытия:\n"
            "• Закрытие — только по паролю\n"
            "• Планировщик задач Windows запускает приложение каждые 5 минут\n"
            "• Сетевой агент позволяет управлять этим ПК удалённо с сервера"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #a6adc8;")
        sl.addWidget(info)
        layout.addWidget(sec_group)

        layout.addStretch()
        self.tabs.addTab(outer, "Настройки")

    def create_logs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(f"Файл лога: {get_log_file_path()}")
        info.setObjectName("titleLabel")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh_logs)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.refresh_logs()
        self.tabs.addTab(tab, "Логи")

    def create_profiles_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            "Профили конфигурации хранятся в скрытой папке AppData.\n"
            "Файлы имеют UUID-имена без расширения. Удалить из проводника сложно."
        )
        info.setObjectName("titleLabel")
        info.setWordWrap(True)
        layout.addWidget(info)

        row = QHBoxLayout()
        save_btn = QPushButton("Сохранить текущий как профиль")
        save_btn.clicked.connect(self.save_as_profile)
        row.addWidget(save_btn)

        import_btn = QPushButton("Импорт конфига (под паролем)")
        import_btn.clicked.connect(self.import_profile)
        row.addWidget(import_btn)

        export_btn = QPushButton("Экспорт активного в файл...")
        export_btn.clicked.connect(self.export_active_profile)
        row.addWidget(export_btn)
        layout.addLayout(row)

        layout.addWidget(QLabel("Сохранённые профили:"))
        self.profiles_listbox = QListWidget()
        layout.addWidget(self.profiles_listbox)

        action_row = QHBoxLayout()
        load_btn = QPushButton("Загрузить как активный (под паролем)")
        load_btn.clicked.connect(self.load_selected_profile)
        action_row.addWidget(load_btn)

        delete_btn = QPushButton("Удалить выбранный (под паролем)")
        delete_btn.clicked.connect(self.delete_selected_profile)
        action_row.addWidget(delete_btn)

        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh_profiles_list)
        action_row.addWidget(refresh_btn)
        layout.addLayout(action_row)

        self.tabs.addTab(tab, "Профили")

    # ------------- Drag & drop -------------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if not os.path.isfile(path):
            return
        # Сразу загружаем как новый конфиг (запрос пароля)
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = f.read()
            cfg = config_storage.import_from_payload(payload)
            if not cfg:
                QMessageBox.critical(self, "Импорт", "Не удалось разобрать файл конфига")
                return
            # Запрос пароля при импорте
            pw, ok = QInputDialog.getText(
                self, "Импорт конфига", "Введите пароль для подтверждения:",
                QLineEdit.Password,
            )
            if not ok:
                return
            if hashlib.sha256((pw or "").encode()).hexdigest() != self.config.get(
                "password_hash"
            ):
                QMessageBox.warning(self, "Импорт", "Неверный пароль")
                logger.warning("Попытка импорта с неверным паролем")
                return
            name, ok = QInputDialog.getText(
                self, "Имя профиля", "Под каким именем сохранить?:", text=os.path.basename(path)
            )
            if not ok or not name.strip():
                name = "imported"
            cfg["password_hash"] = self.config.get("password_hash")
            cfg["profile_name"] = name.strip()
            pid = config_storage.save_config(name.strip(), cfg)
            self.config_manager.save(self.config)
            self.refresh_profiles_list()
            QMessageBox.information(
                self, "Импорт", f"Конфиг импортирован (id={pid[:8]})"
            )
            logger.info(f"Импортирован конфиг из {path} -> {pid[:8]}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать: {e}")

    # ------------- Базовые операции над списками -------------

    def add_process(self):
        name = self.process_input.text().strip()
        #пароль на ввод имени процесса
        pw, ok = QInputDialog.getText(
            self, "Добавление процесса",
            "Введите пароль:", QLineEdit.Password,
        )
        if not ok:
            return
        if hashlib.sha256((pw or "").encode()).hexdigest() != self.config.get(
            "password_hash"
        ):
            QMessageBox.warning(self, "Ошибка", "Неверный пароль")
            logger.warning("Попытка добавления процесса с неверным паролем")
            return



        if not name:
            return
        if not name.lower().endswith(".exe"):
            name = name + ".exe"
        if self.process_list.findItems(name, Qt.MatchExactly):
            QMessageBox.warning(self, "Внимание", f"Процесс {name} уже в списке")
            return
        #тут если не имя самого процесса
        if name.lower() == os.path.basename(sys.executable).lower():
            QMessageBox.warning(self, "Внимание", f"Нельзя блокировать сам AntiGameController")
            return
        self.process_list.addItem(name)
        self.process_input.clear()
        logger.info(f"Добавлен процесс: {name}")
        #применение
        if self.is_monitoring:
            self.save_lists_from_ui()

    def delete_process(self):
        # Пароль на удаление
        pw, ok = QInputDialog.getText(
            self, "Удаление процесса",
            "Введите пароль:", QLineEdit.Password,
        )
        if not ok:
            return
        if hashlib.sha256((pw or "").encode()).hexdigest() != self.config.get(
            "password_hash"
        ):
            QMessageBox.warning(self, "Ошибка", "Неверный пароль")
            logger.warning("Попытка удаления процесса с неверным паролем")
            return
        for item in self.process_list.selectedItems():
            self.process_list.takeItem(self.process_list.row(item))
            logger.info(f"Удален процесс: {item.text()}")
        # Сразу применяем
        if self.is_monitoring:
            self.save_lists_from_ui()

    def add_website(self):
        site = self.website_input.text().strip().lower()
        if not site:
            return
        site = site.replace("http://", "").replace("https://", "").replace("www.", "")
        site = site.split("/")[0]
        if self.website_list.findItems(site, Qt.MatchExactly):
            QMessageBox.warning(self, "Внимание", f"Сайт {site} уже в списке")
            return
        self.website_list.addItem(site)
        self.website_input.clear()
        logger.info(f"Добавлен сайт: {site}")

    def delete_website(self):
        # Пароль на удаление
        pw, ok = QInputDialog.getText(
            self, "Удаление сайта",
            "Введите пароль:", QLineEdit.Password,
        )
        if not ok:
            return
        if hashlib.sha256((pw or "").encode()).hexdigest() != self.config.get(
            "password_hash"
        ):
            QMessageBox.warning(self, "Ошибка", "Неверный пароль")
            logger.warning("Попытка удаления сайта с неверным паролем")
            return
        for item in self.website_list.selectedItems():
            self.website_list.takeItem(self.website_list.row(item))
            logger.info(f"Удален сайт: {item.text()}")
        if self.is_monitoring:
            self.save_lists_from_ui()
            self.apply_blocking()

    def load_lists_to_ui(self):
        self.process_list.clear()
        for p in self.config.get("blocked_processes", []):
            self.process_list.addItem(p)
        self.website_list.clear()
        for w in self.config.get("blocked_websites", []):
            self.website_list.addItem(w)

    def save_lists_from_ui(self) -> bool:
        processes = [self.process_list.item(i).text() for i in range(self.process_list.count())]
        websites = [self.website_list.item(i).text() for i in range(self.website_list.count())]
        self.config["blocked_processes"] = processes
        self.config["blocked_websites"] = websites
        self.config["check_interval"] = self.interval_spin.value()
        self.config["show_notifications"] = self.show_notif_check.isChecked()
        self.config["notification_message"] = self.notif_text.toPlainText()
        self.config["enable_autostart"] = self.autostart_check.isChecked()
        self.config["enable_process_protection"] = self.protection_check.isChecked()
        self.config["theme"] = "dark" if self.theme_combo.currentIndex() == 0 else "light"
        return self.config_manager.save(self.config)

    # ------------- Профили конфигов -------------

    def refresh_profiles_list(self):
        if not hasattr(self, "profiles_listbox"):
            return
        self.profiles_listbox.clear()
        for p in config_storage.list_profiles():
            label = (
                f"{p.get('name', '(без имени)')} — "
                f"{p.get('created', '')} [{p['id'][:8]}]"
            )
            self.profiles_listbox.addItem(f"{p['id']}||{label}")

    def save_as_profile(self):
        # Сначала применим текущее состояние GUI
        self.save_lists_from_ui()
        name, ok = QInputDialog.getText(
            self, "Новый профиль", "Имя профиля:", text=self.config.get("profile_name", "")
        )
        if not ok or not name.strip():
            return
        self.config["profile_name"] = name.strip()
        self.config_manager.save(self.config)
        pid = config_storage.save_config(name.strip(), self.config)
        self.refresh_profiles_list()
        self.profile_label.setText(f"Профиль: {name.strip()}")
        QMessageBox.information(
            self, "Профиль", f"Сохранён как {name.strip()} [{pid[:8]}]"
        )
        logger.info(f"Сохранён новый профиль {name.strip()} -> {pid[:8]}")

    def import_profile(self):
        # Пароль
        pw, ok = QInputDialog.getText(
            self, "Импорт", "Пароль для подтверждения:", QLineEdit.Password,
        )
        if not ok:
            return
        if hashlib.sha256((pw or "").encode()).hexdigest() != self.config.get(
            "password_hash"
        ):
            QMessageBox.warning(self, "Импорт", "Неверный пароль")
            logger.warning("Попытка импорта с неверным паролем")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл конфига", "", "JSON (*.json);;Все файлы (*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Импорт", f"Не удалось прочитать файл: {e}")
            return
        cfg = config_storage.import_from_payload(payload)
        if not cfg:
            QMessageBox.critical(self, "Импорт", "Невалидный файл конфига")
            return
        name, ok = QInputDialog.getText(
            self, "Имя профиля", "Под каким именем сохранить?:",
            text=os.path.splitext(os.path.basename(path))[0],
        )
        if not ok or not name.strip():
            name = "imported"
        cfg["password_hash"] = self.config.get("password_hash")
        cfg["profile_name"] = name.strip()
        pid = config_storage.save_config(name.strip(), cfg)
        self.refresh_profiles_list()
        QMessageBox.information(
            self, "Импорт", f"Конфиг '{name.strip()}' импортирован [{pid[:8]}]"
        )
        logger.info(f"Импорт '{name.strip()}' -> {pid[:8]}")

    def export_active_profile(self):
        # Сохраняем то, что в UI, и экспортируем активный конфиг
        self.save_lists_from_ui()
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт конфига",
            f"{self.config.get('profile_name', 'profile')}.json",
            "JSON (*.json)",
        )
        if not path:
            return
        config_storage.export_to_clipboard_or_file(self.config, path)
        QMessageBox.information(self, "Экспорт", f"Сохранено: {path}")
        logger.info(f"Экспорт конфига в {path}")

    def load_selected_profile(self):
        item = self.profiles_listbox.currentItem()
        if not item:
            QMessageBox.warning(self, "Выбор", "Сначала выберите профиль")
            return
        pid = item.text().split("||", 1)[0]
        # Пароль при загрузке
        pw, ok = QInputDialog.getText(
            self, "Загрузка профиля", "Введите пароль:", QLineEdit.Password,
        )
        if not ok:
            return
        if hashlib.sha256((pw or "").encode()).hexdigest() != self.config.get(
            "password_hash"
        ):
            QMessageBox.warning(self, "Загрузка", "Неверный пароль")
            logger.warning("Попытка загрузки профиля с неверным паролем")
            return
        cfg = config_storage.load_config(pid)
        if not cfg:
            QMessageBox.critical(self, "Загрузка", "Профиль не найден")
            return
        cfg["password_hash"] = self.config.get("password_hash")
        self.config = cfg
        if getattr(self, "network_agent", None) is not None:
            self.network_agent.apply_agent_name(self.config.get("agent_name", ""))
        self.config_manager.save(self.config)
        self.load_lists_to_ui()
        self.interval_spin.setValue(self.config.get("check_interval", 5))
        self.show_notif_check.setChecked(self.config.get("show_notifications", True))
        self.notif_text.setPlainText(
            self.config.get("notification_message", "Доступ запрещен!")
        )
        self.autostart_check.setChecked(self.config.get("enable_autostart", True))
        self.protection_check.setChecked(
            self.config.get("enable_process_protection", True)
        )
        self.host_mode_check.setChecked(self.config.get("host_mode", False))
        self.theme_combo.setCurrentIndex(
            0 if self.config.get("theme", "dark") == "dark" else 1
        )
        self.profile_label.setText(
            f"Профиль: {self.config.get('profile_name', 'default')}"
        )
        self.apply_theme()
        # Если защита активна — применим новые списки к hosts и процессам
        if self.is_monitoring:
            self.apply_blocking()
        QMessageBox.information(self, "Загрузка", "Профиль загружен")
        logger.info(f"Профиль {self.config.get('profile_name')} загружен")

    def delete_selected_profile(self):
        item = self.profiles_listbox.currentItem()
        if not item:
            QMessageBox.warning(self, "Удаление", "Сначала выберите профиль")
            return
        pid = item.text().split("||", 1)[0]
        pw, ok = QInputDialog.getText(
            self, "Удаление профиля", "Введите пароль:", QLineEdit.Password,
        )
        if not ok:
            return
        if hashlib.sha256((pw or "").encode()).hexdigest() != self.config.get(
            "password_hash"
        ):
            QMessageBox.warning(self, "Удаление", "Неверный пароль")
            logger.warning("Попытка удаления профиля с неверным паролем")
            return
        if QMessageBox.question(
            self, "Удалить?",
            f"Удалить профиль {pid[:8]}?", QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            config_storage.delete_profile(pid)
            self.refresh_profiles_list()
            logger.info(f"Профиль {pid[:8]} удалён")

    def apply_changes(self):
        if not self._confirm_admin_password(
            "Применение настроек",
            "Введите пароль для применения настроек:",
        ):
            return
        if self.save_lists_from_ui():
            self.statusBar().showMessage("Настройки сохранены", 3000)
            logger.info("Настройки сохранены")
            if self.is_monitoring:
                self.apply_blocking()
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось сохранить настройки")

    def apply_blocking(self):
        websites = self.config.get("blocked_websites", [])
        if websites:
            block_websites(websites)
        else:
            unblock_websites()

    def apply_theme(self):
        theme = self.config.get("theme", "dark")
        if theme == "dark":
            self.setStyleSheet(DARK_THEME)
        else:
            self.setStyleSheet(LIGHT_THEME)

    def on_theme_changed(self, index):
        self.config["theme"] = "dark" if index == 0 else "light"
        self.config_manager.save(self.config)
        self.apply_theme()

    def init_tray(self):
        try:
            self.tray_icon = QSystemTrayIcon(self)
            icon_path = "icon.ico"
            self.tray_icon.setIcon(
                self.style().standardIcon(self.style().SP_ComputerIcon)
                if not os.path.exists(icon_path)
                else QIcon(icon_path)
            )
            menu = QMenu()
            show_action = QAction("Показать", self)
            show_action.triggered.connect(self.show_normal)
            menu.addAction(show_action)
            menu.addSeparator()
            quit_action = QAction("Выход (с паролем)", self)
            quit_action.triggered.connect(self.exit_from_tray)
            menu.addAction(quit_action)
            self.tray_icon.setContextMenu(menu)
            self.tray_icon.activated.connect(self.on_tray_activated)
            self.tray_icon.show()
        except Exception as e:
            logger.warning(f"Не удалось создать трей: {e}")

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_normal()

    def show_normal(self):
        self.show()
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.activateWindow()

    def hide_to_tray(self):
        if self.tray_icon and self.tray_icon.isVisible():
            self.hide()
            return True
        return False

    # ------------- Сетевой агент -------------

    def _start_network_agent(self):
        """Запуск сетевого агента: heartbeat + приём команд от сервера."""
        try:
            self.network_agent = NetworkAgent(self)
            self.network_agent.start()
        except Exception:
            logger.exception("Не удалось запустить сетевой агент")

    def _open_admin_in_browser(self):
        """Открывает URL админки в системном браузере."""
        agent = getattr(self, "network_agent", None)
        if not agent:
            QMessageBox.warning(self, "Админка", "Агент ещё не запущен.")
            return
        url = agent.get_admin_url()
        if not url:
            QMessageBox.information(
                self, "Админка",
                "Пока не нашли главного в локальной сети.\n"
                "Если этот ноутбук должен быть главным — "
                "включите его первым.",
            )
            return
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.warning(self, "Админка", f"Ошибка: {e}")

    def _refresh_admin_qr(self):
        """Обновляет QR-картинку по текущему состоянию агента."""
        if not hasattr(self, "qr_label"):
            return
        agent = getattr(self, "network_agent", None)
        if not agent:
            return
        url = agent.get_admin_url()
        if not url:
            self.qr_label.setText(
                "(QR появится\nкогда я — host\nили найду host)"
            )
            return
        pix = agent.get_qr_pixmap(size=180)
        if pix is None:
            self.qr_label.setText(
                f"Админка:\n{url}\n\n(qrcode не установлен)"
            )
            return
        self.qr_label.setPixmap(pix)
        self.qr_label.setToolTip(url)

    def apply_network_settings(self):
        if not self._confirm_admin_password(
            "Сетевые настройки",
            "Введите пароль для применения сетевых настроек:",
        ):
            return
        new_agent_name = self.agent_id_edit.text().strip()
        self.config["agent_name"] = new_agent_name
        self.config["auto_update"] = self.auto_update_check.isChecked()
        self.config["host_mode"] = self.host_mode_check.isChecked()
        if self.config_manager.save(self.config):
            if getattr(self, "network_agent", None) is not None:
                self.network_agent.apply_agent_name(new_agent_name)
            QMessageBox.information(
                self, "Сохранено",
                "Настройки сохранены. Агент перезапустится автоматически "
                "и либо останется главным, либо подключится к существующему.",
            )
            self._restart_network_agent()
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось сохранить настройки")

    def force_host_action(self):
        """Обработка нажатия на кнопку принудительного хостинга с проверкой пароля."""
        if not self._confirm_admin_password(
            "Смена роли",
            "Введите пароль для принудительного назначения этого ПК главным:",
        ):
            return
        
        if getattr(self, "network_agent", None) is not None:
            self.network_agent.force_become_host()
            QMessageBox.information(
                self, "Успех", 
                "Команда выполнена. В течение нескольких секунд этот ПК станет главным, а прошлый хост перейдет в режим клиента."
            )
            self.statusBar().showMessage("Этот ПК назначен главным", 3000)
        else:
            QMessageBox.warning(self, "Ошибка", "Сетевой агент не запущен.")

    def _restart_network_agent(self):
        """Перезапуск агента после смены настроек."""
        try:
            if getattr(self, "network_agent", None) is not None:
                self.network_agent.stop()
        except Exception:
            pass
        self._start_network_agent()

    def _integrity_guard_loop(self):
        while getattr(self, "_integrity_guard_running", False):
            try:
                if self.config.get("enable_autostart", True):
                    if not self.task_scheduler.is_task_exists():
                        self.task_scheduler.create_startup_task()
                    if not self.autostart.is_autostart_enabled():
                        self.autostart.set_autostart()
            except Exception:
                logger.exception("Не удалось восстановить автозапуск")
            time.sleep(120)

    def _check_updates_now(self):
        try:
            ok, info = self.auto_updater.check_now()
            if not ok:
                QMessageBox.warning(
                    self, "Обновление",
                    f"Не удалось проверить обновления: "
                    f"{info.get('error', 'unknown')}",
                )
                return
            tag = (info.get("tag_name") or "").lstrip("v")
            current = CURRENT_VERSION
            if tag == current:
                QMessageBox.information(
                    self, "Обновление",
                    f"Установлена актуальная версия ({current}).",
                )
            else:
                QMessageBox.information(
                    self, "Обновление",
                    f"Доступна новая версия: v{tag}\n"
                    f"Текущая: v{current}\n\n"
                    f"Если включено автообновление — оно скачается "
                    f"в ближайшие минуты.",
                )
        except Exception as e:
            QMessageBox.warning(self, "Обновление", f"Ошибка: {e}")

    def _apply_config_from_server(self, command: dict):
        """Безопасное применение конфига от сервера в главном потоке GUI."""
        try:
            payload = command.get("payload") or {}
            new_cfg = command.get("config") or payload.get("config") or {}
            
            if not new_cfg:
                logger.warning("[server] получен пустой конфиг или неверная структура")
                return

            # --- НОВЫЙ КОД: Защита уникальных данных компьютера ---
            # Эти ключи никогда не должны затираться общим шаблоном конфига
            protected_keys = ["agent_id", "agent_name", "password_hash", "profile_name"]
            for key in protected_keys:
                new_cfg.pop(key, None) # Безопасно удаляем ключ из присланного конфига
            # ------------------------------------------------------

            self.config.update(new_cfg)

            # Сохраняем обновленный конфиг
            if self.config_manager.save(self.config):
                self.load_lists_to_ui()
                self.refresh_profiles_list()
                self.apply_theme()
                if self.is_monitoring:
                    self.apply_blocking()
                logger.info("[server] конфигурация успешно применена и сохранена")
            else:
                logger.error("[server] не удалось сохранить обновленную конфигурацию")

        except Exception as e:
            logger.exception(f"[server] ошибка при применении конфигурации: {e}")


    def on_server_command(self, command: dict):
        """Обработка команды от сервера (вызывается из NetworkAgent)."""
        try:
            cmd = command.get("command")
            from functools import partial

            if cmd == "lockscreen_on":
                # Включаем блокировку экрана (локально)
                QTimer.singleShot(0, self.lockscreen_on)
                logger.info("[server] команда: lockscreen_on")
                
            if cmd == "lockscreen_off":
                # Выключаем блокировку экрана (локально)
                QTimer.singleShot(0, self.lockscreen_off)
                logger.info("[server] команда: lockscreen_off")

            if cmd == "start_protection":
                if not self.is_monitoring:
                    # Передаем ссылку на метод без круглых скобок ()
                    QTimer.singleShot(0, self._safe_start_protection)
                logger.info("[server] команда: start_protection")
                
            elif cmd == "stop_protection":
                # Принудительно останавливаем — даже если локальное
                # состояние успело разъехаться с серверным, выполняем,
                # иначе защита «зависает» во включённом состоянии.
                
                # Используем partial, чтобы безопасно «заморозить» аргумент from_remote=True
                QTimer.singleShot(
                    0, partial(self._safe_stop_protection, from_remote=True)
                )
                logger.info("[server] команда: stop_protection")
            elif cmd == "apply_config":
                # Замораживаем аргумент command и вызываем выделенный метод в главном потоке
                from functools import partial
                QTimer.singleShot(0, partial(self._apply_config_from_server, command))
                logger.info("[server] команда apply_config отправлена в главный поток")
            elif cmd == "rename_agent":
                payload = command.get("payload") or {}
                new_name = (command.get("agent_name")
                            or payload.get("agent_name") or "").strip()
                if new_name:
                    self.config["agent_name"] = new_name
                    if getattr(self, "network_agent", None) is not None:
                        self.network_agent.apply_agent_name(new_name)
                    if hasattr(self, "agent_id_edit"):
                        self.agent_id_edit.setText(new_name)
                    self.config_manager.save(self.config)
                    logger.info(f"[server] имя компьютера изменено: {new_name}")
            elif cmd == "shutdown_pc":
                logger.info("[server] команда: shutdown_pc")
                self._shutdown_computer()
            elif cmd == "update":
                payload = command.get("payload") or {}
                url = command.get("url") or payload.get("url")
                version = command.get("version") or payload.get("version") or ""
                if url:
                    logger.info(f"[server] update {version} -> {url}")
                    QMessageBox.information(
                        self, "Обновление",
                        f"Сервер запросил обновление до v{version}.\n"
                        f"Файл: {url}\nСкачайте вручную или дождитесь "
                        f"автообновления.",
                    )
        except Exception:
            logger.exception("Ошибка обработки команды сервера")

    # ------------- Защита (мониторинг) -------------

    def _safe_start_protection(self):
        """Запуск защиты по команде сервера — без диалогов, с защитой от race."""
        try:
            if self.is_monitoring:
                return
            self.start_protection()
        except Exception:
            logger.exception("remote start_protection failed")

    def _safe_stop_protection(self, from_remote: bool = False):
        """Остановка защиты по команде сервера — без диалогов, с защитой от race."""
        try:
            if self.is_monitoring:
                self.stop_protection(from_remote=from_remote)
        except Exception:
            logger.exception("remote stop_protection failed")

    def start_protection(self):
        if self.is_monitoring:
            return
        self.save_lists_from_ui()
        self.apply_blocking()
        self.is_monitoring = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.update_status()

        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        logger.info("Защита запущена")
        self.statusBar().showMessage("Защита активна", 3000)

    def stop_protection(self, from_remote=False):
        """Остановка защиты (локально под паролем или удаленно по команде сервера)."""
        if not from_remote:
            # Запрашиваем пароль ТОЛЬКО если выключение идет вручную на самом ПК
            pw, ok = QInputDialog.getText(
                self, "Остановка защиты", "Введите администраторский пароль:", QLineEdit.Password
            )
            if not ok:
                return
            if hashlib.sha256((pw or "").encode()).hexdigest() != self.config.get("password_hash"):
                QMessageBox.warning(self, "Ошибка", "Неверный пароль")
                logger.warning("Попытка локальной остановки с неверным паролем")
                return

        # --- Остановка (один раз, для обоих вариантов выключения) ---
        self.is_monitoring = False  # Останавливает фоновый цикл мониторинга
        logger.info(f"Защита остановлена {'удаленно через сервер' if from_remote else 'локально пользователем'}")

        # Разблокируем сайты в hosts
        try:
            unblock_websites()
        except Exception as e:
            logger.error(f"Ошибка при разблокировке сайтов: {e}")

        # Переключаем кнопки в UI, иначе после выключения «Запустить защиту»
        # остаётся заблокированной и пользователь не может снова включить.
        try:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        except Exception as e:
            logger.error(f"Ошибка при обновлении кнопок: {e}")

        # Обновляем статус графического интерфейса
        try:
            self.update_status()
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса UI: {e}")

    def _shutdown_application(self):
        try:
            self._integrity_guard_running = False
        except Exception:
            pass
        try:
            if getattr(self, "network_agent", None) is not None:
                self.network_agent.stop()
        except Exception:
            pass
        try:
            if getattr(self, "auto_updater", None) is not None:
                self.auto_updater.stop()
        except Exception:
            pass
        QApplication.quit()

    def _shutdown_computer(self):
        try:
            self._shutdown_application()
        except Exception:
            pass
        try:
            if os.name == "nt":
                popen_hidden(["shutdown", "/s", "/t", "0"])
            else:
                popen_hidden(["shutdown", "-h", "now"])
        except FileNotFoundError:
            try:
                if os.name != "nt":
                    popen_hidden(["systemctl", "poweroff"])
            except Exception as e:
                logger.error(f"Не удалось выключить компьютер: {e}")
        except Exception as e:
            logger.error(f"Не удалось выключить компьютер: {e}")

    def monitor_loop(self):
        while self.is_monitoring:
            try:
                # Добавлено: экстренный выход, если защиту отключили удаленно
                if not self.is_monitoring:
                    break

                processes = self.config.get("blocked_processes", [])
                if processes:
                    kill_processes(
                        processes,
                        notification_callback=self.show_notification,
                    )
                
                interval = max(1, self.config.get("check_interval", 5))
                for _ in range(interval * 10):
                    if not self.is_monitoring:
                        return  # Немедленный выход из фонового потока
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Ошибка в мониторинге: {e}")
                time.sleep(1)

    def show_notification(self, process_name):
        if not self.config.get("show_notifications", True):
            return
        try:
            msg = self.config.get("notification_message", "Доступ запрещен!")
            if self.tray_icon and self.tray_icon.isVisible():
                self.tray_icon.showMessage(
                    "Anti-Game Controller",
                    f"Закрыт процесс: {process_name}\n{msg}",
                    QSystemTrayIcon.Warning,
                    3000,
                )
        except Exception as e:
            logger.error(f"Ошибка уведомления: {e}")

    def update_status(self):
        if self.is_monitoring:
            self.status_label.setText("Активно")
            self.status_label.setObjectName("statusActive")
        else:
            self.status_label.setText("Неактивно")
            self.status_label.setObjectName("statusInactive")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def change_password(self):
        dlg = ChangePasswordDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        old, new, confirm = dlg.get_data()
        if not old or not new:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля")
            return
        if new != confirm:
            QMessageBox.warning(self, "Ошибка", "Пароли не совпадают")
            return
        if len(new) < 3:
            QMessageBox.warning(self, "Ошибка", "Пароль должен быть не менее 3 символов")
            return

        old_hash = hashlib.sha256(old.encode()).hexdigest()
        if old_hash != self.config.get("password_hash"):
            QMessageBox.warning(self, "Ошибка", "Неверный текущий пароль")
            logger.warning("Смена пароля: неверный старый пароль")
            return

        self.config["password_hash"] = hashlib.sha256(new.encode()).hexdigest()
        if self.config_manager.save(self.config):
            # Обновим и сохранённую копию в хранилище (последний сохранённый профиль)
            try:
                # Сохраняем текущий конфиг как профиль "default" (overwrite)
                config_storage.save_config(
                    self.config.get("profile_name", "default"), self.config
                )
            except Exception:
                pass
            QMessageBox.information(self, "Успех", "Пароль изменён")
            logger.info("Пароль изменён")
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось сохранить пароль")

    def _confirm_admin_password(self, title: str, prompt: str) -> bool:
        pw, ok = QInputDialog.getText(
            self,
            title,
            prompt,
            QLineEdit.Password,
        )
        if not ok:
            return False
        if not self.check_password(pw):
            QMessageBox.warning(self, title, "Неверный пароль")
            logger.warning(f"Отказано в доступе для действия: {title}")
            return False
        return True

    def check_password(self, password: str) -> bool:
        return hashlib.sha256((password or "").encode()).hexdigest() == self.config.get(
            "password_hash"
        )

    def close_with_password(self):
        dlg = PasswordDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return False
        if not self.check_password(dlg.get_password()):
            QMessageBox.warning(self, "Ошибка", "Неверный пароль")
            logger.warning("Попытка закрытия с неверным паролем")
            return False
        return True

    def exit_from_tray(self):
        if not self.close_with_password():
            return
        self._exit_requested = True
        if self.is_monitoring:
            self.stop_protection(from_remote=True)
        self._shutdown_application()

    def closeEvent(self, event):
        if self._exit_requested:
            event.accept()
            return
        if self.hide_to_tray():
            event.ignore()
            return
        if self.close_with_password():
            self._exit_requested = True
            if self.is_monitoring:
                self.stop_protection(from_remote=True)
            self._shutdown_application()
            event.accept()
            return
        event.ignore()

    def refresh_logs(self):
        try:
            log_path = get_log_file_path()
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                lines_log = content.splitlines()
                if len(lines_log) > 200:
                    content = "\n".join(lines_log[-200:])
                self.log_text.setPlainText(content)

                cursor = self.log_text.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.log_text.setTextCursor(cursor)
                
            else:
                self.log_text.setPlainText("Файл лога не найден")
        except Exception as e:
            self.log_text.setPlainText(f"Ошибка чтения лога: {e}")


def main():
    if not _acquire_single_instance_lock():
        return
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = MainWindow()
    sys.exit(app.exec_())
 

if __name__ == "__main__":
    main()
