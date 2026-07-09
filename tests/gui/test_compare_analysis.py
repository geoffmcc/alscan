# SPDX-License-Identifier: GPL-3.0-only
"""Tests for compare_analysis module."""

from __future__ import annotations

import pytest

from alscan.gui.compare_analysis import (
    ChangeItem,
    CategorySummary,
    CompareAnalysis,
    _explain_property_change,
    _parse_detail,
    _extract_changes,
    _build_summaries,
    _generate_summary_text,
    _collect_categories,
    analyse,
)
from alscan.versioner import DiffResult, TrackChange, DeviceDiff


class TestExplainPropertyChange:
    def test_clip_count_added(self):
        result = _explain_property_change("clip", "Clip count", "0", "2")
        assert result == "2 clips added"

    def test_clip_count_added_singular(self):
        result = _explain_property_change("clip", "Clip count", "0", "1")
        assert result == "1 clip added"

    def test_clip_count_removed(self):
        result = _explain_property_change("clip", "Clip count", "3", "1")
        assert result == "2 clips removed"

    def test_clip_count_removed_singular(self):
        result = _explain_property_change("clip", "Clip count", "1", "0")
        assert result == "1 clip removed"

    def test_tempo_increased(self):
        result = _explain_property_change("tempo", "Tempo", "120", "128")
        assert "increased by 8" in result
        assert "BPM" in result

    def test_tempo_decreased(self):
        result = _explain_property_change("tempo", "Tempo", "128", "120")
        assert "decreased by 8" in result
        assert "BPM" in result

    def test_device_count_added(self):
        result = _explain_property_change("track", "Device count", "1", "3")
        assert result == "2 devices added"

    def test_renamed(self):
        result = _explain_property_change("track", "Name", "Drums", "Percussion")
        assert result == 'Renamed from "Drums" to "Percussion"'

    def test_frozen(self):
        result = _explain_property_change("track", "Frozen", "False", "True")
        assert result == "Track frozen"

    def test_unfrozen(self):
        result = _explain_property_change("track", "Frozen", "True", "False")
        assert result == "Track unfrozen"

    def test_volume_increased(self):
        result = _explain_property_change("track", "Volume", "0.75", "1.0")
        assert "increased" in result
        assert "0.75" in result
        assert "1.0" in result

    def test_volume_decreased(self):
        result = _explain_property_change("track", "Volume", "1.0", "0.75")
        assert "decreased" in result

    def test_type_change(self):
        result = _explain_property_change("track", "Type", "audio", "midi")
        assert "Type changed" in result

    def test_color_change(self):
        result = _explain_property_change("track", "Color", "0", "3")
        assert "Color index changed" in result

    def test_group_change(self):
        result = _explain_property_change("track", "Group", "-1", "2")
        assert "Group changed" in result

    def test_time_signature(self):
        result = _explain_property_change("time_sig", "Time Signature", "4/4", "3/4")
        assert "Time signature changed" in result

    def test_fallback(self):
        result = _explain_property_change("track", "Unknown", "x", "y")
        assert result == "Changed from x to y"


class TestParseDetail:
    def test_name_change(self):
        prop, val_a, val_b = _parse_detail('name: "Drums" -> "Percussion"')
        assert prop == "Name"
        assert val_a == "Drums"
        assert val_b == "Percussion"

    def test_clip_count(self):
        prop, val_a, val_b = _parse_detail("clips: 0 -> 2")
        assert prop == "Clip count"
        assert val_a == "0"
        assert val_b == "2"

    def test_device_count(self):
        prop, val_a, val_b = _parse_detail("devices: 1 -> 3")
        assert prop == "Device count"
        assert val_a == "1"
        assert val_b == "3"

    def test_volume(self):
        prop, val_a, val_b = _parse_detail("volume: 0.75 -> 1.0")
        assert prop == "Volume"
        assert val_a == "0.75"
        assert val_b == "1.0"

    def test_frozen(self):
        prop, val_a, val_b = _parse_detail("frozen: False -> True")
        assert prop == "Frozen"
        assert val_a == "False"
        assert val_b == "True"

    def test_type(self):
        prop, val_a, val_b = _parse_detail("type: audio -> midi")
        assert prop == "Type"
        assert val_a == "audio"
        assert val_b == "midi"

    def test_color(self):
        prop, val_a, val_b = _parse_detail("color: 0 -> 3")
        assert prop == "Color"
        assert val_a == "0"
        assert val_b == "3"

    def test_group_id(self):
        prop, val_a, val_b = _parse_detail("group_id: -1 -> 2")
        assert prop == "Group"
        assert val_a == "-1"
        assert val_b == "2"

    def test_unknown_key(self):
        prop, val_a, val_b = _parse_detail("custom_field: a -> b")
        assert prop == "Custom Field"
        assert val_a == "a"
        assert val_b == "b"

    def test_invalid_format_returns_none(self):
        assert _parse_detail("no arrow here") is None


