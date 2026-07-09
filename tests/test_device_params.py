# SPDX-License-Identifier: GPL-3.0-only
"""Tests for device parameter extraction and comparison."""

from pathlib import Path

import pytest

from alscan.models import Device
from alscan.parser import parse_xml_string, _extract_device_params
from alscan.versioner import _detect_param_changes, diff_snapshots, Snapshot


# ---------------------------------------------------------------------------
# Parameter extraction from XML
# ---------------------------------------------------------------------------

class TestExtractDeviceParams:
    def test_device_on_off(self):
        xml = """<Eq8>
        <AutomationTarget Id="0">
            <Target><Name Value="Device On"/></Target>
            <Manual Value="true"/>
        </AutomationTarget>
        </Eq8>"""
        from lxml import etree
        el = etree.fromstring(xml, parser=etree.XMLParser(
            resolve_entities=False, no_network=True, recover=False))
        params = _extract_device_params(el)
        assert params["device_on"] is True

    def test_device_off(self):
        xml = """<Eq8>
        <AutomationTarget Id="0">
            <Target><Name Value="Device On"/></Target>
            <Manual Value="false"/>
        </AutomationTarget>
        </Eq8>"""
        from lxml import etree
        el = etree.fromstring(xml, parser=etree.XMLParser(
            resolve_entities=False, no_network=True, recover=False))
        params = _extract_device_params(el)
        assert params["device_on"] is False

    def test_named_parameter_float(self):
        xml = """<Eq8>
        <AutomationTarget Id="1">
            <Target><UserName Value="Frequency"/></Target>
            <Manual Value="1000.0"/>
        </AutomationTarget>
        </Eq8>"""
        from lxml import etree
        el = etree.fromstring(xml, parser=etree.XMLParser(
            resolve_entities=False, no_network=True, recover=False))
        params = _extract_device_params(el)
        assert params["Frequency"] == 1000.0

    def test_named_parameter_string(self):
        xml = """<Eq8>
        <AutomationTarget Id="1">
            <Target><UserName Value="Mode"/></Target>
            <Manual Value="stereo"/>
        </AutomationTarget>
        </Eq8>"""
        from lxml import etree
        el = etree.fromstring(xml, parser=etree.XMLParser(
            resolve_entities=False, no_network=True, recover=False))
        params = _extract_device_params(el)
        assert params["Mode"] == "stereo"

    def test_no_automation_targets(self):
        xml = "<Eq8></Eq8>"
        from lxml import etree
        el = etree.fromstring(xml, parser=etree.XMLParser(
            resolve_entities=False, no_network=True, recover=False))
        params = _extract_device_params(el)
        assert params == {}


# ---------------------------------------------------------------------------
# Full parse with params
# ---------------------------------------------------------------------------

class TestFullParseParams:
    def test_builtin_device_has_params(self):
        xml = """<?xml version="1.0"?>
        <Ableton MajorVersion="5" MinorVersion="12.1.0" Creator="test">
        <LiveSet>
        <Tempo><Manual Value="120"/></Tempo>
        <Tracks>
        <AudioTrack Id="1">
        <Name Value="Audio"/>
        <DeviceChain>
        <Devices>
        <Eq8>
        <AutomationTarget Id="0">
            <Target><Name Value="Device On"/></Target>
            <Manual Value="true"/>
        </AutomationTarget>
        <AutomationTarget Id="1">
            <Target><UserName Value="Frequency"/></Target>
            <Manual Value="500.0"/>
        </AutomationTarget>
        </Eq8>
        </Devices>
        </DeviceChain>
        </AudioTrack>
        </Tracks>
        </LiveSet>
        </Ableton>"""
        proj = parse_xml_string(xml)
        dev = proj.tracks[0].devices[0]
        assert dev.device_type == "Eq8"
        assert dev.params.get("device_on") is True
        assert dev.params.get("Frequency") == 500.0

    def test_plugin_device_no_params(self):
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
        <PluginId Value="123"/>
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
        dev = proj.tracks[0].devices[0]
        assert dev.params == {}


# ---------------------------------------------------------------------------
# Param change detection in diffs
# ---------------------------------------------------------------------------

