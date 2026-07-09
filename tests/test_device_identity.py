# SPDX-License-Identifier: GPL-3.0-only
"""Tests for per-device identity matching in three-way analysis."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from alscan.merge.analysis import build_merge_plan, _device_id_sig, _device_type_sig
from alscan.merge.inputs import ThreeWayInput
from alscan.merge.plan import MergePlan
from alscan.versioner import Snapshot


def _snap(name="test", tracks=None, **kwargs):
    return Snapshot(
        format_version="1",
        structural_fingerprint=name,
        project_name=name,
        timestamp=1.0,
        creator="t",
        major_version="12",
        minor_version="0",
        tempo=120.0,
        time_signature=[4, 4],
        tracks=tracks or [],
        locators=[],
    )


def _plan_for(base, ours, theirs, **kwargs):
    lineage = SimpleNamespace(
        level=kwargs.get("lineage_level", "strong"),
        warnings=[],
    )
    inputs = ThreeWayInput(
        mode="snapshot",
        base_snapshot=base,
        ours_snapshot=ours,
        theirs_snapshot=theirs,
        lineage=lineage,
        base_identity=SimpleNamespace(sha256="sha-base", size=100, path=Path("base.json")),
        ours_identity=SimpleNamespace(sha256="sha-ours", size=100, path=Path("ours.json")),
        theirs_identity=SimpleNamespace(sha256="sha-theirs", size=100, path=Path("theirs.json")),
    )
    return build_merge_plan(inputs)


def _make_device(name, device_type="Eq8", plugin_name=None, plugin_type=None,
                 plugin_version=None, params=None, is_frozen=False):
    d = {"name": name, "device_type": device_type, "is_frozen": is_frozen,
         "plugin_name": plugin_name, "plugin_type": plugin_type,
         "plugin_version": plugin_version, "params": params or {}}
    return d


def _track_devices(track_id=1, name="Track", devices=None, **kwargs):
    return {"track_id": track_id, "name": name, "track_type": kwargs.get("track_type", "midi"),
            "is_frozen": False, "color_index": 0, "group_id": -1, "volume": 1.0,
            "device_count": len(devices or []), "clip_count": 0,
            "devices": devices or [], "samples": []}


# ---------------------------------------------------------------------------
# Device identity signatures
# ---------------------------------------------------------------------------

class TestDeviceSignatures:
    def test_full_sig_match(self):
        d1 = _make_device("Eq8", "Eq8")
        d2 = _make_device("Eq8", "Eq8")
        assert _device_id_sig(d1) == _device_id_sig(d2)

    def test_full_sig_diff_name(self):
        d1 = _make_device("Eq8", "Eq8")
        d2 = _make_device("EQ Eight", "Eq8")
        assert _device_id_sig(d1) != _device_id_sig(d2)

    def test_type_sig_match(self):
        d1 = _make_device("Eq8", "Eq8")
        d2 = _make_device("EQ8", "Eq8")
        assert _device_type_sig(d1) == _device_type_sig(d2)

    def test_type_sig_diff_type(self):
        d1 = _make_device("Eq8", "Eq8")
        d2 = _make_device("Comp", "Compressor2")
        assert _device_type_sig(d1) != _device_type_sig(d2)

    def test_type_sig_match_with_plugin(self):
        d1 = _make_device("Serum", "plugin", plugin_name="Serum", plugin_type="vst3")
        d2 = _make_device("Serum v2", "plugin", plugin_name="Serum", plugin_type="vst3")
        assert _device_type_sig(d1) == _device_type_sig(d2)


# ---------------------------------------------------------------------------
# Per-device identity: identical devices
# ---------------------------------------------------------------------------

class TestDeviceIdentityIdentical:
    def test_identical_devices_no_conflict(self):
        base = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        ours = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        theirs = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        plan = _plan_for(base, ours, theirs)
        assert not plan.conflicts
        assert not any("device" in ar.field for ar in plan.auto_resolved)

    def test_ours_adds_device(self):
        base = _snap(tracks=[_track_devices(devices=[])])
        ours = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        theirs = _snap(tracks=[_track_devices(devices=[])])
        plan = _plan_for(base, ours, theirs)
        assert any(ar.field == "track.devices" for ar in plan.auto_resolved)

    def test_theirs_adds_device(self):
        base = _snap(tracks=[_track_devices(devices=[])])
        ours = _snap(tracks=[_track_devices(devices=[])])
        theirs = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        plan = _plan_for(base, ours, theirs)
        assert any(ar.field == "track.devices" for ar in plan.auto_resolved)

    def test_ours_removes_device(self):
        base = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        ours = _snap(tracks=[_track_devices(devices=[])])
        theirs = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        plan = _plan_for(base, ours, theirs)
        assert any(ar.field == "track.devices" for ar in plan.auto_resolved)

    def test_both_add_same_device(self):
        base = _snap(tracks=[_track_devices(devices=[])])
        ours = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        theirs = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        plan = _plan_for(base, ours, theirs)
        assert not plan.conflicts

    def test_both_add_different_devices(self):
        base = _snap(tracks=[_track_devices(devices=[])])
        ours = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        theirs = _snap(tracks=[_track_devices(devices=[_make_device("Compressor2", "Compressor2")])])
        plan = _plan_for(base, ours, theirs)
        assert any(c.field == "track.devices" for c in plan.conflicts)

    def test_both_remove_same_device_conflict(self):
        base = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        ours = _snap(tracks=[_track_devices(devices=[])])
        theirs = _snap(tracks=[_track_devices(devices=[])])
        plan = _plan_for(base, ours, theirs)
        assert not plan.conflicts

    def test_ours_removes_theirs_changes(self):
        base = _snap(tracks=[_track_devices(devices=[_make_device("Eq8", params={"device_on": True})])])
        ours = _snap(tracks=[_track_devices(devices=[])])
        theirs = _snap(tracks=[_track_devices(devices=[_make_device("Compressor2", "Compressor2")])])
        plan = _plan_for(base, ours, theirs)
        assert any(c.field == "track.devices" for c in plan.conflicts)

    def test_rename_device_plausible_match(self):
        base = _snap(tracks=[_track_devices(devices=[_make_device("EQ 8", "Eq8")])])
        ours = _snap(tracks=[_track_devices(devices=[_make_device("EQ Eight", "Eq8")])])
        theirs = _snap(tracks=[_track_devices(devices=[_make_device("EQ 8", "Eq8")])])
        plan = _plan_for(base, ours, theirs)
        assert not plan.conflicts


# ---------------------------------------------------------------------------
# Multiple devices
# ---------------------------------------------------------------------------

class TestMultipleDevices:
    def test_reorder_devices_no_conflict(self):
        base = _snap(tracks=[_track_devices(devices=[
            _make_device("Eq8"), _make_device("Compressor2", "Compressor2"),
        ])])
        ours = _snap(tracks=[_track_devices(devices=[
            _make_device("Compressor2", "Compressor2"), _make_device("Eq8"),
        ])])
        theirs = _snap(tracks=[_track_devices(devices=[
            _make_device("Eq8"), _make_device("Compressor2", "Compressor2"),
        ])])
        plan = _plan_for(base, ours, theirs)
        assert not plan.conflicts

    def test_duplicate_devices_ambiguous(self):
        base = _snap(tracks=[_track_devices(devices=[
            _make_device("Eq8"), _make_device("Eq8"),
        ])])
        ours = _snap(tracks=[_track_devices(devices=[
            _make_device("Eq8"), _make_device("Eq8"),
        ])])
        theirs = _snap(tracks=[_track_devices(devices=[
            _make_device("Eq8"), _make_device("Eq8"),
        ])])
        plan = _plan_for(base, ours, theirs)
        assert not plan.conflicts

    def test_one_side_adds_other_unchanged(self):
        base = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        ours = _snap(tracks=[_track_devices(devices=[
            _make_device("Eq8"), _make_device("Compressor2", "Compressor2"),
        ])])
        theirs = _snap(tracks=[_track_devices(devices=[_make_device("Eq8")])])
        plan = _plan_for(base, ours, theirs)
        assert not plan.conflicts
        assert any(ar.field == "track.devices" for ar in plan.auto_resolved)


# ---------------------------------------------------------------------------
# Plugin device identity
# ---------------------------------------------------------------------------

class TestPluginDeviceIdentity:
    def test_identical_plugins(self):
        base = _snap(tracks=[_track_devices(devices=[
            _make_device("Serum", "plugin", plugin_name="Serum", plugin_type="vst3"),
        ])])
        ours = _snap(tracks=[_track_devices(devices=[
            _make_device("Serum", "plugin", plugin_name="Serum", plugin_type="vst3"),
        ])])
        theirs = _snap(tracks=[_track_devices(devices=[
            _make_device("Serum", "plugin", plugin_name="Serum", plugin_type="vst3"),
        ])])
        plan = _plan_for(base, ours, theirs)
        assert not plan.conflicts

    def test_different_plugin_same_track(self):
        base = _snap(tracks=[_track_devices(devices=[
            _make_device("Serum", "plugin", plugin_name="Serum", plugin_type="vst3"),
        ])])
        ours = _snap(tracks=[_track_devices(devices=[
            _make_device("Massive", "plugin", plugin_name="Massive", plugin_type="vst3"),
        ])])
        theirs = _snap(tracks=[_track_devices(devices=[
            _make_device("Serum", "plugin", plugin_name="Serum", plugin_type="vst3"),
        ])])
        plan = _plan_for(base, ours, theirs)
        assert not plan.conflicts
