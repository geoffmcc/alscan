# SPDX-License-Identifier: GPL-3.0-only
import gzip
import json

import pytest
from click.testing import CliRunner

from alscan.cli import cli
from alscan.merge.manifest import MergeManifest, MANIFEST_FORMAT_VERSION


def _write_als(tmp_path, name, xml):
    path = tmp_path / name
    path.write_bytes(gzip.compress(xml.encode("utf-8")))
    return path


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
      <AudioTrack Id="2">
        <Name><EffectiveName Value="Bass"/></Name>
        <ColorIndex Value="2"/>
        <DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain>
      </AudioTrack>
    </Tracks>
  </LiveSet>
</Ableton>"""

RUNNER = CliRunner()


class TestMergeGuideCli:
    def test_merge_guide_basic(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        result = RUNNER.invoke(cli, [
            "merge", "guide", "--allow-unrelated",
            str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 0, result.output

    def test_merge_guide_missing_args(self, tmp_path):
        result = RUNNER.invoke(cli, ["merge", "guide"])
        assert result.exit_code == 1, result.output

    def test_merge_guide_not_found(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        missing = tmp_path / "ghost.als"
        result = RUNNER.invoke(cli, [
            "merge", "guide",
            str(base), str(missing), str(base),
        ])
        assert result.exit_code == 1, result.output

    def test_merge_guide_unknown_subcommand(self, tmp_path):
        result = RUNNER.invoke(cli, ["merge", "nonesuch", "a", "b", "c"])
        assert result.exit_code == 1, result.output


class TestMergePlanManifestCli:
    def test_merge_plan_output(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        out = tmp_path / "manifest.json"
        result = RUNNER.invoke(cli, [
            "merge", "plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 0, result.output
        assert out.exists()
        d = json.loads(out.read_text(encoding="utf-8"))
        assert d["document_type"] == "alscan-merge-manifest"
        assert d["format_version"] == MANIFEST_FORMAT_VERSION
        assert "session" in d
        assert "operations" in d
        assert "source_hashes_captured" in d
        assert isinstance(d["operations"], list)

    def test_merge_plan_stdout(self, tmp_path):
        same = BASE_XML
        base = _write_als(tmp_path, "a.als", same)
        ours = _write_als(tmp_path, "b.als", same)
        theirs = _write_als(tmp_path, "c.als", same)
        result = RUNNER.invoke(cli, [
            "merge", "plan",
            str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 0, result.output

    def test_merge_plan_rejects_output_collision(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        out = tmp_path / "manifest.json"
        out.write_text("existing")
        result = RUNNER.invoke(cli, [
            "merge", "plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 1, result.output

    def test_merge_plan_rejects_ableton_dest(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        out = tmp_path / "out.als"
        result = RUNNER.invoke(cli, [
            "merge", "plan",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 1, result.output

    def test_merge_plan_exit_code_conflicts(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs_xml = OURS_XML.replace('Value="128"', 'Value="132"')
        theirs = _write_als(tmp_path, "theirs.als", theirs_xml)
        result = RUNNER.invoke(cli, [
            "merge", "plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 3, result.output


class TestMergeVerifyCli:
    def test_merge_verify_missing_args(self, tmp_path):
        result = RUNNER.invoke(cli, ["merge", "verify"])
        assert result.exit_code == 1, result.output

    def test_merge_verify_manifest_not_found(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        result = RUNNER.invoke(cli, [
            "merge", "verify",
            str(tmp_path / "missing.json"),
            str(base),
        ])
        assert result.exit_code == 1, result.output

    def test_merge_verify_malformed_manifest(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json")
        base = _write_als(tmp_path, "base.als", BASE_XML)
        result = RUNNER.invoke(cli, [
            "merge", "verify",
            str(bad), str(base),
        ])
        assert result.exit_code == 1, result.output

    def test_merge_verify_dest_missing(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        out = tmp_path / "manifest.json"
        run = RUNNER.invoke(cli, [
            "merge", "plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert run.exit_code == 0, run.output
        result = RUNNER.invoke(cli, [
            "merge", "verify",
            str(out), str(tmp_path / "gone.als"),
        ])
        assert result.exit_code == 3, result.output

    def test_merge_verify_against_self(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        out = tmp_path / "manifest.json"
        run = RUNNER.invoke(cli, [
            "merge", "plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert run.exit_code == 0, run.output
        result = RUNNER.invoke(cli, [
            "merge", "verify",
            str(out), str(base),
        ])
        assert result.exit_code == 3, result.output


class TestMergeResumeCli:
    def test_merge_resume_no_args(self, tmp_path):
        result = RUNNER.invoke(cli, ["merge", "resume"])
        assert result.exit_code == 1, result.output

    def test_merge_resume_not_found(self, tmp_path):
        result = RUNNER.invoke(cli, [
            "merge", "resume",
            str(tmp_path / "nope.json"),
        ])
        assert result.exit_code == 1, result.output

    def test_merge_resume_basic(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        out = tmp_path / "manifest.json"
        run = RUNNER.invoke(cli, [
            "merge", "plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert run.exit_code == 0, run.output
        result = RUNNER.invoke(cli, [
            "merge", "resume", str(out),
        ])
        assert result.exit_code == 0, result.output

    def test_merge_resume_malformed(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not a manifest")
        result = RUNNER.invoke(cli, [
            "merge", "resume", str(bad),
        ])
        assert result.exit_code == 1, result.output


class TestMergeManifestRoundtrip:
    def test_manifest_generation_and_parsing(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        out = tmp_path / "manifest.json"
        run = RUNNER.invoke(cli, [
            "merge", "plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert run.exit_code == 0, run.output
        raw = out.read_text(encoding="utf-8")
        manifest = MergeManifest.from_json(raw)
        assert manifest.document_type == "alscan-merge-manifest"
        assert manifest.format_version == MANIFEST_FORMAT_VERSION
        session = manifest.get_session()
        assert session.session_id
        assert session.workflow_state in {
            "choosing_foundation", "analyzing",
        }
        operations = manifest.get_operations()
        assert isinstance(operations, list)

    def test_manifest_has_source_hashes(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        out = tmp_path / "manifest.json"
        run = RUNNER.invoke(cli, [
            "merge", "plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert run.exit_code == 0, run.output
        raw = out.read_text(encoding="utf-8")
        manifest = MergeManifest.from_json(raw)
        assert isinstance(manifest.source_hashes_captured, dict)
        assert "base" in manifest.source_hashes_captured
        assert "ours" in manifest.source_hashes_captured
        assert "theirs" in manifest.source_hashes_captured
        for role in ("base", "ours", "theirs"):
            assert len(manifest.source_hashes_captured[role]) == 64

    def test_manifest_operations_have_ids(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", OURS_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        out = tmp_path / "manifest.json"
        run = RUNNER.invoke(cli, [
            "merge", "plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert run.exit_code == 0, run.output
        raw = out.read_text(encoding="utf-8")
        manifest = MergeManifest.from_json(raw)
        operations = manifest.get_operations()
        for op in operations:
            assert op.operation_id
            assert isinstance(op.operation_id, str)
            assert len(op.operation_id) > 0