class TestDetectParamChanges:
    def test_param_changed(self):
        old = [{"name": "Eq8", "device_type": "Eq8",
                "params": {"device_on": True, "Frequency": 500.0}}]
        new = [{"name": "Eq8", "device_type": "Eq8",
                "params": {"device_on": True, "Frequency": 1000.0}}]
        changes = _detect_param_changes(old, new)
        assert len(changes) == 1
        assert changes[0]["device_name"] == "Eq8"
        assert changes[0]["changes"]["Frequency"]["old"] == 500.0
        assert changes[0]["changes"]["Frequency"]["new"] == 1000.0

    def test_device_on_changed(self):
        old = [{"name": "Eq8", "device_type": "Eq8",
                "params": {"device_on": True}}]
        new = [{"name": "Eq8", "device_type": "Eq8",
                "params": {"device_on": False}}]
        changes = _detect_param_changes(old, new)
        assert len(changes) == 1
        assert changes[0]["changes"]["device_on"]["old"] is True
        assert changes[0]["changes"]["device_on"]["new"] is False

    def test_no_param_change(self):
        old = [{"name": "Eq8", "device_type": "Eq8",
                "params": {"device_on": True}}]
        new = [{"name": "Eq8", "device_type": "Eq8",
                "params": {"device_on": True}}]
        changes = _detect_param_changes(old, new)
        assert len(changes) == 0

    def test_no_params_in_either(self):
        old = [{"name": "Eq8", "device_type": "Eq8"}]
        new = [{"name": "Eq8", "device_type": "Eq8"}]
        changes = _detect_param_changes(old, new)
        assert len(changes) == 0

    def test_param_added(self):
        old = [{"name": "Eq8", "device_type": "Eq8", "params": {}}]
        new = [{"name": "Eq8", "device_type": "Eq8",
                "params": {"Frequency": 500.0}}]
        changes = _detect_param_changes(old, new)
        assert len(changes) == 1
        assert changes[0]["changes"]["Frequency"]["old"] is None
        assert changes[0]["changes"]["Frequency"]["new"] == 500.0

    def test_param_removed(self):
        old = [{"name": "Eq8", "device_type": "Eq8",
                "params": {"Frequency": 500.0}}]
        new = [{"name": "Eq8", "device_type": "Eq8", "params": {}}]
        changes = _detect_param_changes(old, new)
        assert len(changes) == 1
        assert changes[0]["changes"]["Frequency"]["old"] == 500.0
        assert changes[0]["changes"]["Frequency"]["new"] is None

    def test_float_tolerance(self):
        old = [{"name": "Eq8", "device_type": "Eq8",
                "params": {"Frequency": 500.0000001}}]
        new = [{"name": "Eq8", "device_type": "Eq8",
                "params": {"Frequency": 500.0000002}}]
        changes = _detect_param_changes(old, new)
        assert len(changes) == 0

    def test_multiple_devices(self):
        old = [
            {"name": "Eq8", "device_type": "Eq8", "params": {"device_on": True}},
            {"name": "Comp", "device_type": "Compressor2", "params": {"Threshold": -20.0}},
        ]
        new = [
            {"name": "Eq8", "device_type": "Eq8", "params": {"device_on": False}},
            {"name": "Comp", "device_type": "Compressor2", "params": {"Threshold": -20.0}},
        ]
        changes = _detect_param_changes(old, new)
        assert len(changes) == 1
        assert changes[0]["device_name"] == "Eq8"


# ---------------------------------------------------------------------------
# Full diff integration
# ---------------------------------------------------------------------------

