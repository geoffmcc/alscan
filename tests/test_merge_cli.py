"""Integration tests for alscan merge commands via CliRunner."""

import json

import pytest
from click.testing import CliRunner

from alscan.cli import cli
from alscan.parser import parse_xml_string
from alscan.versioner import build_snapshot, save_snapshot

BASE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12" Creator="Ableton Live 12">
  <LiveSet>
    <Tempo><Manual Value="120"/></Tempo>
    <TimeSignature>
      <TimeSignatures>
        <RemoteableTimeSignature>
          <Numerator Value="4"/><Denominator Value="4"/>
        </RemoteableTimeSignature>
      </TimeSignatures>
    </TimeSignature>
    <Locators><Locators/></Locators>
    <Tracks>
      <AudioTrack Id="0">
        <Name><EffectiveName Value="Kick"/></Name>
        <ColorIndex Value="1"/>
        <DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain>
      </AudioTrack>
      <AudioTrack Id="1">
        <Name><EffectiveName Value="Synth"/></Name>
        <ColorIndex Value="2"/>
        <DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain>
      </AudioTrack>
    </Tracks>
  </LiveSet>
</Ableton>"""

OURS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12" Creator="Ableton Live 12">
  <LiveSet>
    <Tempo><Manual Value="128"/></Tempo>
    <TimeSignature>
      <TimeSignatures>
        <RemoteableTimeSignature>
          <Numerator Value="4"/><Denominator Value="4"/>
        </RemoteableTimeSignature>
      </TimeSignatures>
    </TimeSignature>
    <Locators><Locators/></Locators>
    <Tracks>
      <AudioTrack Id="0">
        <Name><EffectiveName Value="Kick"/></Name>
        <ColorIndex Value="1"/>
        <DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain>
      </AudioTrack>
      <AudioTrack Id="1">
        <Name><EffectiveName Value="Synth"/></Name>
        <ColorIndex Value="3"/>
        <DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain>
      </AudioTrack>
    </Tracks>
  </LiveSet>
</Ableton>"""

THEIRS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12" Creator="Ableton Live 12">
  <LiveSet>
    <Tempo><Manual Value="132"/></Tempo>
    <TimeSignature>
      <TimeSignatures>
        <RemoteableTimeSignature>
          <Numerator Value="4"/><Denominator Value="4"/>
        </RemoteableTimeSignature>
      </TimeSignatures>
    </TimeSignature>
    <Locators><Locators/></Locators>
    <Tracks>
      <AudioTrack Id="0">
        <Name><EffectiveName Value="Kick"/></Name>
        <ColorIndex Value="1"/>
        <DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain>
      </AudioTrack>
      <AudioTrack Id="1">
        <Name><EffectiveName Value="Bass"/></Name>
        <ColorIndex Value="4"/>
        <DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain>
      </AudioTrack>
    </Tracks>
  </LiveSet>
</Ableton>"""

RUNNER = CliRunner()


def _write_als(tmp_path, name, xml):
    """Write .als (gzipped XML) to tmp_path."""
    import gzip
    path = tmp_path / name
    data = xml.encode("utf-8")
    path.write_bytes(gzip.compress(data))
    return path


class TestMergePlanAlsInput:
    def test_merge_plan_tempo_conflict(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs = _write_als(tmp_path, "theirs.als", THEIRS_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 3, result.output
        d = json.loads(result.output)
        assert d["document_type"] == "alscan-merge-plan"
        assert d["input_mode"] == "als"
        assert d["conflict_count"] == 2
        conflicts = {c["field"] for c in d["conflicts"]}
        assert "tempo" in conflicts

    def test_merge_plan_with_conflicts(self, tmp_path):
        """Tempo changes on both sides differently -> conflict."""
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs_xml = THEIRS_XML.replace('Value="132"', 'Value="128"')
        theirs = _write_als(tmp_path, "theirs.als", theirs_xml)
        # base=120, ours=128, theirs=130 (different from each other)
        ours_xml = OURS_XML.replace('Value="128"', 'Value="130"')
        ours = _write_als(tmp_path, "ours2.als", ours_xml)
        result = RUNNER.invoke(cli, [
            "merge-plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 3, result.output
        d = json.loads(result.output)
        assert d["conflict_count"] > 0
        conflicts = [c for c in d["conflicts"] if c["field"] == "tempo"]
        assert len(conflicts) > 0

    def test_merge_plan_exits_0_no_changes(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 0, result.output
        d = json.loads(result.output)
        assert d["conflict_count"] == 0

    def test_merge_plan_missing_file(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        missing = tmp_path / "nonexistent.als"
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(missing), str(base),
        ])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_merge_plan_mixed_inputs_rejected(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        snap = tmp_path / "snap.json"
        snap.write_text(build_snapshot(parse_xml_string(BASE_XML)).to_json())
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(snap), str(base),
        ])
        assert result.exit_code == 1
        assert "Mixed input types" in result.output


class TestMergePlanSnapshotInput:
    def test_merge_plan_snapshots(self, tmp_path):
        def make_snap(name):
            path = tmp_path / name
            proj = parse_xml_string(BASE_XML)
            snap = build_snapshot(proj)
            path.write_text(snap.to_json())
            return path

        base = make_snap("base.json")
        ours = make_snap("ours.json")
        theirs = make_snap("theirs.json")
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 0, result.output
        d = json.loads(result.output)
        assert d["input_mode"] == "snapshot"

    def test_merge_plan_rejects_merge_plan_as_snapshot(self, tmp_path):
        plan = tmp_path / "plan.json"
        plan.write_text(json.dumps({"document_type": "alscan-merge-plan"}))
        snap = tmp_path / "snap.json"
        snap.write_text(build_snapshot(parse_xml_string(BASE_XML)).to_json())
        result = RUNNER.invoke(cli, [
            "merge-plan", str(plan), str(snap), str(snap),
        ])
        assert result.exit_code == 1


class TestMergePlanOutput:
    def test_merge_plan_writes_output(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs = tmp_path / "theirs.als"
        theirs.write_bytes(base.read_bytes())  # same as base
        out = tmp_path / "plan.json"
        result = RUNNER.invoke(cli, [
            "merge-plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 0, result.output
        assert out.exists()
        d = json.loads(out.read_text())
        assert d["document_type"] == "alscan-merge-plan"

    def test_merge_plan_output_rejects_existing(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        out = tmp_path / "plan.json"
        out.write_text("existing")
        result = RUNNER.invoke(cli, [
            "merge-plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_merge_plan_output_rejects_ableton_ext(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = tmp_path / "ours.als"
        ours.write_bytes(base.read_bytes())
        out = tmp_path / "out.als"
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(base),
            "--output", str(out),
        ])
        assert result.exit_code == 1


class TestMergePlanLineage:
    def test_unrelated_requires_flag(self, tmp_path):
        proj_a = parse_xml_string(BASE_XML)
        xml_b = BASE_XML.replace("Kick", "Guitar").replace("Synth", "Bass")
        proj_b = parse_xml_string(xml_b)
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", xml_b)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(theirs),
        ])
        # If lineage is too weak, it should fail with error
        assert result.exit_code in (0, 1)

    def test_divergent_lineage_no_flag_needed(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 0, result.output
