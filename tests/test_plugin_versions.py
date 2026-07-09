# SPDX-License-Identifier: GPL-3.0-only
"""Tests for plugin version tracking."""

from pathlib import Path

import pytest

from alscan.models import Device, PluginRef, Project, Track, Clip
from alscan.parser import parse_xml_string
from alscan.versioner import (
    build_snapshot,
    diff_snapshots,
    _detect_version_changes,
    _device_signature,
)
from alscan.services import scan_project

FIXTURES = Path(__file__).parent / "fixtures"


def _plugin_ref_vst3(name="Serum", version="1.351"):
    return PluginRef(name=name, plugin_type="vst3", version=version, unique_id="1234")


def _plugin_ref_vst2(name="Massive"):
    return PluginRef(name=name, plugin_type="vst2", path="/tmp/Massive.dll", unique_id="5678")


# ---------------------------------------------------------------------------
# PluginRef version field
# ---------------------------------------------------------------------------

class TestPluginRefVersion:
    def test_default_version_empty(self):
        ref = PluginRef(name="Test", plugin_type="vst2")
        assert ref.version == ""

    def test_version_stored(self):
        ref = PluginRef(name="Serum", plugin_type="vst3", version="1.351")
        assert ref.version == "1.351"


# ---------------------------------------------------------------------------
# VST3 PluginVersion extraction from XML
# ---------------------------------------------------------------------------

class TestVst3VersionExtraction:
    def test_plugin_version_extracted(self):
        xml = """<?xml version="1.0"?>
        <Ableton MajorVersion="5" MinorVersion="12.1.0" Creator="test">
        <LiveSet>
        <Tempo><Manual Value="120"/></Tempo>
        <Tracks>
        <MidiTrack Id="1">
        <Name Value="Synth"/>
        <DeviceChain>
        <Devices>
        <PluginDevice>
        <PluginDesc>
        <Vst3PluginInfo>
        <Name Value="Serum"/>
        <PluginId Value="1234"/>
        <PluginVersion Value="1.351"/>
        </Vst3PluginInfo>
        </PluginDesc>
        </PluginDevice>
        </Devices>
        </DeviceChain>
        </MidiTrack>
        </Tracks>
        </LiveSet>
        </Ableton>"""
        proj = parse_xml_string(xml)
        assert len(proj.tracks) == 1
        assert len(proj.tracks[0].devices) == 1
        device = proj.tracks[0].devices[0]
        assert device.plugin_ref is not None
        assert device.plugin_ref.version == "1.351"
        assert device.plugin_ref.plugin_type == "vst3"

    def test_plugin_version_missing(self):
        xml = """<?xml version="1.0"?>
        <Ableton MajorVersion="5" MinorVersion="12.1.0" Creator="test">
        <LiveSet>
        <Tempo><Manual Value="120"/></Tempo>
        <Tracks>
        <MidiTrack Id="1">
        <Name Value="Synth"/>
        <DeviceChain>
        <Devices>
        <PluginDevice>
        <PluginDesc>
        <Vst3PluginInfo>
        <Name Value="Serum"/>
        <PluginId Value="1234"/>
        </Vst3PluginInfo>
        </PluginDesc>
        </PluginDevice>
        </Devices>
        </DeviceChain>
        </MidiTrack>
        </Tracks>
        </LiveSet>
        </Ableton>"""
        proj = parse_xml_string(xml)
        ref = proj.tracks[0].devices[0].plugin_ref
        assert ref is not None
        assert ref.version == ""

    def test_vst2_has_no_version(self):
        xml = """<?xml version="1.0"?>
        <Ableton MajorVersion="5" MinorVersion="12.1.0" Creator="test">
        <LiveSet>
        <Tempo><Manual Value="120"/></Tempo>
        <Tracks>
        <MidiTrack Id="1">
        <Name Value="Synth"/>
        <DeviceChain>
        <Devices>
        <PluginDevice>
        <PluginDesc>
        <VstPluginInfo>
        <Name Value="Massive"/>
        <Path Value="C:/VST/Massive.dll"/>
        <UniqueId Value="5678"/>
        </VstPluginInfo>
        </PluginDesc>
        </PluginDevice>
        </Devices>
        </DeviceChain>
        </MidiTrack>
        </Tracks>
        </LiveSet>
        </Ableton>"""
        proj = parse_xml_string(xml)
        ref = proj.tracks[0].devices[0].plugin_ref
        assert ref is not None
        assert ref.version == ""
        assert ref.plugin_type == "vst2"


