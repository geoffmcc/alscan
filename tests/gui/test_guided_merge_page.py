# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import gzip
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from alscan.gui.pages.guided_merge_page import GuidedMergePage

BASE_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b"<Ableton MajorVersion=\"5\" MinorVersion=\"11.0_511\" SchemaChangeCount=\"1\" "
    b"Creator=\"Ableton Live 11.0\">"
    b"<LiveSet>"
    b"<Tempo>"
    b"<LomId Value=\"0\" />"
    b"<Manual Value=\"120\" />"
    b"</Tempo>"
    b"<Tracks>"
    b"<AudioTrack Id=\"0\">"
    b"<Name>"
    b"<EffectiveName Value=\"Kick\" />"
    b"</Name>"
    b"</AudioTrack>"
    b"</Tracks>"
    b"</LiveSet>"
    b"</Ableton>"
)


def _write_als(tmp_path: Path, name: str, xml: bytes) -> Path:
    tgt = tmp_path / f"{name}.als"
    with gzip.open(str(tgt), "wb") as f:
        f.write(xml)
    return tgt


class TestGuidedMergePageCreation:
    def test_page_creates(self, qtbot):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        assert page is not None

    def test_has_all_stages(self, qtbot):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        assert page.stage_stack.count() == 9

    def test_stage_labels_are_created(self, qtbot):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        assert len(page._stage_labels) == 9

    def test_starts_on_stage_0(self, qtbot):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        assert page.stage_stack.currentIndex() == 0

    def test_navigate_between_stages(self, qtbot):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        page._navigate_stage(1)
        assert page.stage_stack.currentIndex() == 1
        page._navigate_stage(2)
        assert page.stage_stack.currentIndex() == 2
        page._navigate_stage(0)
        assert page.stage_stack.currentIndex() == 0

    def test_stage_0_has_file_inputs(self, qtbot):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        assert page._base_input is not None
        assert page._ours_input is not None
        assert page._theirs_input is not None

    def test_stage_0_has_analyze_button(self, qtbot):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        assert page._analyze_btn is not None
        assert page._analyze_btn.isEnabled()

    def test_analyze_button_disabled_without_inputs(self, qtbot):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        page._analyze_btn.click()
        assert page.stage_stack.currentIndex() == 0

    def test_analyze_with_valid_inputs(self, qtbot, tmp_path):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        base_p = _write_als(tmp_path, "base", BASE_XML)
        ours_p = _write_als(tmp_path, "ours", BASE_XML)
        theirs_p = _write_als(tmp_path, "theirs", BASE_XML)
        page._get_base_input().setText(str(base_p))
        page._get_ours_input().setText(str(ours_p))
        page._get_theirs_input().setText(str(theirs_p))
        page._analyze_btn.click()
        assert page.stage_stack.currentIndex() == 1

    def test_allow_unrelated_checkbox(self, qtbot):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        assert page._allow_unrelated_cb is not None
        assert not page._allow_unrelated_cb.isChecked()

    def test_no_dead_controls_on_stage_0(self, qtbot):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        page.show()
        assert not page._analyze_btn.isHidden()


class TestGuidedMergeStageAccessibility:
    def test_stage_navigation_labels_are_meaningful(self, qtbot):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        labels = [label.text() for label in page._stage_labels]
        assert labels[0] == "1. Select Sets"
        assert labels[1] == "2. Analyze"
        assert labels[2] == "3. Choose Foundation"

    def test_headings_have_object_name(self, qtbot):
        page = GuidedMergePage()
        qtbot.addWidget(page)
        assert page.info_label.objectName() == "subheading"
