# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from PySide6.QtCore import QByteArray

from alscan.gui.settings import AppSettings


def test_default_theme(app_settings):
    assert app_settings.theme == "system"


def test_set_theme(app_settings):
    app_settings.theme = "dark"
    assert app_settings.theme == "dark"


def test_default_output_dir(app_settings):
    assert app_settings.default_output_dir == ""


def test_set_output_dir(app_settings):
    app_settings.default_output_dir = "/tmp/output"
    assert app_settings.default_output_dir == "/tmp/output"


def test_auto_open_reports_default(app_settings):
    assert app_settings.auto_open_reports is True


def test_auto_open_reports_toggle(app_settings):
    app_settings.auto_open_reports = False
    assert app_settings.auto_open_reports is False


def test_confirm_overwrite_default(app_settings):
    assert app_settings.confirm_overwrite is True


def test_verbose_scan_default(app_settings):
    assert app_settings.verbose_scan is False


def test_max_recent_default(app_settings):
    assert app_settings.max_recent == 10


def test_max_recent_set(app_settings):
    app_settings.max_recent = 5
    assert app_settings.max_recent == 5


def test_recent_paths_add(app_settings):
    app_settings.add_recent_path("/some/project.als")
    paths = app_settings.recent_paths
    assert len(paths) == 1
    assert paths[0].endswith("project.als")


def test_recent_paths_dedup(app_settings):
    app_settings.add_recent_path("/a/project.als")
    app_settings.add_recent_path("/a/project.als")
    assert len(app_settings.recent_paths) == 1


def test_recent_paths_order(app_settings):
    app_settings.add_recent_path("/first/project.als")
    app_settings.add_recent_path("/second/project.als")
    assert "second" in app_settings.recent_paths[0]


def test_recent_paths_max(app_settings):
    app_settings.max_recent = 3
    for i in range(5):
        app_settings.add_recent_path(f"/proj{i}/project.als")
    assert len(app_settings.recent_paths) == 3


def test_reset(app_settings):
    app_settings.theme = "dark"
    app_settings.verbose_scan = True
    app_settings.reset()
    assert app_settings.theme == "system"
    assert app_settings.verbose_scan is False


def test_window_geometry(app_settings):
    assert app_settings.window_geometry is None
    app_settings.window_geometry = QByteArray(b"test")
    assert app_settings.window_geometry == QByteArray(b"test")
