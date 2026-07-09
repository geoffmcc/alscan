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
QLabel#badgeAdded {
    background-color: rgba(166, 227, 161, 0.15);
    color: #a6e3a1;
    border: 1px solid #a6e3a1;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel#badgeRemoved {
    background-color: rgba(243, 139, 168, 0.15);
    color: #f38ba8;
    border: 1px solid #f38ba8;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel#badgeModified {
    background-color: rgba(137, 180, 250, 0.15);
    color: #89b4fa;
    border: 1px solid #89b4fa;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel#badgeMoved {
    background-color: rgba(250, 179, 135, 0.15);
    color: #fab387;
    border: 1px solid #fab387;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel#badgeRenamed {
    background-color: rgba(203, 166, 247, 0.15);
    color: #cba6f7;
    border: 1px solid #cba6f7;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QPushButton#compareModeBtn {
    background-color: transparent;
    color: #a6adc8;
    border: 1px solid #45475a;
    border-radius: 0px;
    padding: 4px 12px;
    font-size: 12px;
}
QPushButton#compareModeBtn:checked {
    background-color: #45475a;
    color: #cdd6f4;
}
QPushButton#compareModeBtn:first-child {
    border-top-left-radius: 4px;
    border-bottom-left-radius: 4px;
}
QPushButton#compareModeBtn:last-child {
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}
QFrame#compareSourceHeader {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
}
QWidget#compareToolbar {
    background-color: transparent;
}
QLabel#compareSourceA {
    color: #a6e3a1;
    font-size: 13px;
}
QLabel#compareSourceB {
    color: #89b4fa;
    font-size: 13px;
}
QLabel#compareSummary {
    color: #cdd6f4;
    font-size: 13px;
    padding: 8px;
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
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
QLabel#badgeAdded {
    background-color: rgba(64, 160, 43, 0.12);
    color: #40a02b;
    border: 1px solid #40a02b;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel#badgeRemoved {
    background-color: rgba(210, 15, 57, 0.12);
    color: #d20f39;
    border: 1px solid #d20f39;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel#badgeModified {
    background-color: rgba(4, 165, 229, 0.12);
    color: #04a5e5;
    border: 1px solid #04a5e5;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel#badgeMoved {
    background-color: rgba(254, 100, 11, 0.12);
    color: #fe640b;
    border: 1px solid #fe640b;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel#badgeRenamed {
    background-color: rgba(136, 57, 239, 0.12);
    color: #8839ef;
    border: 1px solid #8839ef;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QPushButton#compareModeBtn {
    background-color: transparent;
    color: #6c6f85;
    border: 1px solid #ccd0da;
    border-radius: 0px;
    padding: 4px 12px;
    font-size: 12px;
}
QPushButton#compareModeBtn:checked {
    background-color: #ccd0da;
    color: #4c4f69;
}
QPushButton#compareModeBtn:first-child {
    border-top-left-radius: 4px;
    border-bottom-left-radius: 4px;
}
QPushButton#compareModeBtn:last-child {
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}
QFrame#compareSourceHeader {
    background-color: #e6e9ef;
    border: 1px solid #ccd0da;
    border-radius: 6px;
}
QWidget#compareToolbar {
    background-color: transparent;
}
QLabel#compareSourceA {
    color: #40a02b;
    font-size: 13px;
}
QLabel#compareSourceB {
    color: #04a5e5;
    font-size: 13px;
}
QLabel#compareSummary {
    color: #4c4f69;
    font-size: 13px;
    padding: 8px;
    background-color: #e6e9ef;
    border: 1px solid #ccd0da;
    border-radius: 6px;
}
"""


_COMPARE_MINIMAL_STYLESHEET = """
QLabel#badgeAdded {
    background-color: rgba(0, 128, 0, 0.12);
    color: #208020;
    border: 1px solid #208020;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel#badgeRemoved {
    background-color: rgba(200, 0, 0, 0.12);
    color: #c02020;
    border: 1px solid #c02020;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel#badgeModified {
    background-color: rgba(0, 100, 200, 0.12);
    color: #2060c0;
    border: 1px solid #2060c0;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel#badgeMoved {
    background-color: rgba(200, 120, 0, 0.12);
    color: #c06000;
    border: 1px solid #c06000;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QLabel#badgeRenamed {
    background-color: rgba(100, 30, 200, 0.12);
    color: #6020c0;
    border: 1px solid #6020c0;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: bold;
}
QPushButton#compareModeBtn {
    background-color: transparent;
    color: palette(text);
    border: 1px solid palette(mid);
    border-radius: 0px;
    padding: 4px 12px;
    font-size: 12px;
}
QPushButton#compareModeBtn:checked {
    background-color: palette(midlight);
    color: palette(text);
}
QPushButton#compareModeBtn:first-child {
    border-top-left-radius: 4px;
    border-bottom-left-radius: 4px;
}
QPushButton#compareModeBtn:last-child {
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}
QFrame#compareSourceHeader {
    background-color: palette(window);
    border: 1px solid palette(mid);
    border-radius: 6px;
}
QWidget#compareToolbar {
    background-color: transparent;
}
QLabel#compareSourceA {
    color: #40a02b;
    font-size: 13px;
}
QLabel#compareSourceB {
    color: #04a5e5;
    font-size: 13px;
}
QLabel#compareSummary {
    font-size: 13px;
    padding: 8px;
    background-color: palette(window);
    border: 1px solid palette(mid);
    border-radius: 6px;
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
            app.setStyleSheet(_COMPARE_MINIMAL_STYLESHEET)
        else:
            app.setStyleSheet(DARK_STYLESHEET)


def theme_mode_from_string(s: str) -> ThemeMode:
    try:
        return ThemeMode(s)
    except ValueError:
        return ThemeMode.SYSTEM
