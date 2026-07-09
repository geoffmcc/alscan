# SPDX-License-Identifier: GPL-3.0-only
"""Tests for CSV report output."""

import csv
import io
from pathlib import Path

import pytest

from alscan.models import Finding, Project, ScanResult
from alscan.report.csv import (
    generate_csv_report,
    generate_csv_batch,
    CSV_FIELD_NAMES,
    _formula_safe,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


# ---------------------------------------------------------------------------
# Formula injection protection
# ---------------------------------------------------------------------------

class TestFormulaSafe:
    def test_equals_prefix(self):
        assert _formula_safe("=SUM(A1)") == "'=SUM(A1)"

    def test_plus_prefix(self):
        assert _formula_safe("+100") == "'+100"

    def test_minus_prefix(self):
        assert _formula_safe("-100") == "'-100"

    def test_at_prefix(self):
        assert _formula_safe("@SUM") == "'@SUM"

    def test_normal_text_unchanged(self):
        assert _formula_safe("hello") == "hello"

    def test_empty_string(self):
        assert _formula_safe("") == ""

    def test_tab_prefix(self):
        assert _formula_safe("\t=cmd") == "\t=cmd"


# ---------------------------------------------------------------------------
# generate_csv_report — single project
# ---------------------------------------------------------------------------

class TestGenerateCsvReport:
    def test_header_row(self):
        proj = Project(path=Path("."), creator="t")
        result = ScanResult(project=proj, findings=[])
        csv_text = generate_csv_report(result)
        rows = _parse_csv(csv_text)
        assert len(rows) == 1
        assert list(rows[0].keys()) == CSV_FIELD_NAMES

    def test_no_findings_one_row(self):
        proj = Project(path=Path("."), creator="t")
        result = ScanResult(project=proj, findings=[])
        csv_text = generate_csv_report(result)
        rows = _parse_csv(csv_text)
        assert len(rows) == 1
        assert rows[0]["project"] == "unknown"
        assert rows[0]["severity"] == ""

    def test_one_finding(self):
        proj = Project(path=Path("/test"), file_path=Path("/test/song.als"), creator="t")
        f = Finding(
            severity="error", check_name="broken_plugins",
            title="Broken Plugin", message="Serum not found",
            location="Track 1", suggestion="Reinstall",
        )
        result = ScanResult(project=proj, findings=[f])
        csv_text = generate_csv_report(result)
        rows = _parse_csv(csv_text)
        assert len(rows) == 1
        assert rows[0]["project"] == "song"
        assert Path(rows[0]["project_path"]) == Path("/test")
        assert rows[0]["severity"] == "error"
        assert rows[0]["check_name"] == "broken_plugins"
        assert rows[0]["title"] == "Broken Plugin"
        assert rows[0]["message"] == "Serum not found"
        assert rows[0]["location"] == "Track 1"
        assert rows[0]["suggestion"] == "Reinstall"

    def test_multiple_findings(self):
        proj = Project(path=Path("."), file_path=Path("song.als"), creator="t")
        findings = [
            Finding(severity="error", check_name="a", title="A", message="m1",
                    location="", suggestion=""),
            Finding(severity="warning", check_name="b", title="B", message="m2",
                    location="", suggestion=""),
            Finding(severity="info", check_name="c", title="C", message="m3",
                    location="", suggestion=""),
        ]
        result = ScanResult(project=proj, findings=findings)
        csv_text = generate_csv_report(result)
        rows = _parse_csv(csv_text)
        assert len(rows) == 3

    def test_project_name_from_file_path(self):
        proj = Project(path=Path("."), file_path=Path("/music/my_track.als"), creator="t")
        result = ScanResult(project=proj, findings=[])
        csv_text = generate_csv_report(result)
        rows = _parse_csv(csv_text)
        assert rows[0]["project"] == "my_track"

    def test_project_name_fallback(self):
        proj = Project(path=Path("."), creator="t")
        result = ScanResult(project=proj, findings=[])
        csv_text = generate_csv_report(result)
        rows = _parse_csv(csv_text)
        assert rows[0]["project"] == "unknown"

    def test_commas_in_fields_quoted(self):
        proj = Project(path=Path("."), creator="t")
        f = Finding(
            severity="info", check_name="test",
            title="Comma, Title", message="Message, with, commas",
            location="Track, 1", suggestion="Fix, it, please",
        )
        result = ScanResult(project=proj, findings=[f])
        csv_text = generate_csv_report(result)
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        assert rows[0]["title"] == "Comma, Title"
        assert rows[0]["message"] == "Message, with, commas"

    def test_quotes_in_fields_escaped(self):
        proj = Project(path=Path("."), creator="t")
        f = Finding(
            severity="info", check_name="test",
            title='Quote "Test"', message='Say "hello"',
            location="", suggestion="",
        )
        result = ScanResult(project=proj, findings=[f])
        csv_text = generate_csv_report(result)
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        assert rows[0]["title"] == 'Quote "Test"'
        assert rows[0]["message"] == 'Say "hello"'

    def test_newlines_in_fields_quoted(self):
        proj = Project(path=Path("."), creator="t")
        f = Finding(
            severity="info", check_name="test",
            title="Line 1", message="Line 1\nLine 2",
            location="", suggestion="",
        )
        result = ScanResult(project=proj, findings=[f])
        csv_text = generate_csv_report(result)
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        assert "Line 1\nLine 2" == rows[0]["message"]

    def test_unicode_support(self):
        proj = Project(path=Path("."), creator="t")
        f = Finding(
            severity="info", check_name="test",
            title="Tést", message="café résumé naïve",
            location="", suggestion="",
        )
        result = ScanResult(project=proj, findings=[f])
        csv_text = generate_csv_report(result)
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        assert rows[0]["title"] == "Tést"

    def test_formula_injection_prevented(self):
        proj = Project(path=Path("."), creator="t")
        f = Finding(
            severity="info", check_name="test",
            title="=cmd", message="=SUM(A1:A10)",
            location="", suggestion="+NA()",
        )
        result = ScanResult(project=proj, findings=[f])
        csv_text = generate_csv_report(result)
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        assert rows[0]["title"] == "'=cmd"
        assert rows[0]["message"] == "'=SUM(A1:A10)"
        assert rows[0]["suggestion"] == "'+NA()"

    def test_deterministic_columns(self):
        proj = Project(path=Path("."), creator="t")
        result1 = generate_csv_report(ScanResult(project=proj, findings=[]))
        result2 = generate_csv_report(ScanResult(project=proj, findings=[]))
        assert result1 == result2

    def test_no_header_option(self):
        proj = Project(path=Path("."), creator="t")
        csv_text = generate_csv_report(ScanResult(project=proj, findings=[]), include_header=False)
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        assert len(rows) == 1  # data row only
        assert rows[0][0] == "unknown"  # first data value, not a header

    def test_empty_optional_fields(self):
        proj = Project(path=Path("."), creator="t")
        f = Finding(severity="info", check_name="test", title="T", message="M",
                    location="", suggestion="", file_path="")
        result = ScanResult(project=proj, findings=[f])
        csv_text = generate_csv_report(result)
        rows = _parse_csv(csv_text)
        assert rows[0]["file_path"] == ""
        assert rows[0]["location"] == ""


# ---------------------------------------------------------------------------
# generate_csv_batch — recursive scan
# ---------------------------------------------------------------------------

class TestGenerateCsvBatch:
    def test_batch_empty(self):
        csv_text = generate_csv_batch([])
        rows = _parse_csv(csv_text)
        assert len(rows) == 0

    def test_batch_one_project_no_findings(self):
        proj = Project(path=Path("/a"), file_path=Path("/a/song.als"), creator="t")
        result = ScanResult(project=proj, findings=[])
        csv_text = generate_csv_batch([(Path("/a"), result, None)])
        rows = _parse_csv(csv_text)
        assert len(rows) == 1
        assert rows[0]["project"] == "a"
        assert rows[0]["severity"] == ""

    def test_batch_one_project_with_findings(self):
        proj = Project(path=Path("/a"), file_path=Path("/a/song.als"), creator="t")
        f = Finding(severity="error", check_name="c", title="T", message="M",
                    location="", suggestion="")
        result = ScanResult(project=proj, findings=[f])
        csv_text = generate_csv_batch([(Path("/a"), result, None)])
        rows = _parse_csv(csv_text)
        assert len(rows) == 1
        assert rows[0]["severity"] == "error"

    def test_batch_multiple_projects(self):
        p1 = Project(path=Path("/a"), file_path=Path("/a/s1.als"), creator="t")
        p2 = Project(path=Path("/b"), file_path=Path("/b/s2.als"), creator="t")
        f1 = Finding(severity="error", check_name="c1", title="T1", message="M1",
                     location="", suggestion="")
        f2 = Finding(severity="warning", check_name="c2", title="T2", message="M2",
                     location="", suggestion="")
        csv_text = generate_csv_batch([
            (Path("/a"), ScanResult(project=p1, findings=[f1]), None),
            (Path("/b"), ScanResult(project=p2, findings=[f2]), None),
        ])
        rows = _parse_csv(csv_text)
        assert len(rows) == 2
        assert {r["project"] for r in rows} == {"a", "b"}

    def test_batch_scan_error(self):
        csv_text = generate_csv_batch([
            (Path("/bad"), None, "Project not found"),
        ])
        rows = _parse_csv(csv_text)
        assert len(rows) == 1
        assert rows[0]["severity"] == "error"
        assert rows[0]["check_name"] == "scan_error"
        assert "Project not found" in rows[0]["message"]

    def test_batch_mixed_success_and_failure(self):
        proj = Project(path=Path("/ok"), file_path=Path("/ok/s.als"), creator="t")
        f = Finding(severity="info", check_name="c", title="T", message="M",
                    location="", suggestion="")
        csv_text = generate_csv_batch([
            (Path("/bad"), None, "Parse error"),
            (Path("/ok"), ScanResult(project=proj, findings=[f]), None),
        ])
        rows = _parse_csv(csv_text)
        assert len(rows) == 2
        severities = {r["severity"] for r in rows}
        assert "error" in severities
        assert "info" in severities

    def test_batch_project_with_no_result(self):
        csv_text = generate_csv_batch([
            (Path("/missing"), None, None),
        ])
        rows = _parse_csv(csv_text)
        assert len(rows) == 1
        assert rows[0]["project"] == "missing"
        assert rows[0]["severity"] == ""


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

def test_cli_scan_csv_format():
    from click.testing import CliRunner
    from alscan.cli import cli
    result = CliRunner().invoke(cli, [
        "scan", str(FIXTURES / "clean.als"), "--format", "csv",
    ])
    assert result.exit_code == 0
    assert "project" in result.output
    assert "severity" in result.output


def test_cli_scan_csv_to_file(tmp_path):
    from click.testing import CliRunner
    from alscan.cli import cli
    dest = tmp_path / "report.csv"
    result = CliRunner().invoke(cli, [
        "scan", str(FIXTURES / "clean.als"), "--format", "csv", "--output", str(dest),
    ])
    assert result.exit_code == 0
    assert dest.exists()
    content = dest.read_text()
    assert "project" in content


def test_cli_list_checks_includes_csv():
    from click.testing import CliRunner
    from alscan.cli import cli
    result = CliRunner().invoke(cli, ["list-checks"])
    assert result.exit_code == 0
    assert "22 checks" in result.output


def test_cli_recursive_csv_format(tmp_path):
    from click.testing import CliRunner
    from alscan.cli import cli
    import shutil
    proj = tmp_path / "test_proj"
    proj.mkdir()
    shutil.copy2(str(FIXTURES / "clean.als"), str(proj / "clean.als"))
    result = CliRunner().invoke(cli, [
        "scan", str(tmp_path), "--recursive", "--format", "csv",
    ])
    assert result.exit_code == 0
    assert "project" in result.output
    assert "severity" in result.output


def test_cli_help_shows_csv_format():
    from click.testing import CliRunner
    from alscan.cli import cli
    result = CliRunner().invoke(cli, ["scan", "--help"])
    assert result.exit_code == 0
    assert "csv" in result.output


# ---------------------------------------------------------------------------
# JSON round-trip consistency
# ---------------------------------------------------------------------------

def test_csv_round_trip():
    """Verify CSV can be parsed back and field values match."""
    proj = Project(path=Path("/test"), file_path=Path("/test/song.als"), creator="t")
    f = Finding(
        severity="warning", check_name="overlapping_notes",
        title="Overlapping MIDI Notes", message="Has 2 overlapping note(s)",
        location="Track: Track > Clip: clip",
        suggestion="Shorten or delete the earlier note.",
    )
    result = ScanResult(project=proj, findings=[f])
    csv_text = generate_csv_report(result)
    rows = _parse_csv(csv_text)
    assert len(rows) == 1
    r = rows[0]
    assert r["project"] == "song"
    assert r["severity"] == "warning"
    assert r["check_name"] == "overlapping_notes"
    assert r["message"] == "Has 2 overlapping note(s)"
    assert r["suggestion"] == "Shorten or delete the earlier note."


# ---------------------------------------------------------------------------
# services.py integration
# ---------------------------------------------------------------------------

def test_render_health_report_csv():
    from alscan.services import render_health_report
    proj = Project(path=Path("."), creator="t")
    f = Finding(severity="error", check_name="test", title="T", message="M",
                location="", suggestion="")
    result = ScanResult(project=proj, findings=[f])
    text = render_health_report(result, "csv")
    assert "project" in text
    assert "error" in text
    assert "test" in text
