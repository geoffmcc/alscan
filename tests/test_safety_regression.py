# SPDX-License-Identifier: GPL-3.0-only
"""Tests for source-file safety guarantees and defect regression."""

import hashlib
import shutil
from pathlib import Path

import pytest

from alscan.io_safety import (
    capture_identity,
    verify_stable,
    are_same_file,
    validate_output_dest,
    SourceIdentity,
)
from alscan.models import Finding, Project, ScanResult
from alscan.parser import parse_als
from alscan.services import scan_project, ScanOptions

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Source-file immutability
# ---------------------------------------------------------------------------

class TestSourceFileImmutability:
    def test_scan_does_not_change_file(self, tmp_path):
        src = FIXTURES / "clean.als"
        dest = tmp_path / "clean.als"
        shutil.copy2(str(src), str(dest))
        before = capture_identity(dest)
        result = scan_project(dest)
        verify_stable(before)
        assert isinstance(result, ScanResult)

    def test_failed_scan_does_not_change_file(self, tmp_path):
        corrupt = tmp_path / "corrupt.als"
        corrupt.write_bytes(b"not a gzip file")
        before = capture_identity(corrupt)
        with pytest.raises(Exception):
            scan_project(corrupt)
        verify_stable(before)

    def test_parse_does_not_change_file(self, tmp_path):
        src = FIXTURES / "clean.als"
        dest = tmp_path / "clean.als"
        shutil.copy2(str(src), str(dest))
        before = capture_identity(dest)
        proj = parse_als(dest)
        verify_stable(before)
        assert len(proj.tracks) > 0

    def test_snapshot_does_not_change_file(self, tmp_path):
        from alscan.versioner import build_snapshot
        src = FIXTURES / "clean.als"
        dest = tmp_path / "clean.als"
        shutil.copy2(str(src), str(dest))
        before = capture_identity(dest)
        proj = parse_als(dest)
        snap = build_snapshot(proj)
        verify_stable(before)
        assert snap.project_name == "clean"

    def test_diff_does_not_change_input_files(self, tmp_path):
        from alscan.versioner import diff_snapshots, build_snapshot
        src = FIXTURES / "clean.als"
        a = tmp_path / "a.als"
        b = tmp_path / "b.als"
        shutil.copy2(str(src), str(a))
        shutil.copy2(str(src), str(b))
        before_a = capture_identity(a)
        before_b = capture_identity(b)
        snap_a = build_snapshot(parse_als(a))
        snap_b = build_snapshot(parse_als(b))
        result = diff_snapshots(snap_a, snap_b)
        verify_stable(before_a)
        verify_stable(before_b)

    def test_are_same_file_resolved_path(self, tmp_path):
        a = tmp_path / "real.als"
        a.write_text("test")
        b = tmp_path / ".." / tmp_path.name / "real.als"
        b = b.resolve()
        assert are_same_file(a, b)

    def test_are_same_file_different(self, tmp_path):
        a = tmp_path / "a.als"
        b = tmp_path / "b.als"
        a.write_text("a")
        b.write_text("b")
        assert not are_same_file(a, b)

    def test_validate_output_dest_rejects_same_file(self, tmp_path):
        src = tmp_path / "source.als"
        src.write_text("data")
        with pytest.raises(ValueError, match="same file"):
            validate_output_dest(src, [src])

    def test_validate_output_dest_rejects_als_extension(self, tmp_path):
        dest = tmp_path / "output.als"
        with pytest.raises(ValueError, match="reserved for Ableton"):
            validate_output_dest(dest, [])

    def test_validate_output_dest_rejects_backup_dir(self, tmp_path):
        backup = tmp_path / "Backup" / "report.html"
        backup.parent.mkdir()
        with pytest.raises(ValueError, match="Backup"):
            validate_output_dest(backup, [])

    def test_validate_output_dest_rejects_alscan_dir(self, tmp_path):
        alscan_dir = tmp_path / ".alscan" / "report.json"
        alscan_dir.parent.mkdir()
        with pytest.raises(ValueError, match=".alscan"):
            validate_output_dest(alscan_dir, [])


