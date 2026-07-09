# SPDX-License-Identifier: GPL-3.0-only
"""Tests for alscan.services — shared typed application APIs."""

from pathlib import Path
import json

import pytest

from alscan.services import (
    scan_project,
    scan_projects_recursive,
    get_checks,
    get_check,
    create_snapshot,
    list_snapshots,
    compare_sources,
    create_merge_plan,
    render_health_report,
    save_report,
    save_merge_plan,
    save_merge_report,
    ScanError,
    SnapshotError,
    CompareError,
    MergePlanError,
    ReportError,
    ScanOptions,
)
from alscan.models import ScanResult, Finding
from alscan.merge.plan import MergePlan


FIXTURES = Path(__file__).parent / "fixtures"


class TestScanProject:
    def test_scan_clean_project(self):
        result = scan_project(FIXTURES / "clean.als")
        assert isinstance(result, ScanResult)
        assert len(result.findings) == 0

    def test_scan_all_checks_project(self):
        result = scan_project(FIXTURES / "all_checks.als")
        assert isinstance(result, ScanResult)
        assert len(result.findings) > 0
        assert len(result.errors) > 0
        assert len(result.warnings) > 0
        assert len(result.info) > 0

    def test_scan_missing_path(self):
        with pytest.raises(ScanError):
            scan_project("/nonexistent/path.als")

    def test_scan_project_folder(self):
        with pytest.raises(ScanError, match="Multiple"):
            scan_project(FIXTURES)

    def test_scan_with_options(self):
        opts = ScanOptions(verbose=True)
        result = scan_project(FIXTURES / "clean.als", opts)
        assert isinstance(result, ScanResult)

    def test_scan_cancelled(self):
        def cancel():
            return True
        with pytest.raises(ScanError, match="cancelled"):
            scan_project(
                FIXTURES / "all_checks.als",
                cancelled_cb=cancel,
            )


class TestScanRecursive:
    def test_recursive_finds_projects(self):
        results = scan_projects_recursive(FIXTURES)
        assert len(results) >= 1
        for proj_dir, result, error in results:
            if result:
                assert isinstance(result, ScanResult)
            else:
                assert error is not None

    def test_recursive_cancelled(self):
        def cancel():
            return True
        with pytest.raises(ScanError, match="cancelled"):
            scan_projects_recursive(FIXTURES, cancelled_cb=cancel)


class TestGetChecks:
    def test_list_checks(self):
        checks = get_checks()
        names = {c.name for c in checks}
        assert "missing_samples" in names
        assert "broken_plugins" in names
        assert len(checks) == 19

    def test_get_check_by_name(self):
        c = get_check("missing_samples")
        assert c is not None
        assert c.name == "missing_samples"
        assert c.severity == "error"

    def test_get_check_nonexistent(self):
        assert get_check("nonexistent_check") is None


class TestSnapshots:
    def test_create_and_list_snapshots(self, tmp_path):
        # Copy fixture to tmp_path so snapshot dir is safe
        import shutil
        src = FIXTURES / "clean.als"
        dest = tmp_path / "clean.als"
        shutil.copy2(src, dest)
        snap_path = create_snapshot(dest)
        assert snap_path.exists()
        assert snap_path.suffix == ".json"

        infos = list_snapshots(dest)
        assert len(infos) == 1
        info = infos[0]
        assert info.project_name == "clean"
        assert info.tempo == 120.0

    def test_snapshot_missing_path(self):
        with pytest.raises(SnapshotError):
            create_snapshot("/nonexistent/path.als")


class TestCompareSources:
    def test_compare_als_files(self):
        result = compare_sources(
            FIXTURES / "clean.als",
            FIXTURES / "all_checks.als",
        )
        assert result.has_changes
        assert result.tempo_changed

    def test_compare_same_files(self):
        result = compare_sources(
            FIXTURES / "clean.als",
            FIXTURES / "clean.als",
        )
        assert not result.has_changes

    def test_compare_invalid_path(self):
        with pytest.raises(CompareError):
            compare_sources("/nonexistent.als", FIXTURES / "clean.als")


