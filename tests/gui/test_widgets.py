# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from alscan.gui.widgets.result_table import (
    ResultTableWidget,
    FindingsTableModel,
    FindingsFilterProxy,
)
from alscan.gui.widgets.drop_area import DropArea, ThreeWayDropArea
from alscan.models import Finding


class TestFindingsTableModel:
    def test_row_count(self, sample_findings):
        model = FindingsTableModel(sample_findings)
        assert model.rowCount() == 3

    def test_column_count(self, sample_findings):
        model = FindingsTableModel(sample_findings)
        assert model.columnCount() == 5

    def test_column_names(self, sample_findings):
        model = FindingsTableModel(sample_findings)
        assert model.headerData(0, Qt.Orientation.Horizontal) == "Severity"
        assert model.headerData(1, Qt.Orientation.Horizontal) == "Check"
        assert model.headerData(4, Qt.Orientation.Horizontal) == "Message"

    def test_data_display(self, sample_findings):
        model = FindingsTableModel(sample_findings)
        assert model.data(model.index(0, 0)) == "ERROR"
        assert model.data(model.index(1, 0)) == "WARNING"
        assert model.data(model.index(2, 0)) == "INFO"

    def test_data_user_role(self, sample_findings):
        model = FindingsTableModel(sample_findings)
        f = model.data(model.index(0, 0), Qt.ItemDataRole.UserRole)
        assert f is sample_findings[0]

    def test_sort_by_severity(self, sample_findings):
        model = FindingsTableModel(sample_findings)
        model.sort(0, Qt.SortOrder.AscendingOrder)
        sev0 = model.data(model.index(0, 0))
        sev_last = model.data(model.index(2, 0))
        assert sev0 == "ERROR"
        assert sev_last == "INFO"


class TestFindingsFilterProxy:
    def test_no_filter_shows_all(self, sample_findings):
        model = FindingsTableModel(sample_findings)
        proxy = FindingsFilterProxy()
        proxy.setSourceModel(model)
        assert proxy.rowCount() == 3

    def test_severity_filter(self, sample_findings):
        model = FindingsTableModel(sample_findings)
        proxy = FindingsFilterProxy()
        proxy.setSourceModel(model)
        proxy.set_severity_filter("error")
        assert proxy.rowCount() == 1

    def test_search_filter(self, sample_findings):
        model = FindingsTableModel(sample_findings)
        proxy = FindingsFilterProxy()
        proxy.setSourceModel(model)
        proxy.set_search_text("Kick")
        assert proxy.rowCount() == 1

    def test_search_no_match(self, sample_findings):
        model = FindingsTableModel(sample_findings)
        proxy = FindingsFilterProxy()
        proxy.setSourceModel(model)
        proxy.set_search_text("zzzznotfound")
        assert proxy.rowCount() == 0


class TestResultTableWidget:
    def test_create(self, qtbot):
        widget = ResultTableWidget()
        qtbot.addWidget(widget)
        assert widget.count_label.text() == ""

    def test_set_findings(self, qtbot, sample_findings):
        widget = ResultTableWidget()
        qtbot.addWidget(widget)
        widget.set_findings(sample_findings)
        assert widget.model.rowCount() == 3
        assert "3" in widget.count_label.text()

    def test_severity_filter_updates_count(self, qtbot, sample_findings):
        widget = ResultTableWidget()
        qtbot.addWidget(widget)
        widget.set_findings(sample_findings)
        widget.severity_combo.setCurrentText("error")
        assert "1" in widget.count_label.text()

    def test_search_filters(self, qtbot, sample_findings):
        widget = ResultTableWidget()
        qtbot.addWidget(widget)
        widget.set_findings(sample_findings)
        widget.search_input.setText("Kick")
        assert "1" in widget.count_label.text()


class TestDropArea:
    def test_create(self, qtbot):
        area = DropArea("Drop files here")
        qtbot.addWidget(area)
        assert area.label.text() == "Drop files here"
        assert area.ACCEPTED_EXTS == {".als", ".json"}

    def test_accepts_als_ext(self):
        area = DropArea()
        assert ".als" in area.ACCEPTED_EXTS

    def test_accepts_json_ext(self):
        area = DropArea()
        assert ".json" in area.ACCEPTED_EXTS


class TestThreeWayDropArea:
    def test_create(self, qtbot):
        area = ThreeWayDropArea()
        qtbot.addWidget(area)
        assert area.label is not None
        assert "three" in area.label.text().lower()

    def test_initially_no_paths(self):
        area = ThreeWayDropArea()
        assert area._paths == []