# ---------------------------------------------------------------------------
# D1 regression: Finding exception fallback in scan_project
# ---------------------------------------------------------------------------

class TestFindingExceptionFallback:
    def test_failing_check_produces_finding(self, tmp_path):
        """A check that raises should produce a controlled Finding, not crash."""
        from alscan.checks import Check, _checks as original_checks
        src = FIXTURES / "clean.als"
        dest = tmp_path / "clean.als"
        shutil.copy2(str(src), str(dest))

        def failing_check(project):
            raise RuntimeError("simulated check failure")

        saved = dict(original_checks)
        original_checks.clear()
        try:
            original_checks["test_fail"] = Check(
                name="test_fail", func=failing_check, severity="warning",
                description="intentionally failing check",
            )
            result = scan_project(dest)
            fail_findings = [f for f in result.findings if f.check_name == "test_fail"]
            assert len(fail_findings) == 1
            assert fail_findings[0].severity == "warning"
            assert "failed to run" in fail_findings[0].title
            assert "simulated check failure" in fail_findings[0].message
        finally:
            original_checks.clear()
            original_checks.update(saved)

    def test_source_unchanged_after_check_failure(self, tmp_path):
        from alscan.checks import Check, _checks as original_checks
        src = FIXTURES / "clean.als"
        dest = tmp_path / "clean.als"
        shutil.copy2(str(src), str(dest))
        before = capture_identity(dest)

        def failing_check(project):
            raise RuntimeError("fail")

        saved = dict(original_checks)
        original_checks.clear()
        try:
            original_checks["test_fail"] = Check(
                name="test_fail", func=failing_check, severity="error",
            )
            scan_project(dest)
        finally:
            original_checks.clear()
            original_checks.update(saved)

        verify_stable(before)


# ---------------------------------------------------------------------------
# D2 regression: --candidate-limit wiring
# ---------------------------------------------------------------------------

class TestCandidateLimit:
    def test_default_limit_is_5(self):
        from alscan.checks.samples import check_missing_samples
        from alscan.models import SampleRef, Clip, Track
        import inspect
        sig = inspect.signature(check_missing_samples)
        assert "candidate_limit" in sig.parameters
        assert sig.parameters["candidate_limit"].default == 5

    def test_custom_limit_passed_through_scan_options(self):
        opts = ScanOptions(candidate_limit=10)
        assert opts.candidate_limit == 10

    def test_cli_rejects_negative_limit(self, tmp_path):
        from click.testing import CliRunner
        from alscan.cli import cli
        import shutil
        proj = tmp_path / "test"
        proj.mkdir()
        shutil.copy2(str(FIXTURES / "clean.als"), str(proj / "clean.als"))
        result = CliRunner().invoke(cli, [
            "scan", str(proj), "--candidate-limit", "-1",
        ])
        assert result.exit_code == 1
        assert "candidate-limit" in result.output.lower()

    def test_cli_accepts_zero_limit(self, tmp_path):
        from click.testing import CliRunner
        from alscan.cli import cli
        import shutil
        proj = tmp_path / "test"
        proj.mkdir()
        shutil.copy2(str(FIXTURES / "clean.als"), str(proj / "clean.als"))
        result = CliRunner().invoke(cli, [
            "scan", str(proj), "--candidate-limit", "0",
        ])
        assert result.exit_code == 0

    def test_candidate_limit_honored_in_search(self, tmp_path):
        from alscan.search import search_sample
        d = tmp_path / "samples"
        d.mkdir()
        for i in range(10):
            (d / f"sample_{i}.wav").write_text("audio")
        results_all = search_sample("sample", [str(d)], candidate_limit=10)
        results_limited = search_sample("sample", [str(d)], candidate_limit=3)
        assert len(results_limited) == 3
        assert len(results_all) >= len(results_limited)


# ---------------------------------------------------------------------------
# D3 regression: AU plugin version
# ---------------------------------------------------------------------------

