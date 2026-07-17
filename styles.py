# Темная тема
DARK_THEME = """
QMainWindow {
    background-color: #1e1e2e;
}

QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
}

/* Вкладки */
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #181825;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: #313244;
    color: #cdd6f4;
    padding: 12px 24px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: 600;
}

QTabBar::tab:hover:!selected {
    background-color: #45475a;
}

/* Кнопки */
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 10pt;
}

QPushButton:hover {
    background-color: #a6c9ff;
}

QPushButton:pressed {
    background-color: #6c9cd4;
}

QPushButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}

QPushButton#startButton {
    background-color: #a6e3a1;
    color: #1e1e2e;
}

QPushButton#startButton:hover {
    background-color: #b8f0b5;
}

QPushButton#stopButton {
    background-color: #f38ba8;
    color: #1e1e2e;
}

QPushButton#stopButton:hover {
    background-color: #ffa0ba;
}

QPushButton#deleteButton {
    background-color: #f38ba8;
    color: #1e1e2e;
}

QPushButton#deleteButton:hover {
    background-color: #ffa0ba;
}

QPushButton#addButton {
    background-color: #94e2d5;
    color: #1e1e2e;
}

QPushButton#addButton:hover {
    background-color: #a8f0e4;
}

/* Списки */
QListWidget {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 8px;
    color: #cdd6f4;
}

QListWidget::item {
    padding: 10px;
    border-radius: 4px;
    margin: 2px 0;
}

QListWidget::item:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
}

QListWidget::item:hover:!selected {
    background-color: #313244;
}

/* Labels */
QLabel {
    color: #cdd6f4;
    background-color: transparent;
}

QLabel#titleLabel {
    font-size: 14pt;
    font-weight: 700;
    color: #89b4fa;
}

QLabel#statusLabel {
    font-size: 11pt;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 6px;
}

QLabel#statusActive {
    background-color: #a6e3a1;
    color: #1e1e2e;
}

QLabel#statusInactive {
    background-color: #f38ba8;
    color: #1e1e2e;
}

/* Группы */
QGroupBox {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 20px;
    font-weight: 600;
    color: #89b4fa;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    color: #89b4fa;
}

/* Поля ввода */
QLineEdit {
    background-color: #181825;
    border: 2px solid #313244;
    border-radius: 6px;
    padding: 8px 12px;
    color: #cdd6f4;
}

QLineEdit:focus {
    border-color: #89b4fa;
}

QSpinBox {
    background-color: #181825;
    border: 2px solid #313244;
    border-radius: 6px;
    padding: 8px 12px;
    color: #cdd6f4;
}

QSpinBox:focus {
    border-color: #89b4fa;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #313244;
    border: none;
    width: 20px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #45475a;
}

/* Чекбоксы */
QCheckBox {
    spacing: 8px;
    color: #cdd6f4;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid #313244;
    background-color: #181825;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

QCheckBox::indicator:hover {
    border-color: #89b4fa;
}

/* Скроллбары */
QScrollBar:vertical {
    background-color: #181825;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Диалоги */
QDialog {
    background-color: #1e1e2e;
}

QMessageBox {
    background-color: #1e1e2e;
}

QMessageBox QLabel {
    color: #cdd6f4;
}

/* Меню */
QMenu {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 8px 20px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
}
"""

# Светлая тема
LIGHT_THEME = """
QMainWindow {
    background-color: #eff1f5;
}

QWidget {
    background-color: #eff1f5;
    color: #4c4f69;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
}

/* Вкладки */
QTabWidget::pane {
    border: 1px solid #dce0e8;
    background-color: #e6e9ef;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: #ccd0da;
    color: #4c4f69;
    padding: 12px 24px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #1e66f5;
    color: #eff1f5;
    font-weight: 600;
}

QTabBar::tab:hover:!selected {
    background-color: #bcc0cc;
}

/* Кнопки */
QPushButton {
    background-color: #1e66f5;
    color: #eff1f5;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 10pt;
}

QPushButton:hover {
    background-color: #4185ff;
}

QPushButton:pressed {
    background-color: #0d4db8;
}

QPushButton:disabled {
    background-color: #bcc0cc;
    color: #9ca0b0;
}

QPushButton#startButton {
    background-color: #40a02b;
    color: #eff1f5;
}

QPushButton#startButton:hover {
    background-color: #5cb83f;
}

QPushButton#stopButton {
    background-color: #d20f39;
    color: #eff1f5;
}

QPushButton#stopButton:hover {
    background-color: #e8385d;
}

QPushButton#deleteButton {
    background-color: #d20f39;
    color: #eff1f5;
}

QPushButton#deleteButton:hover {
    background-color: #e8385d;
}

QPushButton#addButton {
    background-color: #179299;
    color: #eff1f5;
}

QPushButton#addButton:hover {
    background-color: #1faeb5;
}

/* Списки */
QListWidget {
    background-color: #e6e9ef;
    border: 1px solid #dce0e8;
    border-radius: 6px;
    padding: 8px;
    color: #4c4f69;
}

QListWidget::item {
    padding: 10px;
    border-radius: 4px;
    margin: 2px 0;
}

QListWidget::item:selected {
    background-color: #1e66f5;
    color: #eff1f5;
}

QListWidget::item:hover:!selected {
    background-color: #ccd0da;
}

/* Labels */
QLabel {
    color: #4c4f69;
    background-color: transparent;
}

QLabel#titleLabel {
    font-size: 14pt;
    font-weight: 700;
    color: #1e66f5;
}

QLabel#statusLabel {
    font-size: 11pt;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 6px;
}

QLabel#statusActive {
    background-color: #40a02b;
    color: #eff1f5;
}

QLabel#statusInactive {
    background-color: #d20f39;
    color: #eff1f5;
}

/* Группы */
QGroupBox {
    background-color: #e6e9ef;
    border: 1px solid #dce0e8;
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 20px;
    font-weight: 600;
    color: #1e66f5;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    color: #1e66f5;
}

/* Поля ввода */
QLineEdit {
    background-color: #e6e9ef;
    border: 2px solid #dce0e8;
    border-radius: 6px;
    padding: 8px 12px;
    color: #4c4f69;
}

QLineEdit:focus {
    border-color: #1e66f5;
}

QSpinBox {
    background-color: #e6e9ef;
    border: 2px solid #dce0e8;
    border-radius: 6px;
    padding: 8px 12px;
    color: #4c4f69;
}

QSpinBox:focus {
    border-color: #1e66f5;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #ccd0da;
    border: none;
    width: 20px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #bcc0cc;
}

/* Чекбоксы */
QCheckBox {
    spacing: 8px;
    color: #4c4f69;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid #dce0e8;
    background-color: #e6e9ef;
}

QCheckBox::indicator:checked {
    background-color: #1e66f5;
    border-color: #1e66f5;
}

QCheckBox::indicator:hover {
    border-color: #1e66f5;
}

/* Скроллбары */
QScrollBar:vertical {
    background-color: #e6e9ef;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #bcc0cc;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #acb0be;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Диалоги */
QDialog {
    background-color: #eff1f5;
}

QMessageBox {
    background-color: #eff1f5;
}

QMessageBox QLabel {
    color: #4c4f69;
}

/* Меню */
QMenu {
    background-color: #e6e9ef;
    border: 1px solid #dce0e8;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 8px 20px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #1e66f5;
    color: #eff1f5;
}
"""
