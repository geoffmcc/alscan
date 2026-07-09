# SPDX-License-Identifier: GPL-3.0-only
"""Application theme and stylesheet management."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


class ThemeMode(Enum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


DARK_STYLESHEET = """
QMainWindow, QDialog, QWidget#pageContainer {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QMenuBar, QMenuBar::item {
    background-color: #181825;
    color: #cdd6f4;
}
QMenuBar::item:selected { background-color: #313244; }
QMenu {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
}
QMenu::item:selected { background-color: #313244; }
QLabel {
    color: #cdd6f4;
}
QLabel#heading {
    font-size: 16px;
    font-weight: bold;
    color: #cba6f7;
}
QLabel#subheading {
    font-size: 13px;
    color: #a6adc8;
}
QLabel#errorText {
    color: #f38ba8;
}
QLabel#warningText {
    color: #fab387;
}
QLabel#infoText {
    color: #89b4fa;
}
QLabel#successText {
    color: #a6e3a1;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #585b70;
}
QPushButton:pressed {
    background-color: #585b70;
}
QPushButton:disabled {
    background-color: #181825;
    color: #585b70;
    border-color: #313244;
}
QPushButton#primaryButton {
    background-color: #cba6f7;
    color: #1e1e2e;
    border: none;
    font-weight: bold;
}
QPushButton#primaryButton:hover {
    background-color: #b4befe;
}
QPushButton#primaryButton:disabled {
    background-color: #585b70;
    color: #313244;
}
QPushButton#dangerButton {
    background-color: #f38ba8;
    color: #1e1e2e;
    border: none;
}
QPushButton#dangerButton:hover {
    background-color: #eba0ac;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #cba6f7;
}
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px;
}
QComboBox:focus { border-color: #cba6f7; }
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #45475a;
}
QTableView {
    background-color: #1e1e2e;
    alternate-background-color: #181825;
    color: #cdd6f4;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 4px;
    selection-background-color: #313244;
}
QTableView::item:selected {
    background-color: #45475a;
    color: #cdd6f4;
}
QHeaderView::section {
    background-color: #313244;
    color: #cdd6f4;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #45475a;
    font-weight: bold;
}
QTreeView {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 4px;
}
QTreeView::item:selected {
    background-color: #45475a;
}
QTabWidget::pane {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    padding: 8px 16px;
    border: 1px solid #313244;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QScrollBar:vertical {
    background: #181825;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #181825;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #45475a;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QListWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #45475a;
}
QGroupBox {
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #cba6f7;
}
QSplitter::handle {
    background-color: #313244;
}
QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
    height: 20px;
}
QProgressBar::chunk {
    background-color: #cba6f7;
    border-radius: 4px;
}
QCheckBox, QRadioButton {
    color: #cdd6f4;
}
QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px;
}
"""

LIGHT_STYLESHEET = """
QMainWindow, QDialog, QWidget#pageContainer {
    background-color: #eff1f5;
    color: #4c4f69;
}
QLabel {
    color: #4c4f69;
}
QLabel#heading {
    font-size: 16px;
    font-weight: bold;
    color: #8839ef;
}
QLabel#subheading {
    font-size: 13px;
    color: #6c6f85;
}
QLabel#errorText { color: #d20f39; }
QLabel#warningText { color: #fe640b; }
QLabel#infoText { color: #04a5e5; }
QLabel#successText { color: #40a02b; }
QPushButton {
    background-color: #e6e9ef;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #ccd0da;
}
QPushButton:pressed {
    background-color: #bcc0cc;
}
QPushButton:disabled {
    background-color: #e6e9ef;
    color: #9ca0b0;
    border-color: #ccd0da;
}
QPushButton#primaryButton {
    background-color: #8839ef;
    color: #eff1f5;
    border: none;
    font-weight: bold;
}
QPushButton#primaryButton:hover {
    background-color: #7287fd;
}
QPushButton#primaryButton:disabled {
    background-color: #bcc0cc;
    color: #9ca0b0;
}
QPushButton#dangerButton {
    background-color: #d20f39;
    color: #eff1f5;
    border: none;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #e6e9ef;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 4px;
    padding: 6px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #8839ef;
}
QComboBox {
    background-color: #e6e9ef;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 4px;
    padding: 6px;
}
QComboBox:focus { border-color: #8839ef; }
QComboBox QAbstractItemView {
    background-color: #e6e9ef;
    color: #4c4f69;
    selection-background-color: #ccd0da;
}
QTableView {
    background-color: #eff1f5;
    alternate-background-color: #e6e9ef;
    color: #4c4f69;
    gridline-color: #ccd0da;
    border: 1px solid #ccd0da;
    border-radius: 4px;
    selection-background-color: #ccd0da;
}
QHeaderView::section {
    background-color: #e6e9ef;
    color: #4c4f69;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #ccd0da;
    font-weight: bold;
}
QTreeView {
    background-color: #eff1f5;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 4px;
}
QTreeView::item:selected {
    background-color: #ccd0da;
}
QTabWidget::pane {
    background-color: #eff1f5;
    border: 1px solid #ccd0da;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #e6e9ef;
    color: #6c6f85;
    padding: 8px 16px;
    border: 1px solid #ccd0da;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #eff1f5;
    color: #4c4f69;
}
QScrollBar:vertical {
    background: #e6e9ef;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #bcc0cc;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QListWidget {
    background-color: #eff1f5;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #ccd0da;
}
QGroupBox {
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}
QGroupBox::title {
    color: #8839ef;
}
QSplitter::handle {
    background-color: #ccd0da;
}
QProgressBar {
    background-color: #e6e9ef;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #4c4f69;
    height: 20px;
}
QProgressBar::chunk {
    background-color: #8839ef;
    border-radius: 4px;
}
QCheckBox, QRadioButton {
    color: #4c4f69;
}
QToolTip {
    background-color: #e6e9ef;
    color: #4c4f69;
    border: 1px solid #ccd0da;
}
"""


def apply_theme(app: QApplication, mode: ThemeMode | str) -> None:
    if isinstance(mode, str):
        mode = ThemeMode(mode)

    if mode == ThemeMode.DARK:
        app.setStyleSheet(DARK_STYLESHEET)
    elif mode == ThemeMode.LIGHT:
        app.setStyleSheet(LIGHT_STYLESHEET)
    else:
        import sys
        if sys.platform == "win32" or sys.platform == "darwin":
            app.setStyleSheet("")
        else:
            app.setStyleSheet(DARK_STYLESHEET)


def theme_mode_from_string(s: str) -> ThemeMode:
    try:
        return ThemeMode(s)
    except ValueError:
        return ThemeMode.SYSTEM
