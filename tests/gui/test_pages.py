# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QLineEdit, QTreeWidget, QTableWidget

from alscan.gui.pages.home_page import HomePage
from alscan.gui.pages.scan_page import ScanPage
from alscan.gui.pages.batch_page import BatchPage
from alscan.gui.pages.checks_page import ChecksPage
from alscan.gui.pages.snapshots_page import SnapshotsPage
from alscan.gui.pages.compare_page import ComparePage
from alscan.gui.pages.three_way_page import ThreeWayPage
from alscan.gui.pages.settings_page import SettingsPage


class TestHomePage:
    def test_create(self, qtbot, app_settings):
        page = HomePage(recent_paths=[])
        qtbot.addWidget(page)
        assert page.isVisible() is False

    def test_recent_paths_shown(self, qtbot):
        page = HomePage(recent_paths=["/a.als", "/b.als"])
        qtbot.addWidget(page)
        assert page.recent_list.count() == 2

    def test_empty_recent_shows_placeholder(self, qtbot):
        page = HomePage(recent_paths=[])
        qtbot.addWidget(page)
        assert page.recent_list.count() == 1
        assert "No recent" in page.recent_list.item(0).text()

    def test_update_recent(self, qtbot):
        page = HomePage(recent_paths=[])
        qtbot.addWidget(page)
        page.update_recent(["/new.als"])
        assert page.recent_list.count() == 1

    def test_signals_exist(self, qtbot):
        page = HomePage(recent_paths=[])
        qtbot.addWidget(page)
        assert page.scan_path is not None
        assert page.scan_folder is not None
        assert page.compare_requested is not None
        assert page.snapshot_requested is not None
        assert page.three_way_requested is not None


class TestScanPage:
    def test_create(self, qtbot, app_settings):
        page = ScanPage(app_settings)
        qtbot.addWidget(page)
        assert page.isVisible() is False
        assert page.path_input is not None
        assert page.scan_btn is not None

    def test_set_path(self, qtbot, app_settings):
        page = ScanPage(app_settings)
        qtbot.addWidget(page)
        page.set_path("/some/project.als")
        assert page.path_input.text() == "/some/project.als"

    def test_initial_export_buttons_hidden(self, qtbot, app_settings):
        page = ScanPage(app_settings)
        qtbot.addWidget(page)
        assert page.export_json_btn.isVisible() is False
        assert page.export_html_btn.isVisible() is False
        assert page.rescan_btn.isVisible() is False

    def test_empty_path_no_scan(self, qtbot, app_settings):
        page = ScanPage(app_settings)
        qtbot.addWidget(page)
        page._start_scan()
        # should not crash when path is empty
        assert page.scan_btn.isEnabled()


class TestBatchPage:
    def test_create(self, qtbot):
        page = BatchPage()
        qtbot.addWidget(page)
        assert page.path_input is not None
        assert page.scan_btn is not None

    def test_set_path(self, qtbot):
        page = BatchPage()
        qtbot.addWidget(page)
        page.set_path("/some/folder")
        assert page.path_input.text() == "/some/folder"

    def test_table_headers(self, qtbot):
        page = BatchPage()
        qtbot.addWidget(page)
        assert page.table.columnCount() == 5
        headers = [page.table.horizontalHeaderItem(i).text() for i in range(5)]
        assert headers == ["Project", "Status", "Errors", "Warnings", "Info"]

    def test_empty_path_no_scan(self, qtbot):
        page = BatchPage()
        qtbot.addWidget(page)
        page._start_scan()
        assert page.scan_btn.isEnabled()


class TestChecksPage:
    def test_create(self, qtbot):
        page = ChecksPage()
        qtbot.addWidget(page)
        assert page.table.rowCount() > 0

    def test_columns(self, qtbot):
        page = ChecksPage()
        qtbot.addWidget(page)
        assert page.table.columnCount() == 3
        headers = [page.table.horizontalHeaderItem(i).text() for i in range(3)]
        assert headers == ["Check ID", "Severity", "Description"]


class TestSnapshotsPage:
    def test_create(self, qtbot, app_settings):
        page = SnapshotsPage(app_settings)
        qtbot.addWidget(page)
        assert page.snap_path_input is not None
        assert page.snap_btn is not None

    def test_set_path(self, qtbot, app_settings):
        page = SnapshotsPage(app_settings)
        qtbot.addWidget(page)
        page.snap_path_input.setText("/test.als")
        assert page.snap_path_input.text() == "/test.als"


class TestComparePage:
    def test_create(self, qtbot):
        page = ComparePage()
        qtbot.addWidget(page)
        assert page.path_a_input is not None
        assert page.path_b_input is not None
        assert page.compare_btn is not None

    def test_set_sources(self, qtbot):
        page = ComparePage()
        qtbot.addWidget(page)
        page.set_sources("/a.als", "/b.als")
        assert page.path_a_input.text() == "/a.als"
        assert page.path_b_input.text() == "/b.als"

    def test_empty_paths_no_compare(self, qtbot):
        page = ComparePage()
        qtbot.addWidget(page)
        page._start_compare()
        assert page.compare_btn.isEnabled()

    def test_result_tree_hidden_initially(self, qtbot):
        page = ComparePage()
        qtbot.addWidget(page)
        assert page.result_tree.isVisible() is False


class TestThreeWayPage:
    def test_create(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.base_input is not None
        assert page.ours_input is not None
        assert page.theirs_input is not None
        assert page.analyze_btn is not None

    def test_set_sources(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        page.set_sources("/b.als", "/o.als", "/t.als")
        assert page.base_input.text() == "/b.als"
        assert page.ours_input.text() == "/o.als"
        assert page.theirs_input.text() == "/t.als"

    def test_allow_unrelated_default(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.allow_unrelated.isChecked() is False

    def test_export_buttons_hidden_initially(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.save_json_btn.isVisible() is False
        assert page.save_html_btn.isVisible() is False

    def test_result_tree_hidden_initially(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.result_tree.isVisible() is False


class TestSettingsPage:
    def test_create(self, qtbot, app_settings):
        page = SettingsPage(app_settings)
        qtbot.addWidget(page)
        assert page.theme_combo is not None
        assert page.verbose_check is not None

    def test_theme_combo_default(self, qtbot, app_settings):
        page = SettingsPage(app_settings)
        qtbot.addWidget(page)
        assert page.theme_combo.currentText() == "system"

    def test_verbose_check_default(self, qtbot, app_settings):
        page = SettingsPage(app_settings)
        qtbot.addWidget(page)
        assert page.verbose_check.isChecked() is False

    def test_max_recent_default(self, qtbot, app_settings):
        page = SettingsPage(app_settings)
        qtbot.addWidget(page)
        assert page.max_recent_spin.value() == 10
