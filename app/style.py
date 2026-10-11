# -*- coding: utf-8 -*-
"""全局界面样式（现代扁平化风格，浅色主题，中文界面）。"""
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPushButton

ACCENT = "#2D8CF0"
ACCENT_DARK = "#1F7DE0"
TEXT = "#1F2937"
TEXT_MUTED = "#6B7280"
BG = "#F2F5FA"
CARD = "#FFFFFF"
BORDER = "#E3E8F0"

QSS = """
* { outline: none; }
QWidget {
    font-family: "Microsoft YaHei", "Segoe UI", "PingFang SC", "Noto Sans CJK SC", sans-serif;
    font-size: 13px;
    color: #1F2937;
}
QMainWindow, QDialog { background: #F2F5FA; }
QLabel { background: transparent; }
QLabel[class="pageTitle"] { font-size: 15px; font-weight: 700; color: #111827; }
QLabel[class="sectionTitle"] { font-weight: 600; color: #374151; }
QLabel[class="hint"] { color: #9CA3AF; font-size: 12px; }
QLabel[class="big"] { font-size: 18px; font-weight: 700; color: #111827; }
QLabel[class="edited"] {
    color: #B45309; background: #FEF3C7; border-radius: 4px;
    padding: 1px 6px; font-size: 11px;
}

QGroupBox {
    background: #FFFFFF;
    border: 1px solid #E3E8F0;
    border-radius: 10px;
    margin-top: 16px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    top: -2px;
    padding: 0 8px;
    color: #2D8CF0;
    background: transparent;
}

QPushButton {
    background: #FFFFFF;
    border: 1px solid #D8DEE9;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 500;
}
QPushButton:hover { background: #F0F5FF; border-color: #2D8CF0; color: #1F5FBF; }
QPushButton:pressed { background: #E3EEFF; }
QPushButton:disabled { background: #F3F4F6; color: #B0B7C3; border-color: #E5E7EB; }
QPushButton[class="primary"] {
    background: #2D8CF0; color: #FFFFFF; border: none; font-weight: 600;
    padding: 9px 18px;
}
QPushButton[class="primary"]:hover { background: #1F7DE0; color: #FFFFFF; }
QPushButton[class="primary"]:pressed { background: #1868C2; }
QPushButton[class="primary"]:disabled { background: #A9CBF5; color: #EEF4FD; }
QPushButton[class="small"] { padding: 4px 8px; font-size: 12px; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #FFFFFF;
    border: 1px solid #D8DEE9;
    border-radius: 8px;
    padding: 5px 8px;
    selection-background-color: #2D8CF0;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #2D8CF0; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #7A8494;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background: #FFFFFF; border: 1px solid #D8DEE9; border-radius: 8px;
    selection-background-color: #E3EEFF; selection-color: #1F5FBF;
}

QSlider::groove:horizontal { height: 6px; background: #E3E8F0; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #2D8CF0; border-radius: 3px; }
QSlider::handle:horizontal {
    width: 15px; height: 15px; margin: -5px 0; border-radius: 8px;
    background: #FFFFFF; border: 2px solid #2D8CF0;
}

QToolButton {
    background: #FFFFFF; border: 1px solid #D8DEE9; border-radius: 8px;
    padding: 6px 12px; font-weight: 500;
}
QToolButton:hover { background: #F0F5FF; border-color: #2D8CF0; color: #1F5FBF; }
QToolButton:checked { background: #2D8CF0; border-color: #2D8CF0; color: #FFFFFF; font-weight: 600; }

QListWidget, QTableWidget, QPlainTextEdit, QTextEdit {
    background: #FFFFFF;
    border: 1px solid #E3E8F0;
    border-radius: 8px;
}
QListWidget::item { padding: 7px 8px; border-radius: 6px; margin: 1px 3px; }
QListWidget::item:selected { background: #E3EEFF; color: #1F5FBF; }
QListWidget::item:hover:!selected { background: #F5F8FD; }
QTableWidget { gridline-color: #EEF1F6; }
QTableWidget::item { padding: 4px 6px; }
QHeaderView::section {
    background: #F7F9FC; border: none; border-bottom: 1px solid #E3E8F0;
    padding: 7px; font-weight: 600; color: #4B5563;
}

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #C7CFDA; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #A9B4C4; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; width: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: #C7CFDA; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #A9B4C4; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { height: 0; width: 0; }

QToolTip { background: #1F2937; color: #FFFFFF; border: none; padding: 6px 8px; border-radius: 4px; }
QStatusBar { background: #FFFFFF; border-top: 1px solid #E3E8F0; color: #6B7280; }
QStatusBar::item { border: none; }
QMenu { background: #FFFFFF; border: 1px solid #E3E8F0; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 6px; }
QMenu::item:selected { background: #E3EEFF; color: #1F5FBF; }
QMenu::separator { height: 1px; background: #EEF1F6; margin: 5px 8px; }
QCheckBox { spacing: 6px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #C7CFDA; border-radius: 4px; background: #FFFFFF; }
QCheckBox::indicator:checked { background: #2D8CF0; border-color: #2D8CF0; }
"""


def make_button(text: str, kind: str = "default", parent=None) -> QPushButton:
    """创建带样式类别（primary / default / small）的按钮。"""
    btn = QPushButton(text, parent)
    btn.setProperty("class", kind)
    return btn


def apply_style(app) -> None:
    """给 QApplication 应用全局字体与 QSS。"""
    app.setFont(QFont("Microsoft YaHei", 10))
    app.setStyleSheet(QSS)
