# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from alscan.gui.app import create_app
from alscan.gui import APP_NAME


def test_create_app():
    app = create_app([])
    assert isinstance(app, QApplication)
    assert app.applicationName() == APP_NAME