# ---------------------------------------------------------------------------
# Snapshot includes version
# ---------------------------------------------------------------------------

class TestSnapshotVersion:
    def test_version_in_snapshot_device(self):
        track = Track(
            name="Synth", track_id=1, track_type="midi",
            devices=[Device(name="Serum", device_type="Vst3PluginInfo",
                           plugin_ref=_plugin_ref_vst3("Serum", "1.351"))],
        )
        proj = Project(path=Path("."), creator="test", tracks=[track],
                       file_path=Path("test.als"))
        snap = build_snapshot(proj)
        dev = snap.tracks[0]["devices"][0]
        assert dev["plugin_version"] == "1.351"
        assert dev["plugin_name"] == "Serum"

    def test_version_none_when_empty(self):
        track = Track(
            name="Synth", track_id=1, track_type="midi",
            devices=[Device(name="Massive", device_type="VstPluginInfo",
                           plugin_ref=_plugin_ref_vst2("Massive"))],
        )
        proj = Project(path=Path("."), creator="test", tracks=[track],
                       file_path=Path("test.als"))
        snap = build_snapshot(proj)
        dev = snap.tracks[0]["devices"][0]
        assert dev["plugin_version"] is None

    def test_version_none_for_builtin_device(self):
        track = Track(
            name="Synth", track_id=1, track_type="midi",
            devices=[Device(name="Eq8", device_type="Eq8")],
        )
        proj = Project(path=Path("."), creator="test", tracks=[track],
                       file_path=Path("test.als"))
        snap = build_snapshot(proj)
        dev = snap.tracks[0]["devices"][0]
        assert dev["plugin_version"] is None
        assert dev["plugin_name"] is None


# ---------------------------------------------------------------------------
# Version change detection in diffs
# ---------------------------------------------------------------------------

