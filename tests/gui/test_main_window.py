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


class TestAboutDialog:
    def test_help_menu_exists(self, qtbot, app_settings):
        window = MainWindow(app_settings)
        qtbot.addWidget(window)
        menu_bar = window.menuBar()
        menus = [a.text() for a in menu_bar.actions()]
        assert "Help" in menus, f"Help menu not found in {menus}"

    def test_about_action_exists(self, qtbot, app_settings):
        window = MainWindow(app_settings)
        qtbot.addWidget(window)
        menu_bar = window.menuBar()
        help_menu = None
        for action in menu_bar.actions():
            if action.text() == "Help":
                help_menu = action.menu()
                break
        assert help_menu is not None, "Help menu not found"
        actions = [a.text() for a in help_menu.actions()]
        assert "About ALScan" in actions, f"About action not found in {actions}"

    def test_about_displays_version(self, monkeypatch, qtbot, app_settings):
        from alscan import __version__
        from PySide6.QtWidgets import QMessageBox

        captured_text = []

        def fake_about(parent, title, text):
            captured_text.append(text)

        monkeypatch.setattr(QMessageBox, "about", fake_about)

        window = MainWindow(app_settings)
        qtbot.addWidget(window)
        window._show_about()

        assert len(captured_text) == 1
        assert __version__ in captured_text[0], (
            f"Version {__version__} not in about text: {captured_text[0][:200]}"
        )

    def test_about_does_not_contain_fallback(self, monkeypatch, qtbot, app_settings):
        from PySide6.QtWidgets import QMessageBox

        captured_text = []

        def fake_about(parent, title, text):
            captured_text.append(text)

        monkeypatch.setattr(QMessageBox, "about", fake_about)

        window = MainWindow(app_settings)
        qtbot.addWidget(window)
        window._show_about()

        assert len(captured_text) == 1
        assert "0.0.0+unknown" not in captured_text[0], (
            "About should not show fallback version"
        )

    def test_about_does_not_contain_hardcoded_version(self, monkeypatch, qtbot, app_settings):
        from PySide6.QtWidgets import QMessageBox

        captured_text = []

        def fake_about(parent, title, text):
            captured_text.append(text)

        monkeypatch.setattr(QMessageBox, "about", fake_about)

        window = MainWindow(app_settings)
        qtbot.addWidget(window)
        window._show_about()

        assert len(captured_text) == 1
        # The about text must import __version__ at call time, not hardcode
        # Verify it doesn't contain any hardcoded version like "0.6.0" etc
        import re
        hardcoded = re.findall(r'(?:^|[^+])0\.\d+\.\d+', captured_text[0])
        # The fuzzy match could catch 0.7.0 which IS the current version.
        # Instead, verify import __version__ is used at call time by
        # checking the source of _show_about.
        import inspect
        source = inspect.getsource(window._show_about)
        assert "from alscan import __version__" in source or "alscan.__version__" in source, (
            "About dialog must import __version__ at runtime, not hardcode"
        )