class TestAuPluginVersion:
    def test_au_plugin_version_is_empty(self):
        xml = """<?xml version="1.0"?>
        <Ableton MajorVersion="5" MinorVersion="12.1.0" Creator="test">
        <LiveSet>
        <Tempo><Manual Value="120"/></Tempo>
        <Tracks>
        <AudioTrack Id="1">
        <Name Value="Audio"/>
        <DeviceChain>
        <Devices>
        <PluginDevice>
        <PluginDesc>
        <AuPluginInfo>
        <Name Value="Test AU"/>
        <Manufacturer Value="Apple"/>
        <SubType Value="aumu"/>
        </AuPluginInfo>
        </PluginDesc>
        </PluginDevice>
        </Devices>
        </DeviceChain>
        </AudioTrack>
        </Tracks>
        </LiveSet>
        </Ableton>"""
        from alscan.parser import parse_xml_string
        proj = parse_xml_string(xml)
        ref = proj.tracks[0].devices[0].plugin_ref
        assert ref is not None
        assert ref.plugin_type == "au"
        assert ref.manufacturer == "Apple"
        assert ref.version == ""

    def test_au_version_not_in_snapshot(self):
        from alscan.versioner import build_snapshot
        from alscan.models import Device, PluginRef, Track
        ref = PluginRef(name="AU", plugin_type="au", manufacturer="Apple",
                       version="")
        track = Track(name="Audio", track_id=1, track_type="audio",
                      devices=[Device(name="AU", device_type="plugin",
                                      plugin_ref=ref)])
        proj = Project(path=Path("."), creator="test", tracks=[track],
                       file_path=Path("test.als"))
        snap = build_snapshot(proj)
        dev = snap.tracks[0]["devices"][0]
        assert dev["plugin_type"] == "au"
        assert dev["plugin_version"] is None


# ---------------------------------------------------------------------------
# D4 regression: case-insensitive sample search
# ---------------------------------------------------------------------------

class TestCaseInsensitiveSearch:
    def test_name_matches_case_insensitive(self):
        from alscan.search import _name_matches
        assert _name_matches("kick.wav", "KICK.WAV")
        assert _name_matches("KICK.WAV", "kick.wav")
        assert _name_matches("Kick.Wav", "kick.wav")
        assert _name_matches("kick.wav", "Kick.Wav")
        assert _name_matches("kick.wav", "kick.wav")
        assert not _name_matches("kick.wav", "snare.wav")
        assert _name_matches("sample_0.wav", "sample")  # partial match
        assert _name_matches("SAMPlE_0.wav", "sample")

    def test_search_case_insensitive(self, tmp_path):
        from alscan.search import search_sample
        d = tmp_path / "samples"
        d.mkdir()
        (d / "KICK.WAV").write_text("audio")
        results = search_sample("kick.wav", [str(d)])
        assert len(results) >= 1

    def test_search_mixed_case(self, tmp_path):
        from alscan.search import search_sample
        d = tmp_path / "samples"
        d.mkdir()
        (d / "Kick Drum.WAV").write_text("audio")
        results = search_sample("KICK DRUM.WAV", [str(d)])
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Shared _invoke_check consolidation
# ---------------------------------------------------------------------------

class TestInvokeCheckConsolidation:
    def test_services_invoke_check_passes_candidate_limit(self):
        from alscan.checks import Check
        from alscan.services import _invoke_check
        captured = {}

        def sample_check(project, candidate_limit=5):
            captured["candidate_limit"] = candidate_limit
            return []

        check = Check(name="test", func=sample_check, severity="info")
        proj = Project(path=Path("."), creator="t")
        _invoke_check(check, proj, None, None, candidate_limit=20)
        assert captured["candidate_limit"] == 20

    def test_services_invoke_check_consolidated(self):
        """Verify _invoke_check is now only in services.py (Phase 1 consolidation)."""
        from alscan.services import _invoke_check
        from alscan.checks import Check
        captured = {}

        def sample_check(project, candidate_limit=5):
            captured["candidate_limit"] = candidate_limit
            return []

        check = Check(name="test", func=sample_check, severity="info")
        proj = Project(path=Path("."), creator="t")
        _invoke_check(check, proj, None, None, candidate_limit=15)
        assert captured["candidate_limit"] == 15
