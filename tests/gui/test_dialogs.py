# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from PySide6.QtWidgets import QDialogButtonBox

from alscan.gui.dialogs.error_dialog import ErrorDialog


class TestErrorDialog:
    def test_create(self, qtbot):
        dlg = ErrorDialog("Something went wrong", parent=None)
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "Error"
        assert dlg.isVisible() is False

    def test_message_shown(self, qtbot):
        dlg = ErrorDialog("Test error message", parent=None)
        qtbot.addWidget(dlg)
        dlg.show()
        assert dlg.isVisible()

    def test_with_details(self, qtbot):
        dlg = ErrorDialog("Error", "Traceback details here", parent=None)
        qtbot.addWidget(dlg)
        assert dlg.findChild(QDialogButtonBox) is not None

    def test_without_details(self, qtbot):
        dlg = ErrorDialog("Error", parent=None)
        qtbot.addWidget(dlg)
        assert dlg.findChild(QDialogButtonBox) is not None