class TestMergePlan:
    def test_merge_plan_three_als(self, tmp_path):
        import gzip as _gz
        BASE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12" Creator="Ableton Live 12">
  <LiveSet>
    <Tempo><Manual Value="120"/></Tempo>
    <TimeSignature><TimeSignatures><RemoteableTimeSignature><Numerator Value="4"/><Denominator Value="4"/></RemoteableTimeSignature></TimeSignatures></TimeSignature>
    <Locators><Locators/></Locators>
    <Tracks><AudioTrack Id="0"><Name><EffectiveName Value="Kick"/></Name><ColorIndex Value="1"/><DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain></AudioTrack></Tracks>
  </LiveSet>
</Ableton>"""
        OURS_XML = BASE_XML.replace('Value="120"', 'Value="128"')
        THEIRS_XML = BASE_XML.replace('Value="120"', 'Value="132"')

        base_p = tmp_path / "base.als"
        ours_p = tmp_path / "ours.als"
        theirs_p = tmp_path / "theirs.als"

        base_p.write_bytes(_gz.compress(BASE_XML.encode()))
        ours_p.write_bytes(_gz.compress(OURS_XML.encode()))
        theirs_p.write_bytes(_gz.compress(THEIRS_XML.encode()))

        plan = create_merge_plan(
            str(base_p), str(ours_p), str(theirs_p),
            allow_unrelated=True,
        )
        assert isinstance(plan, MergePlan)
        assert plan.conflict_count > 0

    def test_merge_plan_nonexistent(self):
        with pytest.raises(MergePlanError):
            create_merge_plan("/nonexistent.als", "/nonexistent.als", "/nonexistent.als")


class TestReports:
    def test_render_json_report(self, tmp_path):
        from alscan.parser import parse_als
        proj = parse_als(FIXTURES / "clean.als")
        from alscan.checks import list_checks
        findings = []
        for check in list_checks():
            findings.extend(check.func(proj))
        result = ScanResult(project=proj, findings=findings)
        text = render_health_report(result, "json")
        d = json.loads(text)
        assert "project" in d
        assert "findings" in d

    def test_render_html_report(self, tmp_path):
        from alscan.parser import parse_als
        proj = parse_als(FIXTURES / "clean.als")
        from alscan.checks import list_checks
        findings = []
        for check in list_checks():
            findings.extend(check.func(proj))
        result = ScanResult(project=proj, findings=findings)
        html = render_health_report(result, "html")
        assert "<html" in html.lower() or "<!DOCTYPE" in html

    def test_save_report(self, tmp_path):
        dest = tmp_path / "report.json"
        saved = save_report('{"test": true}', dest)
        assert saved == dest.resolve()
        assert dest.exists()

    def test_save_report_existing_fails(self, tmp_path):
        dest = tmp_path / "report.json"
        dest.write_text("existing")
        with pytest.raises(ReportError):
            save_report("new content", dest)

    def test_save_merge_plan(self, tmp_path):
        plan = MergePlan()
        sources = [tmp_path / "base.als"]
        sources[0].write_text("")
        dest = tmp_path / "plan.json"
        saved = save_merge_plan(plan, dest, sources)
        assert saved.exists()

    def test_save_merge_report(self, tmp_path):
        plan = MergePlan()
        plan.sources = {
            "base": {"sha256": "abc", "size": 1, "label": "base.als"},
            "ours": {"sha256": "def", "size": 1, "label": "ours.als"},
            "theirs": {"sha256": "ghi", "size": 1, "label": "theirs.als"},
        }
        sources = [tmp_path / "base.als"]
        sources[0].write_text("")
        dest = tmp_path / "report.html"
        saved = save_merge_report(plan, dest, sources)
        assert saved.exists()
        assert saved.read_text() != ""


class TestProgressCallbacks:
    def test_scan_progress_called(self):
        progress_log = []

        def progress(completed, total, label):
            progress_log.append((completed, total, label))

        result = scan_project(
            FIXTURES / "clean.als",
            progress_cb=progress,
        )
        assert isinstance(result, ScanResult)
        assert len(progress_log) > 0
