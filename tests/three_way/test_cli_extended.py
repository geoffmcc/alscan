# SPDX-License-Identifier: GPL-3.0-only
"""Extended CLI tests for three-way merge analysis."""

from __future__ import annotations

import json
import gzip

import pytest
from click.testing import CliRunner

from alscan.cli import cli
from alscan.merge.report import render_merge_report

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

CONFLICT_XML = """<?xml version="1.0" encoding="UTF-8"?>
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


def _write_als(tmp_path, name, xml):
    path = tmp_path / name
    path.write_bytes(gzip.compress(xml.encode("utf-8")))
    return path


class TestExitCodes:
    def test_exit_0_for_clean(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 0

    def test_exit_1_for_error(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), "nonexistent.als", str(base),
        ])
        assert result.exit_code == 1

    def test_exit_3_for_conflicts(self, tmp_path):
        base = _write_als(tmp_path, "base.als", CONFLICT_XML)
        xml_ours = CONFLICT_XML.replace('Value="120"', 'Value="128"')
        xml_theirs = CONFLICT_XML.replace('Value="120"', 'Value="140"')
        ours = _write_als(tmp_path, "ours.als", xml_ours)
        theirs = _write_als(tmp_path, "theirs.als", xml_theirs)
        result = RUNNER.invoke(cli, [
            "merge-plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 3

    def test_merge_report_exit_0_for_clean(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        out = tmp_path / "report.html"
        result = RUNNER.invoke(cli, [
            "merge-report", str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 0

    def test_merge_report_exit_3_for_conflicts(self, tmp_path):
        base = _write_als(tmp_path, "base.als", CONFLICT_XML)
        xml_ours = CONFLICT_XML.replace('Value="120"', 'Value="128"')
        xml_theirs = CONFLICT_XML.replace('Value="120"', 'Value="140"')
        ours = _write_als(tmp_path, "ours.als", xml_ours)
        theirs = _write_als(tmp_path, "theirs.als", xml_theirs)
        out = tmp_path / "report.html"
        result = RUNNER.invoke(cli, [
            "merge-report", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 3
        assert out.exists()


class TestOutputFileCreation:
    def test_merge_plan_output_valid_json(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        out = tmp_path / "plan.json"
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()
        d = json.loads(out.read_text())
        assert d["document_type"] == "alscan-merge-plan"

    def test_merge_report_output_valid_html(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        out = tmp_path / "report.html"
        result = RUNNER.invoke(cli, [
            "merge-report", str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()
        html = out.read_text()
        assert "<!doctype html>" in html.lower()

    def test_no_partial_output_on_error(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        out = tmp_path / "plan.json"
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), "nonexistent.als", str(base),
            "--output", str(out),
        ])
        assert result.exit_code == 1
        assert not out.exists()


class TestOutputFlagBehavior:
    def test_output_to_stdout_without_flag(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 0
        d = json.loads(result.output)
        assert d["document_type"] == "alscan-merge-plan"

    def test_output_to_file_skips_stdout(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        out = tmp_path / "plan.json"
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 0
        assert out.stat().st_size > 0

    def test_output_subdirectory(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        sub = tmp_path / "subdir"
        sub.mkdir()
        out = sub / "plan.json"
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()


class TestAllowUnrelatedFlag:
    def test_allow_unrelated_accepted(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge-plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 0


class TestSourceFilesUnchanged:
    def test_source_files_unchanged_after_analysis(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        base_bytes = base.read_bytes()
        ours_bytes = ours.read_bytes()
        theirs_bytes = theirs.read_bytes()
        RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(theirs),
        ])
        assert base.read_bytes() == base_bytes
        assert ours.read_bytes() == ours_bytes
        assert theirs.read_bytes() == theirs_bytes


class TestRejectOverwriteExisting:
    def test_reject_existing_output_file(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        out = tmp_path / "plan.json"
        out.write_text("existing content")
        result = RUNNER.invoke(cli, [
            "merge-plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_reject_existing_html_output(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        out = tmp_path / "report.html"
        out.write_text("existing")
        result = RUNNER.invoke(cli, [
            "merge-report", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 1


class TestRejectAlsExtension:
    def test_reject_als_output_extension(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        out = tmp_path / "output.als"
        result = RUNNER.invoke(cli, [
            "merge-plan", str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 1

    def test_reject_als_html_output(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        out = tmp_path / "report.als"
        result = RUNNER.invoke(cli, [
            "merge-report", str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 1