class TestVersionChangeDetection:
    def test_detect_version_change(self):
        old = [{"name": "Serum", "device_type": "Vst3PluginInfo",
                "plugin_name": "Serum", "plugin_type": "vst3",
                "plugin_version": "1.35b"}]
        new = [{"name": "Serum", "device_type": "Vst3PluginInfo",
                "plugin_name": "Serum", "plugin_type": "vst3",
                "plugin_version": "1.351"}]
        changes = _detect_version_changes(old, new)
        assert len(changes) == 1
        assert changes[0]["device_name"] == "Serum"
        assert changes[0]["old_version"] == "1.35b"
        assert changes[0]["new_version"] == "1.351"

    def test_same_version_no_change(self):
        old = [{"name": "Serum", "device_type": "Vst3PluginInfo",
                "plugin_name": "Serum", "plugin_type": "vst3",
                "plugin_version": "1.351"}]
        new = [{"name": "Serum", "device_type": "Vst3PluginInfo",
                "plugin_name": "Serum", "plugin_type": "vst3",
                "plugin_version": "1.351"}]
        changes = _detect_version_changes(old, new)
        assert len(changes) == 0

    def test_no_version_in_either(self):
        old = [{"name": "Serum", "device_type": "Vst3PluginInfo",
                "plugin_name": "Serum", "plugin_type": "vst3"}]
        new = [{"name": "Serum", "device_type": "Vst3PluginInfo",
                "plugin_name": "Serum", "plugin_type": "vst3"}]
        changes = _detect_version_changes(old, new)
        assert len(changes) == 0

    def test_version_becomes_known(self):
        old = [{"name": "Serum", "device_type": "Vst3PluginInfo",
                "plugin_name": "Serum", "plugin_type": "vst3",
                "plugin_version": None}]
        new = [{"name": "Serum", "device_type": "Vst3PluginInfo",
                "plugin_name": "Serum", "plugin_type": "vst3",
                "plugin_version": "1.351"}]
        changes = _detect_version_changes(old, new)
        assert len(changes) == 0  # going from unknown to known isn't a "change"

    def test_version_becomes_unknown(self):
        old = [{"name": "Serum", "device_type": "Vst3PluginInfo",
                "plugin_name": "Serum", "plugin_type": "vst3",
                "plugin_version": "1.351"}]
        new = [{"name": "Serum", "device_type": "Vst3PluginInfo",
                "plugin_name": "Serum", "plugin_type": "vst3",
                "plugin_version": None}]
        changes = _detect_version_changes(old, new)
        assert len(changes) == 0

    def test_full_diff_includes_version_change(self):
        from alscan.versioner import Snapshot
        snap_a = Snapshot(
            format_version="1", structural_fingerprint="a", project_name="test",
            timestamp=1.0, creator="t", major_version="12", minor_version="0",
            tempo=120.0, time_signature=[4, 4], tracks=[
                {"track_id": 1, "name": "Synth", "track_type": "midi",
                 "is_frozen": False, "color_index": 0, "group_id": -1,
                 "volume": 1.0, "device_count": 1, "clip_count": 0,
                 "devices": [
                     {"name": "Serum", "device_type": "Vst3PluginInfo",
                      "is_frozen": False, "plugin_name": "Serum",
                      "plugin_type": "vst3", "plugin_version": "1.35b"},
                 ], "samples": []},
            ], locators=[],
        )
        snap_b = Snapshot(
            format_version="1", structural_fingerprint="b", project_name="test",
            timestamp=2.0, creator="t", major_version="12", minor_version="0",
            tempo=120.0, time_signature=[4, 4], tracks=[
                {"track_id": 1, "name": "Synth", "track_type": "midi",
                 "is_frozen": False, "color_index": 0, "group_id": -1,
                 "volume": 1.0, "device_count": 1, "clip_count": 0,
                 "devices": [
                     {"name": "Serum", "device_type": "Vst3PluginInfo",
                      "is_frozen": False, "plugin_name": "Serum",
                      "plugin_type": "vst3", "plugin_version": "1.351"},
                 ], "samples": []},
            ], locators=[],
        )
        result = diff_snapshots(snap_a, snap_b)
        assert len(result.device_changes) == 1
        assert len(result.device_changes[0].version_changes) == 1
        vc = result.device_changes[0].version_changes[0]
        assert vc["device_name"] == "Serum"
        assert vc["old_version"] == "1.35b"
        assert vc["new_version"] == "1.351"

    def test_multiple_devices_version_change(self):
        old = [
            {"name": "A", "device_type": "Vst3PluginInfo",
             "plugin_name": "A", "plugin_type": "vst3", "plugin_version": "1.0"},
            {"name": "B", "device_type": "Vst3PluginInfo",
             "plugin_name": "B", "plugin_type": "vst3", "plugin_version": "2.0"},
        ]
        new = [
            {"name": "A", "device_type": "Vst3PluginInfo",
             "plugin_name": "A", "plugin_type": "vst3", "plugin_version": "1.1"},
            {"name": "B", "device_type": "Vst3PluginInfo",
             "plugin_name": "B", "plugin_type": "vst3", "plugin_version": "2.0"},
        ]
        changes = _detect_version_changes(old, new)
        assert len(changes) == 1
        assert changes[0]["device_name"] == "A"


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_old_plugin_ref_no_version(self):
        ref = PluginRef(name="Test", plugin_type="vst2", path="/tmp/test.dll", unique_id="123")
        assert ref.version == ""

    def test_snapshot_fingerprint_includes_version(self):
        track1 = Track(
            name="Synth", track_id=1, track_type="midi",
            devices=[Device(name="Serum", device_type="Vst3PluginInfo",
                           plugin_ref=_plugin_ref_vst3("Serum", "1.0"))],
        )
        track2 = Track(
            name="Synth", track_id=1, track_type="midi",
            devices=[Device(name="Serum", device_type="Vst3PluginInfo",
                           plugin_ref=_plugin_ref_vst3("Serum", "2.0"))],
        )
        proj1 = Project(path=Path("."), creator="test", tracks=[track1],
                        file_path=Path("test.als"))
        proj2 = Project(path=Path("."), creator="test", tracks=[track2],
                        file_path=Path("test.als"))
        snap1 = build_snapshot(proj1)
        snap2 = build_snapshot(proj2)
        assert snap1.structural_fingerprint != snap2.structural_fingerprint

    def test_device_signature_excludes_version(self):
        sig1 = _device_signature({"name": "Serum", "device_type": "Vst3PluginInfo",
                                   "plugin_name": "Serum", "plugin_type": "vst3",
                                   "plugin_version": "1.0"})
        sig2 = _device_signature({"name": "Serum", "device_type": "Vst3PluginInfo",
                                   "plugin_name": "Serum", "plugin_type": "vst3",
                                   "plugin_version": "2.0"})
        assert sig1 == sig2  # version not in signature — signatures still match


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCliVersionDiff:
    def test_diff_shows_version_change(self, tmp_path):
        from alscan.versioner import Snapshot
        import json
        from alscan.versioner import save_snapshot as _snap_save
        from click.testing import CliRunner
        from alscan.cli import cli

        probe_dir = tmp_path / "probe"
        probe_dir.mkdir()
        als = probe_dir / "test.als"
        als.write_bytes(b'\x1f\x8b\x08')

        snap_dir = probe_dir / ".alscan" / "snapshots"
        snap_dir.mkdir(parents=True)

        snap_a = Snapshot(
            format_version="1", structural_fingerprint="a", project_name="test",
            timestamp=1.0, creator="t", major_version="12", minor_version="0",
            tempo=120.0, time_signature=[4, 4], tracks=[
                {"track_id": 1, "name": "Synth", "track_type": "midi",
                 "is_frozen": False, "color_index": 0, "group_id": -1,
                 "volume": 1.0, "device_count": 1, "clip_count": 0,
                 "devices": [
                     {"name": "Serum", "device_type": "Vst3PluginInfo",
                      "is_frozen": False, "plugin_name": "Serum",
                      "plugin_type": "vst3", "plugin_version": "1.0"},
                 ], "samples": []},
            ], locators=[],
        )
        snap_b = Snapshot(
            format_version="1", structural_fingerprint="b", project_name="test",
            timestamp=2.0, creator="t", major_version="12", minor_version="0",
            tempo=120.0, time_signature=[4, 4], tracks=[
                {"track_id": 1, "name": "Synth", "track_type": "midi",
                 "is_frozen": False, "color_index": 0, "group_id": -1,
                 "volume": 1.0, "device_count": 1, "clip_count": 0,
                 "devices": [
                     {"name": "Serum", "device_type": "Vst3PluginInfo",
                      "is_frozen": False, "plugin_name": "Serum",
                      "plugin_type": "vst3", "plugin_version": "2.0"},
                 ], "samples": []},
            ], locators=[],
        )
        p1 = snap_dir / "snap_a.json"
        p1.write_text(snap_a.to_json())
        p2 = snap_dir / "snap_b.json"
        p2.write_text(snap_b.to_json())

        result = CliRunner().invoke(cli, [
            "diff", str(p1), str(p2),
        ])
        assert result.exit_code == 0
        assert "1.0 -> 2.0" in result.output
        assert "Serum" in result.output
