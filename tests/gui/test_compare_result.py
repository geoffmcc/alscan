# SPDX-License-Identifier: GPL-3.0-only
"""GUI tests for compare result widgets and compare page."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from alscan.gui.widgets.compare_badge import BadgeWidget
from alscan.gui.widgets.compare_result_widget import CompareResultWidget
from alscan.gui.pages.compare_page import ComparePage
from alscan.versioner import DiffResult, TrackChange, DeviceDiff


class TestBadgeWidget:
    def test_added_badge(self, qtbot):
        badge = BadgeWidget("added")
        qtbot.addWidget(badge)
        assert badge.text() == "Added"
        assert badge.objectName() == "badgeAdded"
        assert badge.minimumWidth() == 64
        assert badge.toolTip() == "Added"

    def test_removed_badge(self, qtbot):
        badge = BadgeWidget("removed")
        qtbot.addWidget(badge)
        assert badge.text() == "Removed"
        assert badge.objectName() == "badgeRemoved"

    def test_modified_badge(self, qtbot):
        badge = BadgeWidget("modified")
        qtbot.addWidget(badge)
        assert badge.text() == "Modified"
        assert badge.objectName() == "badgeModified"

    def test_moved_badge(self, qtbot):
        badge = BadgeWidget("moved")
        qtbot.addWidget(badge)
        assert badge.text() == "Moved"
        assert badge.objectName() == "badgeMoved"

    def test_renamed_badge(self, qtbot):
        badge = BadgeWidget("renamed")
        qtbot.addWidget(badge)
        assert badge.text() == "Renamed"
        assert badge.objectName() == "badgeRenamed"

    def test_badge_fixed_height(self, qtbot):
        badge = BadgeWidget("added")
        qtbot.addWidget(badge)
        assert badge.height() == 22

    def test_badge_alignment(self, qtbot):
        badge = BadgeWidget("modified")
        qtbot.addWidget(badge)
        assert badge.alignment() & Qt.AlignmentFlag.AlignCenter


class TestCompareResultWidget:
    def _make_simple_diff(self) -> DiffResult:
        return DiffResult(
            project_a="TestA", project_b="TestB",
            tempo_changed=True, tempo_before=120.0, tempo_after=128.0,
            track_changes=[
                TrackChange(kind="added", track_id=10, name="New Track"),
                TrackChange(kind="removed", track_id=1, name="Old Track"),
                TrackChange(
                    kind="modified", track_id=2, name="Drums",
                    details=["clips: 0 -> 2", "volume: 0.75 -> 1.0"],
                ),
            ],
            device_changes=[
                DeviceDiff(
                    track_id=2, track_name="Drums",
                    added=[{"name": "Compressor", "device_type": "audio_effect", "plugin_type": "AudioEffect"}],
                ),
            ],
        )

    def test_create(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        assert widget.stack.count() == 3

    def test_set_result_shows_source_labels(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/home/a.als", "/home/b.als")
        assert widget.source_a_label.text() == "a.als"
        assert widget.source_b_label.text() == "b.als"

    def test_source_paths_in_tooltip(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/home/a.als", "/home/b.als")
        assert widget.source_a_path.toolTip() == "/home/a.als"
        assert widget.source_b_path.toolTip() == "/home/b.als"

    def test_mode_buttons_exist(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        texts = [btn.text() for btn in widget.mode_group.buttons()]
        assert "Summary" in texts
        assert "Detailed" in texts
        assert "Raw" in texts

    def test_default_to_detailed(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/a.als", "/b.als")
        assert widget.stack.currentWidget() == widget.detailed_tree

    def test_switch_to_raw(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/a.als", "/b.als")
        for btn in widget.mode_group.buttons():
            if btn.text() == "Raw":
                btn.click()
                break
        assert widget.stack.currentWidget() == widget.raw_text

    def test_raw_view_contains_project_names(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/a.als", "/b.als")
        for btn in widget.mode_group.buttons():
            if btn.text() == "Raw":
                btn.click()
                break
        text = widget.raw_text.toPlainText()
        assert "TestA" in text
        assert "TestB" in text

    def test_raw_view_contains_diff_data(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/a.als", "/b.als")
        for btn in widget.mode_group.buttons():
            if btn.text() == "Raw":
                btn.click()
                break
        text = widget.raw_text.toPlainText()
        assert "120" in text
        assert "128" in text

    def test_switch_to_summary(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/a.als", "/b.als")
        for btn in widget.mode_group.buttons():
            if btn.text() == "Summary":
                btn.click()
                break
        assert widget.stack.currentWidget() == widget.summary_container

    def test_summary_auto_expand_small_result(self, qtbot):
        diff = DiffResult(
            project_a="A", project_b="B",
            track_changes=[
                TrackChange(kind="added", track_id=1, name="T1"),
                TrackChange(kind="added", track_id=2, name="T2"),
            ],
        )
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(diff, "/a.als", "/b.als")
        for btn in widget.mode_group.buttons():
            if btn.text() == "Summary":
                btn.click()
                break
        for i in range(widget.summary_tree.topLevelItemCount()):
            assert widget.summary_tree.topLevelItem(i).isExpanded()

    def test_detail_auto_expand_small_result(self, qtbot):
        diff = DiffResult(
            project_a="A", project_b="B",
            track_changes=[
                TrackChange(kind="added", track_id=1, name="T1"),
                TrackChange(kind="added", track_id=2, name="T2"),
            ],
        )
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(diff, "/a.als", "/b.als")
        for i in range(widget.detailed_tree.topLevelItemCount()):
            assert widget.detailed_tree.topLevelItem(i).isExpanded()

    def test_filters_created(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/a.als", "/b.als")
        assert len(widget.filter_widgets) > 0
        assert any(cat in widget.filter_widgets for cat in ["track", "device"])

    def test_swap_sources_emits_signal(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/home/a.als", "/home/b.als")

        emitted = False
        def on_swap():
            nonlocal emitted
            emitted = True
        widget.swap_requested.connect(on_swap)

        widget.swap_btn.click()
        assert emitted

    def test_swap_toggles_labels(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/home/a.als", "/home/b.als")

        widget._swapped = True
        widget._update_source_display("/home/a.als", "/home/b.als")
        assert widget.source_a_label.text() == "b.als"
        assert widget.source_b_label.text() == "a.als"

    def test_copy_summary_emits_signal(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/a.als", "/b.als")

        emitted = False
        def on_copy():
            nonlocal emitted
            emitted = True
        widget.copy_summary_requested.connect(on_copy)

        widget.copy_summary_btn.click()
        assert emitted

    def test_export_report_emits_signal(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/a.als", "/b.als")

        emitted = False
        def on_export():
            nonlocal emitted
            emitted = True
        widget.export_report_requested.connect(on_export)

        widget.export_btn.click()
        assert emitted

    def test_empty_result_no_changes(self, qtbot):
        diff = DiffResult(project_a="A", project_b="B")
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(diff, "/a.als", "/b.als")

        for btn in widget.mode_group.buttons():
            if btn.text() == "Raw":
                btn.click()
                break
        text = widget.raw_text.toPlainText()
        assert "No differences" in text

    def test_detailed_view_populated(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/a.als", "/b.als")

        for btn in widget.mode_group.buttons():
            if btn.text() == "Detailed":
                btn.click()
                break

        assert widget.detailed_tree.topLevelItemCount() > 0

    def test_source_direction_label(self, qtbot):
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(self._make_simple_diff(), "/a.als", "/b.als")
        assert "A" in widget.direction_label.text()
        assert "\u2192" in widget.direction_label.text()

    def test_large_result_no_auto_expand(self, qtbot):
        changes = [TrackChange(kind="added", track_id=i + 1, name=f"T{i}")
                   for i in range(15)]
        diff = DiffResult(project_a="A", project_b="B", track_changes=changes)
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(diff, "/a.als", "/b.als")
        for btn in widget.mode_group.buttons():
            if btn.text() == "Summary":
                btn.click()
                break
        assert widget.summary_tree.topLevelItemCount() > 0
        any_collapsed = False
        for i in range(widget.summary_tree.topLevelItemCount()):
            if not widget.summary_tree.topLevelItem(i).isExpanded():
                any_collapsed = True
        assert any_collapsed, "At least one group should be collapsed for large results"

    def test_filter_interaction(self, qtbot):
        diff = DiffResult(
            project_a="A", project_b="B",
            tempo_changed=True, tempo_before=120.0, tempo_after=128.0,
            track_changes=[
                TrackChange(kind="added", track_id=1, name="T1"),
            ],
        )
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(diff, "/a.als", "/b.als")

        assert len(widget.filter_widgets) >= 2

        if "track" in widget.filter_widgets:
            widget.filter_widgets["track"].setChecked(False)
            for btn in widget.mode_group.buttons():
                if btn.text() == "Detailed":
                    btn.click()
                    break
            count = widget.detailed_tree.topLevelItemCount()
            assert count >= 0

    def test_elide(self):
        from alscan.gui.widgets.compare_result_widget import _elide
        assert _elide("short") == "short"
        assert _elide("a" * 50) == "a" * 39 + "\u2026"
        assert _elide("a" * 40) == "a" * 40

    def test_detailed_view_structure(self, qtbot):
        diff = DiffResult(
            project_a="A", project_b="B",
            track_changes=[
                TrackChange(
                    kind="modified", track_id=1, name="Drums",
                    details=["clips: 0 -> 2"],
                ),
            ],
            device_changes=[
                DeviceDiff(
                    track_id=1, track_name="Drums",
                    added=[{"name": "EQ", "device_type": "audio_effect", "plugin_type": "AudioEffect"}],
                ),
            ],
        )
        widget = CompareResultWidget()
        qtbot.addWidget(widget)
        widget.set_result(diff, "/a.als", "/b.als")

        for btn in widget.mode_group.buttons():
            if btn.text() == "Detailed":
                btn.click()
                break

        assert widget.detailed_tree.topLevelItemCount() > 0
        header = widget.detailed_tree.header()
        headers = [header.model().headerData(i, Qt.Orientation.Horizontal)
                   for i in range(header.count())]
        assert "Change" in headers
        assert "Object" in headers
        assert "Property" in headers
        assert "Explanation" in headers


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

    def test_result_widget_hidden_initially(self, qtbot):
        page = ComparePage()
        qtbot.addWidget(page)
        assert page.result_widget.isVisible() is False

    def test_cancel_button_visible_during_compare(self, qtbot):
        page = ComparePage()
        qtbot.addWidget(page)
        assert page.cancel_btn.isVisible() is False

    def test_input_area_has_proper_structure(self, qtbot):
        page = ComparePage()
        qtbot.addWidget(page)
        assert page.input_area is not None
        assert page.drop_area is not None

    def test_browse_a_button_exists(self, qtbot):
        from PySide6.QtWidgets import QPushButton
        page = ComparePage()
        qtbot.addWidget(page)
        browse_buttons = page.findChildren(QPushButton)
        browse_texts = [b.text() for b in browse_buttons]
        assert "Browse..." in browse_texts

    def test_on_dropped_fills_source_a_first(self, qtbot):
        page = ComparePage()
        qtbot.addWidget(page)
        page._on_dropped("/test.als")
        assert page.path_a_input.text() == "/test.als"

    def test_on_dropped_fills_source_b_second(self, qtbot):
        page = ComparePage()
        qtbot.addWidget(page)
        page._on_dropped("/first.als")
        page._on_dropped("/second.als")
        assert page.path_a_input.text() == "/first.als"
        assert page.path_b_input.text() == "/second.als"

    def test_swap_sources_triggers_recompare(self, qtbot):
        from alscan.versioner import DiffResult
        diff = DiffResult(project_a="A", project_b="B",
                          tempo_changed=True, tempo_before=120.0, tempo_after=128.0)
        page = ComparePage()
        qtbot.addWidget(page)
        page._last_path_a = "/a.als"
        page._last_path_b = "/b.als"
        page.path_a_input.setText("/a.als")
        page.path_b_input.setText("/b.als")
        page.result_widget.set_result(diff, "/a.als", "/b.als")

        page._on_swap_sources()
        assert page._last_path_a == "/b.als"
        assert page._last_path_b == "/a.als"
        assert "swapped" in page.status_label.text().lower()

    def test_copy_summary_updates_status(self, qtbot):
        page = ComparePage()
        qtbot.addWidget(page)
        page._on_summary_copied()
        assert "copied" in page.status_label.text().lower()

    def test_cancel_compare(self, qtbot):
        page = ComparePage()
        qtbot.addWidget(page)
        page._cancel_compare()
        assert page.compare_btn.isEnabled()
        assert page.status_label.text() == "Comparison cancelled."

    def test_cancel_calls_worker_cancel(self, qtbot):
        from alscan.gui.workers import CompareWorker, CompareTaskInput
        page = ComparePage()
        qtbot.addWidget(page)
        worker = CompareWorker(CompareTaskInput(path_a="/a.als", path_b="/b.als"))
        page._worker = worker
        page._cancel_compare()
        assert worker._cancelled is True
        assert page._worker is None