class TestDiffParamChanges:
    def test_full_diff_with_params(self):
        snap_a = Snapshot(
            format_version="1", structural_fingerprint="a", project_name="test",
            timestamp=1.0, creator="t", major_version="12", minor_version="0",
            tempo=120.0, time_signature=[4, 4], tracks=[
                {"track_id": 1, "name": "Audio", "track_type": "audio",
                 "is_frozen": False, "color_index": 0, "group_id": -1,
                 "volume": 1.0, "device_count": 1, "clip_count": 0,
                 "devices": [
                     {"name": "Eq8", "device_type": "Eq8", "is_frozen": False,
                      "plugin_name": None, "plugin_type": None, "plugin_version": None,
                      "params": {"device_on": True, "Frequency": 500.0}},
                 ], "samples": []},
            ], locators=[],
        )
        snap_b = Snapshot(
            format_version="1", structural_fingerprint="b", project_name="test",
            timestamp=2.0, creator="t", major_version="12", minor_version="0",
            tempo=120.0, time_signature=[4, 4], tracks=[
                {"track_id": 1, "name": "Audio", "track_type": "audio",
                 "is_frozen": False, "color_index": 0, "group_id": -1,
                 "volume": 1.0, "device_count": 1, "clip_count": 0,
                 "devices": [
                     {"name": "Eq8", "device_type": "Eq8", "is_frozen": False,
                      "plugin_name": None, "plugin_type": None, "plugin_version": None,
                      "params": {"device_on": False, "Frequency": 1000.0}},
                 ], "samples": []},
            ], locators=[],
        )
        result = diff_snapshots(snap_a, snap_b)
        assert len(result.device_changes) == 1
        assert len(result.device_changes[0].param_changes) == 1
        pc = result.device_changes[0].param_changes[0]
        assert pc["device_name"] == "Eq8"
        assert pc["changes"]["device_on"]["old"] is True
        assert pc["changes"]["device_on"]["new"] is False
        assert pc["changes"]["Frequency"]["old"] == 500.0
        assert pc["changes"]["Frequency"]["new"] == 1000.0

    def test_old_snapshots_without_params(self):
        """Snapshots without params field should not crash."""
        snap_a = Snapshot(
            format_version="1", structural_fingerprint="a", project_name="test",
            timestamp=1.0, creator="t", major_version="12", minor_version="0",
            tempo=120.0, time_signature=[4, 4], tracks=[
                {"track_id": 1, "name": "Audio", "track_type": "audio",
                 "is_frozen": False, "color_index": 0, "group_id": -1,
                 "volume": 1.0, "device_count": 1, "clip_count": 0,
                 "devices": [
                     {"name": "Eq8", "device_type": "Eq8", "is_frozen": False},
                 ], "samples": []},
            ], locators=[],
        )
        snap_b = Snapshot(
            format_version="1", structural_fingerprint="b", project_name="test",
            timestamp=2.0, creator="t", major_version="12", minor_version="0",
            tempo=120.0, time_signature=[4, 4], tracks=[
                {"track_id": 1, "name": "Audio", "track_type": "audio",
                 "is_frozen": False, "color_index": 0, "group_id": -1,
                 "volume": 1.0, "device_count": 1, "clip_count": 0,
                 "devices": [
                     {"name": "Eq8", "device_type": "Eq8", "is_frozen": False,
                      "params": {"device_on": True}},
                 ], "samples": []},
            ], locators=[],
        )
        result = diff_snapshots(snap_a, snap_b)
        assert len(result.device_changes) == 1
        assert len(result.device_changes[0].param_changes) == 1


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCliParamDiff:
    def test_diff_shows_param_changes(self, tmp_path):
        import json
        from click.testing import CliRunner
        from alscan.cli import cli

        snap_dir = tmp_path / ".alscan" / "snapshots"
        snap_dir.mkdir(parents=True)

        track = {
            "track_id": 1, "name": "Audio", "track_type": "audio",
            "is_frozen": False, "color_index": 0, "group_id": -1,
            "volume": 1.0, "device_count": 1, "clip_count": 0,
            "devices": [
                {"name": "Eq8", "device_type": "Eq8", "is_frozen": False,
                 "plugin_name": None, "plugin_type": None, "plugin_version": None,
                 "params": {"device_on": True}},
            ], "samples": [],
        }

        snap_a = Snapshot(
            format_version="1", structural_fingerprint="a", project_name="test",
            timestamp=1.0, creator="t", major_version="12", minor_version="0",
            tempo=120.0, time_signature=[4, 4],
            tracks=[track], locators=[],
        )
        track2 = dict(track)
        track2["devices"] = [dict(track["devices"][0])]
        track2["devices"][0]["params"] = {"device_on": False}
        snap_b = Snapshot(
            format_version="1", structural_fingerprint="b", project_name="test",
            timestamp=2.0, creator="t", major_version="12", minor_version="0",
            tempo=120.0, time_signature=[4, 4],
            tracks=[track2], locators=[],
        )

        p1 = snap_dir / "snap_a.json"
        p1.write_text(snap_a.to_json())
        p2 = snap_dir / "snap_b.json"
        p2.write_text(snap_b.to_json())

        result = CliRunner().invoke(cli, ["diff", str(p1), str(p2)])
        assert result.exit_code == 0
        assert "device_on" in result.output
        assert "True" in result.output
        assert "False" in result.output
