# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import gzip
import hashlib
import json
import os
import stat
import threading
from dataclasses import asdict
from pathlib import Path

import pytest
from click.testing import CliRunner

import alscan.cli as cli_module
from alscan.cli import cli
from alscan.io_safety import atomic_write
from alscan.merge.plan import AutoResolved, Conflict, IdentityMatch, LocatorChange, MergePlan, TrackChange
from alscan.merge.report import render_merge_report
from alscan.parser import parse_xml_string
from alscan.versioner import build_snapshot


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
UNRELATED_XML = BASE_XML.replace("Kick", "Completely Different Track").replace('AudioTrack Id="0"', 'MidiTrack Id="99"').replace("</AudioTrack>", "</MidiTrack>")

HOSTILE = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    '"><svg onload=alert(1)>' ,
    "&",
    '"',
    "'",
    "<",
    ">",
]

RUNNER = CliRunner()


def test_merge_report_requires_output_before_analysis(tmp_path):
    base = _write_als(tmp_path, "base.als", BASE_XML)
    ours = _write_als(tmp_path, "ours.als", OURS_XML)
    theirs = _write_als(tmp_path, "theirs.als", THEIRS_XML)
    result = RUNNER.invoke(cli, ["merge-report", str(base), str(ours), str(theirs)])
    assert result.exit_code == 2
    assert "Missing option" in result.output
    assert "<!doctype html>" not in result.output
    assert list(tmp_path.glob("*.html")) == []


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(document_type="wrong"),
    lambda d: d.update(format_version="1"),
    lambda d: d.pop("sources"),
    lambda d: d.update(conflict_count="1"),
    lambda d: d["conflicts"].append({"id": "bad"}),
    lambda d: d["identity_matches"].append({"id": "bad"}),
    lambda d: d["track_changes"].append({"id": "bad"}),
    lambda d: d["locator_changes"].append({"id": "bad"}),
    lambda d: d["proposed_track_order"].append({"track": {}}),
    lambda d: d.update(conflicts=[asdict(Conflict(id="nan", field="tempo", base_value=float("nan")))]),
])
def test_render_merge_report_strictly_validates_v2_mappings(mutate):
    data = _valid_plan_dict()
    mutate(data)
    with pytest.raises(ValueError):
        render_merge_report(data)


def test_render_merge_report_rejects_non_merge_plan_objects():
    with pytest.raises(TypeError):
        render_merge_report(object())  # type: ignore[arg-type]


def test_render_merge_report_escapes_project_controlled_values_recursively():
    payload = " | ".join(HOSTILE)
    plan = _representative_plan(payload)
    html = render_merge_report(plan)
    for raw in ("<script", "</script", "<img", "<svg", "<form", "<iframe"):
        assert raw not in html.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "&quot;&gt;&lt;svg onload=alert(1)&gt;" in html
    assert "nested" in html
    assert "[redacted plugin state]" in html
    assert "raw-secret-blob" not in html


def test_render_merge_report_has_no_external_network_surfaces():
    html = render_merge_report(_representative_plan("Safe"))
    forbidden = [
        "http://", "https://", "//cdn", "//www", "<link", "<script src", "@import",
        "fetch(", "xmlhttprequest", "navigator.sendbeacon", "<meta http-equiv=\"refresh",
        "<form", "tracking", "analytics", "pixel",
    ]
    lower = html.lower()
    for token in forbidden:
        assert token not in lower


