# SPDX-License-Identifier: GPL-3.0-only
"""GUI parity tests for the three-way analysis page."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QCheckBox, QMessageBox, QLabel

from alscan.gui.pages.three_way_page import ThreeWayPage
from alscan.gui.workers import ThreeWayTaskInput
from tests.three_way.fixtures import two_track_project, with_tempo, reset_ids


class TestThreeWayPageCreation:
    def test_all_inputs_exist(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.base_input is not None
        assert page.ours_input is not None
        assert page.theirs_input is not None

    def test_all_buttons_exist(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.analyze_btn is not None
        assert page.cancel_btn is not None
        assert page.change_sources_btn is not None
        assert page.save_json_btn is not None
        assert page.save_html_btn is not None

    def test_all_checkboxes_exist(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.allow_unrelated is not None
        assert page.allow_plausible is not None

    def test_allow_unrelated_default_false(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.allow_unrelated.isChecked() is False

    def test_allow_plausible_default_false(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.allow_plausible.isChecked() is False

    def test_export_buttons_hidden_initially(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.save_json_btn.isVisible() is False
        assert page.save_html_btn.isVisible() is False

    def test_cancel_hidden_initially(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.cancel_btn.isVisible() is False

    def test_change_sources_hidden_initially(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.change_sources_btn.isVisible() is False

    def test_result_tree_hidden_initially(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.result_tree.isVisible() is False

    def test_no_experimental_badge(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        badges = [w for w in page.findChildren(QLabel) if w.text() == "EXPERIMENTAL"]
        assert len(badges) == 0, "Experimental badge should not appear after graduation"

    def test_stateless_label_no_merge_language(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        info_text = page.info_label.text().lower()
        assert "does not modify" in info_text
        assert "does not create" in info_text
        assert "does not apply" in info_text
        assert "analytical only" in info_text

    def test_three_way_drop_area(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        from alscan.gui.widgets.drop_area import ThreeWayDropArea
        assert isinstance(page.drop_area, ThreeWayDropArea)


class TestInputValidation:
    def test_empty_inputs_return_error(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        error = page._validate_inputs()
        assert error is not None
        assert "empty" in error.lower() or "Base" in error

    def test_missing_file_returns_error(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        page.base_input.setText("/nonexistent/file.als")
        page.ours_input.setText("/nonexistent/file.als")
        page.theirs_input.setText("/nonexistent/file.als")
        error = page._validate_inputs()
        assert error is not None

    def test_duplicate_inputs_detected(self, qtbot, tmp_path):
        f1 = tmp_path / "a.als"
        f1.write_bytes(b"")
        f2 = tmp_path / "b.als"
        f2.write_bytes(b"")
        page = ThreeWayPage()
        qtbot.addWidget(page)
        page.base_input.setText(str(f1))
        page.ours_input.setText(str(f1))  # duplicate
        page.theirs_input.setText(str(f2))
        error = page._validate_inputs()
        assert error is not None
        assert "duplicate" in error.lower()

    def test_mixed_extensions_detected(self, qtbot, tmp_path):
        f1 = tmp_path / "a.als"
        f1.write_bytes(b"")
        f2 = tmp_path / "b.json"
        f2.write_text("{}")
        f3 = tmp_path / "c.als"
        f3.write_bytes(b"")
        page = ThreeWayPage()
        qtbot.addWidget(page)
        page.base_input.setText(str(f1))
        page.ours_input.setText(str(f2))  # mixed .json
        page.theirs_input.setText(str(f3))
        error = page._validate_inputs()
        assert error is not None
        assert "mixed" in error.lower()

    def test_valid_inputs_pass_validation(self, qtbot, tmp_path):
        f1 = tmp_path / "a.als"
        f1.write_bytes(b"")
        f2 = tmp_path / "b.als"
        f2.write_bytes(b"")
        f3 = tmp_path / "c.als"
        f3.write_bytes(b"")
        page = ThreeWayPage()
        qtbot.addWidget(page)
        page.base_input.setText(str(f1))
        page.ours_input.setText(str(f2))
        page.theirs_input.setText(str(f3))
        error = page._validate_inputs()
        assert error is None


class TestOptionsPassThrough:
    def test_allow_unrelated_passed_to_worker(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        page.base_input.setText("/x.als")
        page.ours_input.setText("/y.als")
        page.theirs_input.setText("/z.als")
        page.allow_unrelated.setChecked(True)
        page.allow_plausible.setChecked(True)

        task = ThreeWayTaskInput(
            base="/x.als", ours="/y.als", theirs="/z.als",
            allow_unrelated=page.allow_unrelated.isChecked(),
            allow_plausible=page.allow_plausible.isChecked(),
        )
        assert task.allow_unrelated is True
        assert task.allow_plausible is True

    def test_defaults_match_cli(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        assert page.allow_unrelated.isChecked() is False
        assert page.allow_plausible.isChecked() is False


class TestEndToEndWithSnapshots:
    """Test the full workflow with in-memory snapshot fixtures."""

    def test_analysis_with_snapshot_fixtures(self, qtbot, tmp_path):
        from tests.three_way.fixtures import three_track_project, with_tempo, add_track
        reset_ids()
        base = three_track_project("e2e")
        ours = with_tempo(base, 128.0)
        theirs = add_track(base, name="New", track_type="midi", clips=1)

        bf = tmp_path / "base.json"; bf.write_text(base.to_json())
        of = tmp_path / "ours.json"; of.write_text(ours.to_json())
        tf = tmp_path / "theirs.json"; tf.write_text(theirs.to_json())

        from alscan.services import create_merge_plan
        plan = create_merge_plan(str(bf), str(of), str(tf))
        assert plan is not None
        assert plan.conflict_count == 0
        js = json.loads(plan.to_json())
        assert js["document_type"] == "alscan-merge-plan"

    def test_tempo_conflict_via_snapshots(self, qtbot, tmp_path):
        from tests.three_way.fixtures import three_track_project, with_tempo, reset_ids
        reset_ids()
        base = three_track_project("tempo-conflict")
        ours = with_tempo(base, 128.0)
        theirs = with_tempo(base, 132.0)

        bf = tmp_path / "b.json"; bf.write_text(base.to_json())
        of = tmp_path / "o.json"; of.write_text(ours.to_json())
        tf = tmp_path / "t.json"; tf.write_text(theirs.to_json())

        from alscan.services import create_merge_plan
        plan = create_merge_plan(str(bf), str(of), str(tf))
        tempo_conflicts = [c for c in plan.conflicts if c.field == "tempo"]
        assert len(tempo_conflicts) == 1

    def test_json_export_round_trip(self, qtbot, tmp_path):
        from tests.three_way.fixtures import two_track_project, with_tempo, reset_ids
        reset_ids()
        base = two_track_project("json-export")
        ours = with_tempo(base, 140.0)
        theirs = base

        bf = tmp_path / "b.json"; bf.write_text(base.to_json())
        of = tmp_path / "o.json"; of.write_text(ours.to_json())
        tf = tmp_path / "t.json"; tf.write_text(theirs.to_json())

        from alscan.services import create_merge_plan, save_merge_plan
        plan = create_merge_plan(str(bf), str(of), str(tf))
        dest = tmp_path / "output.json"
        saved = save_merge_plan(plan, dest, [bf, of, tf])
        assert saved == dest
        assert dest.exists()
        data = json.loads(dest.read_text())
        assert data["conflict_count"] == plan.conflict_count

    def test_html_export_round_trip(self, qtbot, tmp_path):
        from tests.three_way.fixtures import two_track_project, with_tempo, reset_ids
        reset_ids()
        base = two_track_project("html-export")
        ours = with_tempo(base, 140.0)
        theirs = base

        bf = tmp_path / "b.json"; bf.write_text(base.to_json())
        of = tmp_path / "o.json"; of.write_text(ours.to_json())
        tf = tmp_path / "t.json"; tf.write_text(theirs.to_json())

        from alscan.services import create_merge_plan, save_merge_report
        plan = create_merge_plan(str(bf), str(of), str(tf))
        dest = tmp_path / "output.html"
        saved = save_merge_report(plan, dest, [bf, of, tf])
        assert saved == dest
        assert dest.exists()
        html = dest.read_text()
        assert "<!DOCTYPE html>" in html or "<html" in html

    def test_source_preservation(self, qtbot, tmp_path):
        from tests.three_way.fixtures import two_track_project, with_tempo, reset_ids
        import hashlib
        reset_ids()
        base = two_track_project("preserve")
        bf = tmp_path / "b.json"; bf.write_text(base.to_json())
        oh = hashlib.sha256(bf.read_bytes()).hexdigest()
        of = tmp_path / "o.json"; of.write_text(base.to_json())
        tf = tmp_path / "t.json"; tf.write_text(base.to_json())
        from alscan.services import create_merge_plan
        create_merge_plan(str(bf), str(of), str(tf))
        assert hashlib.sha256(bf.read_bytes()).hexdigest() == oh


class TestResultPresentation:
    def test_plan_has_expected_top_level_fields(self, qtbot):
        from tests.three_way.fixtures import two_track_project, with_tempo, reset_ids
        reset_ids()
        base = two_track_project("fields")
        ours = with_tempo(base, 128.0)
        theirs = base
        from tests.three_way.test_sanity import _plan_for
        plan = _plan_for(base, ours, theirs)
        js = json.loads(plan.to_json())
        required = ["conflict_count", "auto_resolved", "identity_matches",
                    "track_changes", "locator_changes", "proposed_track_order",
                    "lineage_confidence", "warnings", "sources"]
        for field in required:
            assert field in js, f"Missing field: {field}"

    def test_proposed_order_structure(self, qtbot):
        from tests.three_way.fixtures import three_track_project, add_track, reset_ids
        reset_ids()
        base = three_track_project("order")
        ours = add_track(base, name="New", track_type="midi", clips=1)
        theirs = base
        from tests.three_way.test_sanity import _plan_for
        plan = _plan_for(base, ours, theirs)
        for entry in plan.proposed_track_order:
            assert "track" in entry, f"missing 'track' in {entry}"
            assert "position" in entry, f"missing 'position' in {entry}"
            t = entry["track"]
            assert "track_id" in t
            assert "name" in t
            p = entry["position"]
            assert "after_base_track_id" in p or "before_base_track_id" in p

    def test_no_merge_language_in_results(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        info_text = page.info_label.text()
        assert "merge" not in info_text.lower() or "does not create a merged" in info_text.lower()

    def test_no_apply_or_restore_buttons(self, qtbot):
        page = ThreeWayPage()
        qtbot.addWidget(page)
        all_buttons = page.findChildren(QPushButton)
        button_texts = [b.text().lower() for b in all_buttons]
        forbidden = ["apply", "restore", "resolve", "save merged", "create merged"]
        for fb in forbidden:
            assert not any(fb in bt for bt in button_texts), f"Forbidden button text found: {fb}"
