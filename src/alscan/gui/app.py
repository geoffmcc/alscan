# SPDX-License-Identifier: GPL-3.0-only
"""Application entry point and QApplication setup."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from alscan.gui import APP_NAME
from alscan.gui.main_window import MainWindow
from alscan.gui.settings import AppSettings
from alscan.gui.theme import apply_theme, theme_mode_from_string


def create_app(argv: list[str] | None = None) -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing

    if argv is None:
        argv = sys.argv

    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName(APP_NAME)
    QApplication.setApplicationDisplayName(APP_NAME)

    app = QApplication(argv)

    settings = AppSettings()
    theme_mode = theme_mode_from_string(settings.theme)
    apply_theme(app, theme_mode)

    return app


def run_gui() -> None:
    app = create_app()
    settings = AppSettings()
    window = MainWindow(settings)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
