# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from PySide6.QtWidgets import QStackedWidget

from alscan.gui.main_window import MainWindow, NavButton
from alscan.gui import APP_NAME, APP_VERSION


class TestNavButton:
    def test_create(self, qapp):
        btn = NavButton("Home", "home")
        assert btn.text() == "Home"
        assert btn.page_id == "home"
        assert btn.isCheckable()
        assert btn.isChecked() is False


class TestMainWindow:
    def test_create(self, qtbot, app_settings):
        window = MainWindow(app_settings)
        qtbot.addWidget(window)
        assert window.windowTitle() == f"{APP_NAME} v{APP_VERSION}"
        assert window.stack is not None
        assert window.stack.count() == 8

    def test_navigation(self, qtbot, app_settings):
        window = MainWindow(app_settings)
        qtbot.addWidget(window)
        window._navigate_to("scan")
        assert window.stack.currentIndex() == 1
        window._navigate_to("settings")
        assert window.stack.currentIndex() == 7
        window._navigate_to("home")
        assert window.stack.currentIndex() == 0

    def test_navigate_to_scan_sets_path(self, qtbot, app_settings):
        window = MainWindow(app_settings)
        qtbot.addWidget(window)
        window.scan_page.path_input.setText("/test.als")
        window._navigate_to("scan")
        assert window.stack.currentIndex() == 1
        assert window.scan_page.path_input.text() == "/test.als"

    def test_navigate_to_batch_sets_path(self, qtbot, app_settings):
        window = MainWindow(app_settings)
        qtbot.addWidget(window)
        window.batch_page.path_input.setText("/test/folder")
        window._navigate_to("batch")
        assert window.stack.currentIndex() == 2
        assert window.batch_page.path_input.text() == "/test/folder"

    def test_nav_buttons_checked_state(self, qtbot, app_settings):
        window = MainWindow(app_settings)
        qtbot.addWidget(window)
        window._navigate_to("scan")
        assert window._nav_buttons[1].isChecked()
        assert window._nav_buttons[0].isChecked() is False

    def test_status_bar_exists(self, qtbot, app_settings):
        window = MainWindow(app_settings)
        qtbot.addWidget(window)
        assert window.status_bar is not None
        assert window.status_label.text() == "Ready"

    def test_minimum_size(self, qtbot, app_settings):
        window = MainWindow(app_settings)
        qtbot.addWidget(window)
        min_size = window.minimumSize()
        assert min_size.width() >= 1000
        assert min_size.height() >= 650