def test_render_merge_report_redacts_only_sensitive_fields_and_has_one_privacy_footer():
    plan = _representative_plan("Safe")
    plan.sources["base"]["label"] = r"C:\Users\geoff\Projects\Secret Song\base.als"
    plan.sources["ours"]["label"] = "/home/geoff/projects/secret/ours.als"
    plan.sources["theirs"]["label"] = "/tmp/pytest-of-geoff/theirs.als"
    plan.track_changes[0].name = "Drums/Bass"
    plan.locator_changes[0].name = r"C:\Section"
    plan.conflicts[0].base_value = {"plugin_state": "raw-secret-blob"}
    html = render_merge_report(plan)
    assert "base.als" in html and "ours.als" in html and "theirs.als" in html
    for private in (r"C:\Users", "/home/geoff", "/tmp/pytest", "Secret Song"):
        assert private not in html
    assert "Drums/Bass" in html
    assert r"C:\Section" in html
    assert "[redacted plugin state]" in html
    assert "raw-secret-blob" not in html
    assert html.count("<footer class=\"privacy-footer\">") == 1
    assert html.count("Privacy warning") == 1


def test_render_merge_report_is_deterministic_and_sorts_all_sections():
    plan = _representative_plan("Safe")
    first = render_merge_report(plan)
    second = render_merge_report(plan)
    assert first == second
    assert first.index("tempo - a-conflict") < first.index("track.order - z-conflict")
    assert first.index("exact - Exact") < first.index("plausible - Plausible") < first.index("ambiguous - Ambiguous")
    assert first.index("added - Added") < first.index("removed - Removed")
    assert first.index("moved - Bridge") < first.index("ambiguous - Chorus")
    assert first.index("analysis-only") < first.index("Supported field scope")


def test_render_merge_report_sections_and_safety_wording_are_accurate():
    html = render_merge_report(_representative_plan("Safe"))
    for text in [
        "Conflicts requiring review", "Automatically reconcilable changes", "Track changes", "Locator changes",
        "Identity matches", "Proposed track order (analysis-only)", "Supported field scope",
        "exact - Exact", "plausible - Plausible", "ambiguous - Ambiguous", "unmatched - Unmatched",
        "delete-vs-modify", "track.insertion_position", "locator.movement", "locator.identity",
        "Resolution options only", "Status", "blocked", "review required",
    ]:
        assert text in html
    assert "write .als files" in html
    assert "apply changes" in html
    for unsafe_claim in ("merged .als exists", "conflicts were applied", "full Ableton-project equivalence"):
        assert unsafe_claim not in html


def test_merge_report_cli_exit_codes_and_output_publication(tmp_path):
    base = _write_als(tmp_path, "base.als", BASE_XML)
    unchanged_ours = _write_als(tmp_path, "ours-same.als", BASE_XML)
    unchanged_theirs = _write_als(tmp_path, "theirs-same.als", BASE_XML)
    conflict_ours = _write_als(tmp_path, "ours-conflict.als", OURS_XML)
    conflict_theirs = _write_als(tmp_path, "theirs-conflict.als", THEIRS_XML)

    clean_out = tmp_path / "clean.html"
    result = RUNNER.invoke(cli, ["merge-report", str(base), str(unchanged_ours), str(unchanged_theirs), "--output", str(clean_out)])
    assert result.exit_code == 0, result.output
    assert clean_out.exists() and "<!doctype html>" in clean_out.read_text()

    conflict_out = tmp_path / "conflict.html"
    result = RUNNER.invoke(cli, ["merge-report", "--allow-unrelated", str(base), str(conflict_ours), str(conflict_theirs), "--output", str(conflict_out)])
    assert result.exit_code == 3, result.output
    assert conflict_out.exists() and "Conflicts requiring review" in conflict_out.read_text()