class TestExtractChanges:
    def test_empty_diff(self):
        diff = DiffResult(project_a="a", project_b="b")
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert items == []

    def test_tempo_change(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            tempo_changed=True, tempo_before=120.0, tempo_after=128.0,
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert items[0].category == "tempo"
        assert items[0].change_type == "modified"
        assert items[0].value_a == "120.0"
        assert items[0].value_b == "128.0"
        assert "increased" in items[0].explanation.lower()

    def test_time_sig_change(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            time_sig_changed=True,
            ts_before=[4, 4], ts_after=[3, 4],
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert items[0].category == "time_signature"
        assert items[0].value_a == "4/4"
        assert items[0].value_b == "3/4"

    def test_locator_added(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            locators_changed=True,
            added_locators=[{"name": "Intro", "time": 1.0}],
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert items[0].change_type == "added"
        assert items[0].category == "locator"
        assert items[0].object_name == "Intro"
        assert items[0].explanation == "Added in Source B"

    def test_locator_removed(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            locators_changed=True,
            removed_locators=[{"name": "Outro", "time": 64.0}],
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert items[0].change_type == "removed"
        assert items[0].category == "locator"
        assert items[0].object_name == "Outro"
        assert items[0].explanation == "Present only in Source A"

    def test_track_added(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            track_changes=[
                TrackChange(kind="added", track_id=3, name="New Track"),
            ],
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert items[0].change_type == "added"
        assert items[0].category == "track"
        assert items[0].object_name == "New Track"
        assert items[0].explanation == "Added in Source B"

    def test_track_removed(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            track_changes=[
                TrackChange(kind="removed", track_id=1, name="Old Track"),
            ],
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert items[0].change_type == "removed"
        assert items[0].explanation == "Present only in Source A"

    def test_track_modified_clip_count(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            track_changes=[
                TrackChange(
                    kind="modified", track_id=2, name="Drums",
                    details=["clips: 0 -> 2"],
                ),
            ],
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert items[0].change_type == "modified"
        assert items[0].category == "clip"
        assert items[0].object_type == "Track"
        assert items[0].object_name == "Drums"
        assert items[0].property_name == "Clip count"
        assert items[0].value_a == "0"
        assert items[0].value_b == "2"
        assert items[0].explanation == "2 clips added"

    def test_track_renamed(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            track_changes=[
                TrackChange(
                    kind="modified", track_id=1, name="Percussion",
                    details=['name: "Drums" -> "Percussion"'],
                ),
            ],
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert items[0].change_type == "renamed"
        assert items[0].property_name == "Name"
        assert items[0].explanation == 'Renamed from "Drums" to "Percussion"'

    def test_device_added(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            device_changes=[
                DeviceDiff(
                    track_id=1, track_name="Drums",
                    added=[{"name": "Compressor", "device_type": "audio_effect", "plugin_type": "AudioEffect"}],
                ),
            ],
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert items[0].change_type == "added"
        assert items[0].category == "device"
        assert items[0].object_name == "Compressor"
        assert items[0].parent_object == "Drums"
        assert items[0].explanation == "Added in Source B"

    def test_device_removed(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            device_changes=[
                DeviceDiff(
                    track_id=2, track_name="Bass",
                    removed=[{"name": "EQ Eight", "device_type": "audio_effect"}],
                ),
            ],
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert items[0].change_type == "removed"
        assert items[0].object_name == "EQ Eight"
        assert items[0].explanation == "Present only in Source A"

    def test_device_order_changed(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            device_changes=[
                DeviceDiff(
                    track_id=1, track_name="Drums",
                    order_changed=True,
                ),
            ],
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert items[0].change_type == "moved"
        assert items[0].category == "device"
        assert "Device order changed" in items[0].explanation

    def test_tempo_decrease(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            tempo_changed=True, tempo_before=128.0, tempo_after=120.0,
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert "decreased" in items[0].explanation.lower()

    def test_multiple_track_details(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            track_changes=[
                TrackChange(
                    kind="modified", track_id=1, name="Synth",
                    details=["clips: 1 -> 4", "volume: 0.8 -> 1.0", 'name: "Synth" -> "Lead Synth"'],
                ),
            ],
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 3

    def test_one_clip_removed(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            track_changes=[
                TrackChange(
                    kind="modified", track_id=1, name="Vocals",
                    details=["clips: 1 -> 0"],
                ),
            ],
        )
        items = _extract_changes(diff, "/a.als", "/b.als")
        assert len(items) == 1
        assert items[0].explanation == "1 clip removed"


class TestSummaryAggregation:
    def test_build_summaries_empty(self):
        summaries = _build_summaries([])
        assert summaries == []

    def test_build_summaries_tracks(self):
        items = [
            ChangeItem("added", "track", "Track", "A", "", "", "", "Added", ""),
            ChangeItem("removed", "track", "Track", "B", "", "", "", "Removed", ""),
            ChangeItem("modified", "track", "Track", "C", "Volume", "0.75", "1.0", "Changed", ""),
            ChangeItem("renamed", "track", "Track", "D", "Name", "X", "Y", "Renamed", ""),
        ]
        summaries = _build_summaries(items)
        track_summary = next(s for s in summaries if s.category == "track")
        assert track_summary.added == 1
        assert track_summary.removed == 1
        assert track_summary.modified == 1
        assert track_summary.renamed == 1
        assert track_summary.total == 4

    def test_build_summaries_clips(self):
        items = [
            ChangeItem("added", "clip", "Track", "A", "", "", "", "Added", ""),
        ]
        summaries = _build_summaries(items)
        clip_summary = next(s for s in summaries if s.category == "clip")
        assert clip_summary.total == 1

    def test_build_summaries_devices(self):
        items = [
            ChangeItem("added", "device", "Device", "EQ", "", "", "", "Added", "Track1"),
            ChangeItem("removed", "device", "Device", "Comp", "", "", "", "Removed", "Track1"),
            ChangeItem("moved", "device", "Device", "Devices", "Order", "", "", "Moved", "Track1"),
        ]
        summaries = _build_summaries(items)
        dev_summary = next(s for s in summaries if s.category == "device")
        assert dev_summary.added == 1
        assert dev_summary.removed == 1
        assert dev_summary.moved == 1

    def test_generate_summary_text_multiple(self):
        items = [
            ChangeItem("modified", "track", "Track", "A", "Volume", "0.75", "1.0", "Changed", ""),
            ChangeItem("added", "clip", "Track", "A", "Clip count", "0", "2", "2 clips added", ""),
            ChangeItem("removed", "device", "Device", "EQ", "", "", "", "Removed", "A"),
        ]
        summaries = _build_summaries(items)
        text = "\n".join(_generate_summary_text(items, summaries))
        assert "track" in text.lower() or "changed" in text
        assert "2 clips added" not in text

    def test_generate_summary_text_no_changes(self):
        text = "\n".join(_generate_summary_text([], []))
        assert "No differences" in text

    def test_category_summary_total(self):
        cs = CategorySummary(category="track", label="Tracks", added=2, removed=1, modified=3)
        assert cs.total == 6


class TestAnalyseIntegration:
    def test_analyse_empty(self):
        diff = DiffResult(project_a="a", project_b="b")
        result = analyse(diff, "/a.als", "/b.als")
        assert result.project_a == "a"
        assert result.project_b == "b"
        assert result.items == []
        assert result.total_changes == 0
        assert result.has_changes is False
        assert not result.is_small

    def test_analyse_with_changes(self):
        diff = DiffResult(
            project_a="ProjA", project_b="ProjB",
            tempo_changed=True, tempo_before=120.0, tempo_after=128.0,
            track_changes=[
                TrackChange(kind="added", track_id=1, name="New Track"),
                TrackChange(kind="modified", track_id=2, name="Drums",
                            details=["clips: 0 -> 2"]),
            ],
        )
        result = analyse(diff, "/a.als", "/b.als")
        assert result.total_changes == 3
        assert result.has_changes is True
        assert result.is_small  # 3 <= 10

    def test_analyse_large_but_not_small(self):
        items = []
        for i in range(15):
            items.append(TrackChange(kind="added", track_id=i + 10, name=f"Track {i}"))
        diff = DiffResult(project_a="a", project_b="b", track_changes=items)
        result = analyse(diff, "/a.als", "/b.als")
        assert result.total_changes == 15
        assert not result.is_small

    def test_analyse_is_small_threshold(self):
        diff = DiffResult(
            project_a="a", project_b="b",
            track_changes=[
                TrackChange(kind="added", track_id=i + 1, name=f"T{i}")
                for i in range(10)
            ],
        )
        result = analyse(diff, "/a.als", "/b.als")
        assert result.is_small


class TestCollectCategories:
    def test_empty(self):
        assert _collect_categories([]) == []

    def test_multiple_categories(self):
        items = [
            ChangeItem("modified", "track", "Track", "A", "", "", "", "", ""),
            ChangeItem("added", "clip", "Track", "A", "", "", "", "", ""),
            ChangeItem("modified", "tempo", "Tempo", "", "Tempo", "120", "128", "", ""),
        ]
        cats = _collect_categories(items)
        assert "clip" in cats
        assert "tempo" in cats
        assert "track" in cats
        assert cats == sorted(cats)
