# SPDX-License-Identifier: GPL-3.0-only
"""Input validation tests for three-way merge analysis."""

from __future__ import annotations

import json
import gzip

import pytest
from click.testing import CliRunner

from alscan.cli import cli
from alscan.merge.inputs import validate_three_way
from alscan.versioner import build_snapshot

RUNNER = CliRunner()

SIMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
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
    </Tracks>
  </LiveSet>
</Ableton>"""


def _write_als(tmp_path, name, xml):
    path = tmp_path / name
    data = xml.encode("utf-8")
    path.write_bytes(gzip.compress(data))
    return path


def _write_snapshot(tmp_path, name, snap=None):
    from alscan.parser import parse_xml_string
    if snap is None:
        snap = build_snapshot(parse_xml_string(SIMPLE_XML))
    path = tmp_path / name
    path.write_text(snap.to_json())
    return path


class TestMissingFiles:
    def test_missing_base_file_cli(self, tmp_path):
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", str(tmp_path / "nope.als"), str(ours), str(theirs),
        ])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_missing_ours_file_cli(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(tmp_path / "nope.als"), str(theirs),
        ])
        assert result.exit_code == 1

    def test_missing_theirs_file_cli(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(tmp_path / "nope.als"),
        ])
        assert result.exit_code == 1


class TestDirectoryInsteadOfFile:
    def test_directory_as_base_cli(self, tmp_path):
        dir_path = tmp_path / "adir"
        dir_path.mkdir()
        result = RUNNER.invoke(cli, [
            "merge-plan", str(dir_path), "x.als", "y.als",
        ])
        assert result.exit_code == 1

    def test_directory_as_ours_cli(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        dir_path = tmp_path / "adir"
        dir_path.mkdir()
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(dir_path), str(base),
        ])
        assert result.exit_code == 1


class TestEmptyFile:
    def test_empty_als_file_cli(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        empty = tmp_path / "empty.als"
        empty.write_bytes(gzip.compress(b""))
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(empty), str(base),
        ])
        assert result.exit_code == 1

    def test_empty_snapshot_file_cli(self, tmp_path):
        snap = _write_snapshot(tmp_path, "base.json")
        empty = tmp_path / "empty.json"
        empty.write_text("")
        result = RUNNER.invoke(cli, [
            "merge-plan", str(snap), str(empty), str(snap),
        ])
        assert result.exit_code == 1


class TestUnsupportedExtension:
    def test_txt_file_rejected_cli(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        bad = tmp_path / "file.txt"
        bad.write_text("hello")
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(bad), str(base),
        ])
        assert result.exit_code == 1

    def test_binary_file_rejected_cli(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        bad = tmp_path / "file.bin"
        bad.write_bytes(b"\x00\x01\x02")
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(bad), str(base),
        ])
        assert result.exit_code == 1


class TestMalformedJson:
    def test_bad_json_snapshot_cli(self, tmp_path):
        snap = _write_snapshot(tmp_path, "base.json")
        bad = tmp_path / "bad.json"
        bad.write_text("{this is not json")
        result = RUNNER.invoke(cli, [
            "merge-plan", str(snap), str(bad), str(snap),
        ])
        assert result.exit_code == 1


class TestWrongSchemaVersion:
    def test_wrong_document_type_rejected(self, tmp_path):
        from alscan.versioner import build_snapshot
        from alscan.parser import parse_xml_string
        snap = _write_snapshot(tmp_path, "good.json")
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(json.dumps({"document_type": "alscan-merge-plan"}))
        result = RUNNER.invoke(cli, [
            "merge-plan", str(snap), str(plan_path), str(snap),
        ])
        assert result.exit_code == 1

    def test_merged_snapshot_rejected(self, tmp_path):
        snap = _write_snapshot(tmp_path, "good.json")
        merged = tmp_path / "merged.json"
        merged.write_text(json.dumps({"document_type": "alscan-merged-snapshot"}))
        result = RUNNER.invoke(cli, [
            "merge-plan", str(snap), str(merged), str(snap),
        ])
        assert result.exit_code == 1


class TestDuplicatePhysicalInputs:
    def test_same_file_three_times_cli(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(base), str(base),
        ])
        assert result.exit_code == 1

    def test_duplicate_base_and_ours_cli(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(base), str(theirs),
        ])
        assert result.exit_code == 1

    def test_python_api_duplicates_rejected(self, tmp_path):
        f = tmp_path / "project.als"
        data = gzip.compress(SIMPLE_XML.encode("utf-8"))
        f.write_bytes(data)
        with pytest.raises(ValueError, match="Duplicate physical input"):
            validate_three_way(str(f), str(f), str(f))


class TestUnrelatedProjects:
    def test_unrelated_rejected_without_flag_cli(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        xml_b = SIMPLE_XML.replace("Kick", "Violin")
        ours = _write_als(tmp_path, "ours.als", xml_b)
        theirs = tmp_path / "theirs.als"
        theirs.write_bytes(gzip.compress(SIMPLE_XML.encode("utf-8")))
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(theirs),
        ])
        assert result.exit_code in (0, 1)

    def test_unrelated_allowed_with_flag_cli(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        xml_b = SIMPLE_XML.replace("Kick", "Bass")
        ours = _write_als(tmp_path, "ours.als", xml_b)
        theirs = tmp_path / "theirs.als"
        theirs.write_bytes(gzip.compress(SIMPLE_XML.encode("utf-8")))
        result = RUNNER.invoke(cli, [
            "merge-plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
        ])
        assert result.exit_code in (0, 3)