def test_merge_report_cli_validation_failures_create_no_file(tmp_path, monkeypatch):
    base = _write_als(tmp_path, "base.als", BASE_XML)
    ours = _write_als(tmp_path, "ours.als", BASE_XML)
    theirs = _write_als(tmp_path, "theirs.als", BASE_XML)

    malformed = tmp_path / "bad.als"
    malformed.write_text("not gzip")
    _assert_no_output(["merge-report", str(base), str(malformed), str(theirs), "--output", str(tmp_path / "bad.html")], tmp_path / "bad.html", 1)

    bad_snapshot = tmp_path / "bad.json"
    bad_snapshot.write_text("{bad json")
    good_snapshot = _write_snapshot(tmp_path, "snap.json", BASE_XML)
    good_snapshot_2 = _write_snapshot(tmp_path, "snap-2.json", BASE_XML)
    _assert_no_output(["merge-report", str(good_snapshot), str(bad_snapshot), str(good_snapshot_2), "--output", str(tmp_path / "bad-snap.html")], tmp_path / "bad-snap.html", 1)

    _assert_no_output(["merge-report", str(base), str(good_snapshot), str(theirs), "--output", str(tmp_path / "mixed.html")], tmp_path / "mixed.html", 1)
    _assert_no_output(["merge-report", str(base), str(base), str(theirs), "--output", str(tmp_path / "dup.html")], tmp_path / "dup.html", 1)

    existing = tmp_path / "existing.html"
    existing.write_text("original")
    result = RUNNER.invoke(cli, ["merge-report", str(base), str(ours), str(theirs), "--output", str(existing)])
    assert result.exit_code == 1
    assert existing.read_text() == "original"

    for path in (tmp_path / "report.als", tmp_path / ".alscan" / "report.html", tmp_path / "Backup" / "report.html"):
        path.parent.mkdir(exist_ok=True)
        _assert_no_output(["merge-report", str(base), str(ours), str(theirs), "--output", str(path)], path, 1)
    _assert_no_output(["merge-report", str(base), str(ours), str(theirs), "--output", str(base)], base, 1, source=True)

    def denied(dest, content):
        raise PermissionError("denied")
    monkeypatch.setattr(cli_module, "_atomic_write_report", denied)
    denied_out = tmp_path / "denied.html"
    _assert_no_output(["merge-report", str(base), str(ours), str(theirs), "--output", str(denied_out)], denied_out, 1)


def test_merge_report_unrelated_override_controls_publication(tmp_path):
    base = _write_als(tmp_path, "base.als", BASE_XML)
    ours = _write_als(tmp_path, "ours-unrelated.als", UNRELATED_XML)
    theirs = _write_als(tmp_path, "theirs-unrelated.als", UNRELATED_XML.replace("Completely", "Totally"))

    blocked = tmp_path / "blocked.html"
    _assert_no_output(["merge-report", str(base), str(ours), str(theirs), "--output", str(blocked)], blocked, 1)

    allowed = tmp_path / "allowed.html"
    result = RUNNER.invoke(cli, ["merge-report", "--allow-unrelated", str(base), str(ours), str(theirs), "--output", str(allowed)])
    assert result.exit_code in (0, 3), result.output
    assert allowed.exists()


def test_merge_report_rejects_parent_symlink(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not available")
    base = _write_als(tmp_path, "base.als", BASE_XML)
    ours = _write_als(tmp_path, "ours.als", BASE_XML)
    theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
    out = link / "report.html"
    _assert_no_output(["merge-report", str(base), str(ours), str(theirs), "--output", str(out)], out, 1)


def test_merge_report_source_preservation_for_als_and_snapshot_modes(tmp_path, monkeypatch):
    base = _write_als(tmp_path, "base.als", BASE_XML)
    ours = _write_als(tmp_path, "ours.als", OURS_XML)
    theirs = _write_als(tmp_path, "theirs.als", THEIRS_XML)
    _assert_sources_unchanged([base, ours, theirs], ["merge-report", "--allow-unrelated", str(base), str(ours), str(theirs), "--output", str(tmp_path / "als-conflict.html")], 3)

    s_base = _write_snapshot(tmp_path, "base.json", BASE_XML)
    s_ours = _write_snapshot(tmp_path, "ours.json", BASE_XML)
    s_theirs = _write_snapshot(tmp_path, "theirs.json", BASE_XML)
    _assert_sources_unchanged([s_base, s_ours, s_theirs], ["merge-report", str(s_base), str(s_ours), str(s_theirs), "--output", str(tmp_path / "snap.html")], 0)

    existing = tmp_path / "collision.html"
    existing.write_text("original")
    _assert_sources_unchanged([base, ours, theirs], ["merge-report", str(base), str(ours), str(theirs), "--output", str(existing)], 1)

    def denied(dest, content):
        raise PermissionError("denied")
    monkeypatch.setattr(cli_module, "_atomic_write_report", denied)
    _assert_sources_unchanged([base, ours, theirs], ["merge-report", str(base), str(ours), str(theirs), "--output", str(tmp_path / "permission.html")], 1)


def test_merge_report_real_permission_denied_leaves_no_partial_output(tmp_path):
    base = _write_als(tmp_path, "base.als", BASE_XML)
    ours = _write_als(tmp_path, "ours.als", BASE_XML)
    theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
    locked = tmp_path / "locked"
    locked.mkdir()
    out = locked / "report.html"
    locked.chmod(stat.S_IREAD | stat.S_IEXEC)
    try:
        probe = locked / "probe"
        try:
            probe.write_text("probe")
        except OSError:
            pass
        else:
            probe.unlink()
            pytest.skip("filesystem permissions do not block writes here")
        result = RUNNER.invoke(cli, ["merge-report", str(base), str(ours), str(theirs), "--output", str(out)])
        assert result.exit_code == 1
        assert not out.exists()
        assert list(locked.glob(".*.tmp.*")) == []
    finally:
        locked.chmod(stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)


def test_shared_atomic_publication_is_no_clobber_and_cleans_temps(tmp_path):
    dest = tmp_path / "report.html"
    successes = []
    failures = []

    def write(value: str):
        try:
            atomic_write(dest, value)
            successes.append(value)
        except FileExistsError:
            failures.append(value)

    threads = [threading.Thread(target=write, args=(f"content-{i}",)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(successes) == 1
    assert len(failures) == 7
    assert dest.read_text() == successes[0]
    assert list(tmp_path.glob(".*.tmp.*")) == []


def test_readme_merge_report_wording_is_read_only():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "An offline HTML report rendered from the MergePlan v2 document model" in text
    assert "does not apply merges" in text
    assert "modify `.als` files" in text
    assert "--output" in text


def _valid_plan_dict() -> dict:
    plan = MergePlan(
        created_at_utc="2026-07-06T00:00:00Z",
        sources={
            "base": {"label": "base.als", "sha256": "a" * 64, "size": 1},
            "ours": {"label": "ours.als", "sha256": "b" * 64, "size": 1},
            "theirs": {"label": "theirs.als", "sha256": "c" * 64, "size": 1},
        },
        source_structural_fingerprints={"base": "fb", "ours": "fo", "theirs": "ft"},
    )
    return asdict(plan)


def _representative_plan(payload: str) -> MergePlan:
    plan = MergePlan(
        created_at_utc="2026-07-06T00:00:00Z",
        lineage_confidence="weak",
        sources={
            "base": {"label": f"base-{payload}.als", "sha256": "a" * 64, "size": 1},
            "ours": {"label": "ours.als", "sha256": "b" * 64, "size": 1},
            "theirs": {"label": "theirs.als", "sha256": "c" * 64, "size": 1},
        },
        source_structural_fingerprints={"base": "fb", "ours": "fo", "theirs": "ft"},
        warnings=[f"unsupported fields warning {payload}", "weak lineage warning"],
        auto_resolved=[AutoResolved(id="auto-tempo", field="tempo", base_value=120, resolved_value=128, resolution=f"accept ours {payload}", description="auto-resolved scalar change")],
        conflicts=[
            Conflict(id="z-conflict", field="track.order", reason="track-order conflict", available_resolutions=[f"accept_ours {payload}", "accept_theirs"]),
            Conflict(id="a-conflict", field="tempo", base_value={"nested": [payload], "plugin_state": "raw-secret-blob"}, ours_value=128, theirs_value=132, reason=f"conflict reason {payload}", available_resolutions=["retain_base"]),
            Conflict(id="delete-vs-modify", field="track.delete_vs_modify", reason="delete-versus-modify conflict", available_resolutions=["keep_modified", "accept_delete"]),
            Conflict(id="insert", field="track.insertion_position", reason="insertion-position conflict", available_resolutions=["manual_order"]),
            Conflict(id="loc-amb", field="locator.identity", reason="locator ambiguity", available_resolutions=["manual_locator_mapping"]),
            Conflict(id="loc-move", field="locator.movement", reason="locator movement", available_resolutions=["accept_ours"]),
        ],
        identity_matches=[
            IdentityMatch(track_id=1, name="Exact", base_track_id=1, ours_track_id=1, theirs_track_id=1, classification="exact", confidence="exact", evidence=["same_track_id"], auto_resolved=True),
            IdentityMatch(track_id=2, name="Plausible", base_track_id=2, ours_track_id=20, theirs_track_id=21, classification="plausible", confidence="plausible", evidence=[payload], auto_resolved=False),
            IdentityMatch(track_id=3, name="Ambiguous", base_track_id=3, ours_track_id=None, theirs_track_id=None, classification="ambiguous", confidence="ambiguous", evidence=["name_only"], auto_resolved=False),
            IdentityMatch(track_id=4, name="Unmatched", base_track_id=4, ours_track_id=None, theirs_track_id=None, classification="unmatched", confidence="unmatched", evidence=[], auto_resolved=False),
        ],
        track_changes=[
            TrackChange(id="z-removed", kind="removed", branch="ours", track_id=9, base_track_id=9, name="Removed", auto_resolved=False),
            TrackChange(id="a-added", kind="added", branch="ours", branch_track_id=10, name=f"Added {payload}", auto_resolved=False, proposed_position={"after_base_track_id": 1, "before_base_track_id": 2}),
            TrackChange(id="m-modified", kind="modified", branch="theirs", track_id=2, base_track_id=2, branch_track_id=21, name="Modified", auto_resolved=False, details={"requires_review": True}),
        ],
        locator_changes=[
            LocatorChange(id="moved-bridge", kind="moved", name="Bridge", base_time=1, ours_time=2, theirs_time=2, auto_resolved=True),
            LocatorChange(id="amb-chorus", kind="ambiguous", name=f"Chorus {payload}", details={"candidate": payload}),
        ],
        proposed_track_order=[
            {"branch": "ours", "track": {"track_id": 10, "name": payload}, "position": {"after_base_track_id": 1, "before_base_track_id": 2}},
        ],
        file_differences_detected=True,
    )
    plan.conflict_count = len(plan.conflicts)
    plan.warning_count = len(plan.warnings)
    return plan


def _write_als(tmp_path, name: str, xml: str) -> Path:
    path = tmp_path / name
    path.write_bytes(gzip.compress(xml.encode("utf-8")))
    return path


def _write_snapshot(tmp_path, name: str, xml: str) -> Path:
    path = tmp_path / name
    path.write_text(build_snapshot(parse_xml_string(xml)).to_json())
    return path


def _assert_no_output(args: list[str], out: Path, exit_code: int, source: bool = False) -> None:
    before = out.read_bytes() if source and out.exists() else None
    result = RUNNER.invoke(cli, args)
    assert result.exit_code == exit_code, result.output
    if source:
        assert out.read_bytes() == before
    else:
        assert not out.exists()


def _assert_sources_unchanged(paths: list[Path], args: list[str], exit_code: int) -> None:
    before = {path: _sha256(path) for path in paths}
    result = RUNNER.invoke(cli, args)
    assert result.exit_code == exit_code, result.output
    after = {path: _sha256(path) for path in paths}
    assert after == before


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
