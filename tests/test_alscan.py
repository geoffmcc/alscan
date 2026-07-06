"""Tests for alscan — Ableton Live project parser and health checks."""

from pathlib import Path

import pytest

from alscan.parser import parse_als
from alscan.models import Track, Clip, Device, PluginRef, SampleRef, Project, Finding
from alscan.checks import list_checks, get_check

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_clean():
    """Clean project parses with no issues."""
    proj = parse_als(FIXTURES / "clean.als")
    assert len(proj.tracks) == 2
    assert all(t.track_type in ("midi",) for t in proj.tracks)


def test_parse_all_checks():
    """all_checks.als parses all 15 tracks correctly."""
    proj = parse_als(FIXTURES / "all_checks.als")
    assert len(proj.tracks) == 15
    types = {t.track_type for t in proj.tracks}
    assert types == {"audio", "midi", "group", "return", "master"}


def test_parse_frozen_returns():
    """frozen_returns.als — return track with clips."""
    proj = parse_als(FIXTURES / "frozen_returns.als")
    assert len(proj.tracks) == 2
    assert proj.tracks[1].track_type == "return"
    assert len(proj.tracks[1].clips) == 1


def test_clean_project_has_no_findings():
    """Clean project triggers zero findings."""
    proj = parse_als(FIXTURES / "clean.als")
    findings = []
    for check in list_checks():
        findings.extend(check.func(proj))
    assert len(findings) == 0


def test_frozen_returns_project_has_no_findings():
    """Return track with clips should not trigger unused_returns."""
    proj = parse_als(FIXTURES / "frozen_returns.als")
    findings = []
    for check in list_checks():
        findings.extend(check.func(proj))
    unused = [f for f in findings if f.check_name == "unused_returns"]
    assert len(unused) == 0


def test_all_checks_triggered():
    """all_checks.als triggers all 19 check types at least once."""
    proj = parse_als(FIXTURES / "all_checks.als")
    findings = []
    for check in list_checks():
        findings.extend(check.func(proj))
    triggered = {f.check_name for f in findings}
    expected = {
        "missing_samples", "missing_pack_samples",
        "broken_plugins", "frozen_plugins",
        "frozen_tracks", "high_device_count",
        "cpu_heavy_plugins", "high_latency_plugins",
        "unfrozen_heavy_tracks",
        "empty_tracks", "unused_returns", "empty_groups",
        "unnamed_tracks", "duplicate_track_names",
        "duplicate_samples",
        "warped_clips", "master_chain_plugins",
        "extreme_tempo", "no_locators",
    }
    missing = expected - triggered
    extra = triggered - expected
    assert not missing, f"Checks not triggered: {missing}"
    assert not extra, f"Unexpected checks triggered: {extra}"


# -- Individual check tests --

def test_missing_samples_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("missing_samples")
    findings = check.func(proj)
    assert len(findings) > 0
    assert all(f.severity == "error" for f in findings)


def test_broken_plugins_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("broken_plugins")
    findings = check.func(proj)
    assert len(findings) > 0
    assert any(f.severity == "error" for f in findings)


def test_frozen_plugins_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("frozen_plugins")
    findings = check.func(proj)
    assert len(findings) == 1
    assert "Frozen Synth" in findings[0].message


def test_frozen_tracks_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("frozen_tracks")
    findings = check.func(proj)
    assert len(findings) == 1
    assert findings[0].severity == "warning"


def test_high_device_count_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("high_device_count")
    findings = check.func(proj)
    assert len(findings) == 1
    assert "Device Hell" in findings[0].message
    assert "10" in findings[0].message  # 10 devices > threshold of 8


def test_cpu_heavy_plugins_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("cpu_heavy_plugins")
    findings = check.func(proj)
    # Serum, Ozone, Kontakt (3 heavy plugins on Heavy Track + others)
    heavy_names = {f.check_name for f in findings}
    assert len(findings) >= 1


def test_high_latency_plugins_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("high_latency_plugins")
    findings = check.func(proj)
    assert len(findings) == 1  # Ozone is the only high-latency one
    assert "Ozone" in findings[0].message


def test_unfrozen_heavy_tracks_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("unfrozen_heavy_tracks")
    findings = check.func(proj)
    assert len(findings) == 1
    assert "Heavy Track" in findings[0].message


def test_empty_tracks_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("empty_tracks")
    findings = check.func(proj)
    # Empty Track (id=0), unnamed (id=1), Device Hell (no clips), Empty Group,
    # Unused Reverb (return — excluded by check), Pack Track (has clips)
    assert len(findings) == 5
    assert all(f.severity == "info" for f in findings)


def test_unused_returns_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("unused_returns")
    findings = check.func(proj)
    assert len(findings) == 1  # Unused Reverb only
    assert "Unused Reverb" in findings[0].message


def test_empty_groups_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("empty_groups")
    findings = check.func(proj)
    assert len(findings) == 1
    assert "Empty Group" in findings[0].message


def test_unnamed_tracks_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("unnamed_tracks")
    findings = check.func(proj)
    assert len(findings) == 1
    assert "Track #1" in findings[0].location


def test_duplicate_track_names_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("duplicate_track_names")
    findings = check.func(proj)
    assert len(findings) == 1
    assert "Audio 1" in findings[0].message


def test_duplicate_samples_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("duplicate_samples")
    findings = check.func(proj)
    assert len(findings) >= 1
    assert all(f.severity == "info" for f in findings)


def test_missing_pack_samples_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("missing_pack_samples")
    findings = check.func(proj)
    assert len(findings) == 1
    assert "Pack" in findings[0].message


# -- New v0.2 check tests --

def test_warped_clips_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("warped_clips")
    findings = check.func(proj)
    assert len(findings) > 0
    assert all(f.severity == "info" for f in findings)


def test_master_chain_plugins_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("master_chain_plugins")
    findings = check.func(proj)
    assert len(findings) > 0
    assert findings[0].severity == "info"


def test_extreme_tempo_check():
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("extreme_tempo")
    findings = check.func(proj)
    assert len(findings) > 0
    assert findings[0].severity == "info"


def test_no_locators_check():
    """project with >5 tracks and no locators triggers this check."""
    proj = parse_als(FIXTURES / "all_checks.als")
    check = get_check("no_locators")
    findings = check.func(proj)
    assert len(findings) > 0
    assert findings[0].severity == "info"


def test_list_checks_returns_all():
    checks = list_checks()
    names = {c.name for c in checks}
    expected = {
        "missing_samples", "missing_pack_samples",
        "broken_plugins", "frozen_plugins",
        "frozen_tracks", "high_device_count",
        "cpu_heavy_plugins", "high_latency_plugins",
        "unfrozen_heavy_tracks",
        "empty_tracks", "unused_returns", "empty_groups",
        "unnamed_tracks", "duplicate_track_names",
        "duplicate_samples",
    }
    expected_all = expected | {
        "warped_clips", "master_chain_plugins",
        "extreme_tempo", "no_locators",
    }
    assert names == expected_all


# -- Model tests --

def test_sample_ref_exists_returns_false_for_bad_path():
    ref = SampleRef(name="test", path="Z:/does/not/exist.wav")
    assert not ref.exists()


def test_sample_ref_resolved_path_returns_none_for_bad():
    ref = SampleRef(name="test", path="Z:/does/not/exist.wav")
    assert ref.resolved_path() is None


def test_plugin_ref_exists_returns_true_for_builtin():
    ref = PluginRef(name="Serum", plugin_type="vst2", is_builtin=True)
    assert ref.exists()


def test_plugin_ref_exists_returns_false_for_bad_path():
    ref = PluginRef(name="Test", plugin_type="vst2", path="Z:/VST/test.dll")
    assert not ref.exists()


def test_scan_result_properties():
    from alscan.models import ScanResult, Project
    proj = Project(path=Path("."))
    result = ScanResult(project=proj, findings=[
        Finding(severity="error", check_name="test", title="E", message="Error"),
        Finding(severity="warning", check_name="test", title="W", message="Warning"),
        Finding(severity="info", check_name="test", title="I", message="Info"),
        Finding(severity="suggestion", check_name="test", title="S", message="Suggestion"),
    ])
    assert len(result.errors) == 1
    assert len(result.warnings) == 1
    assert len(result.info) == 1
    assert len(result.suggestions) == 1


def test_finding_dict():
    f = Finding(severity="error", check_name="test", title="Test", message="Something")
    d = f.dict()
    assert d["severity"] == "error"
    assert d["check_name"] == "test"


def test_parse_xml_string():
    """parse_xml_string works without a real file path."""
    from alscan.parser import parse_xml_string
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12" Creator="Ableton Live 12">
  <LiveSet>
    <Tempo><Manual Value="140"/></Tempo>
    <TimeSignature>
      <TimeSignatures>
        <RemoteableTimeSignature>
          <Numerator Value="3"/><Denominator Value="4"/>
        </RemoteableTimeSignature>
      </TimeSignatures>
    </TimeSignature>
    <Locators><Locators/></Locators>
    <Tracks>
      <MidiTrack Id="0">
        <Name><EffectiveName Value="Test Track"/></Name>
        <ColorIndex Value="1"/>
        <DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain>
      </MidiTrack>
    </Tracks>
  </LiveSet>
</Ableton>"""
    proj = parse_xml_string(xml)
    assert proj.tempo == 140.0
    assert proj.time_signature == (3, 4)
    assert len(proj.tracks) == 1
    assert proj.tracks[0].name == "Test Track"


def test_parse_als_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_als("Z:/does/not/exist.als")


# -- Versioning tests (v0.3) --

def test_build_snapshot():
    from alscan.versioner import build_snapshot
    proj = parse_als(FIXTURES / "clean.als")
    snap = build_snapshot(proj)
    assert snap.project_name == "clean"
    assert snap.tempo == 120.0
    assert snap.track_count == 2
    assert snap.device_count == 0


def test_snapshot_round_trip():
    from alscan.versioner import build_snapshot, Snapshot
    proj = parse_als(FIXTURES / "clean.als")
    snap = build_snapshot(proj)
    js = snap.to_json()
    restored = Snapshot.from_json(js)
    assert restored.project_name == "clean"
    assert restored.tempo == 120.0
    assert restored.track_count == 2


def test_snapshot_has_consistent_fingerprint():
    from alscan.versioner import build_snapshot
    proj = parse_als(FIXTURES / "clean.als")
    snap = build_snapshot(proj)
    assert len(snap.structural_fingerprint) == 16
    assert all(c in "0123456789abcdef" for c in snap.structural_fingerprint)


def test_save_and_find_snapshots(tmp_path):
    from alscan.versioner import build_snapshot, save_snapshot, find_snapshots, load_snapshot
    proj = parse_als(FIXTURES / "clean.als")
    p1 = save_snapshot(proj, tmp_path)
    assert p1.exists()
    assert p1.suffix == ".json"
    assert p1.parent.name == "snapshots"
    snaps = find_snapshots(tmp_path)
    assert len(snaps) == 1
    loaded = load_snapshot(snaps[0])
    assert loaded.tempo == 120.0


def test_diff_same_project_no_changes():
    from alscan.versioner import build_snapshot, diff_snapshots
    proj_a = parse_als(FIXTURES / "clean.als")
    proj_b = parse_als(FIXTURES / "clean.als")
    snap_a = build_snapshot(proj_a)
    snap_b = build_snapshot(proj_b)
    result = diff_snapshots(snap_a, snap_b)
    assert not result.has_changes


def test_diff_different_projects():
    from alscan.versioner import build_snapshot, diff_snapshots
    clean = build_snapshot(parse_als(FIXTURES / "clean.als"))
    all_chk = build_snapshot(parse_als(FIXTURES / "all_checks.als"))
    result = diff_snapshots(clean, all_chk)
    assert result.has_changes
    assert result.tempo_changed
    assert result.tempo_before == 120.0
    assert result.tempo_after == 250.0
    assert len(result.track_changes) > 0


# -- Versioning schema / validation tests --

def test_snapshot_from_json_validates_format_version():
    from alscan.versioner import Snapshot, SNAPSHOT_FORMAT_VERSION
    data = '{"format_version":"0","project_name":"x","timestamp":1.0,"structural_fingerprint":"abc","creator":"","major_version":"","minor_version":"","tempo":120.0,"time_signature":[4,4],"tracks":[],"locators":[]}'
    with pytest.raises(ValueError, match="Unsupported snapshot format version"):
        Snapshot.from_json(data)


def test_snapshot_from_json_rejects_missing_fields():
    from alscan.versioner import Snapshot
    with pytest.raises(ValueError, match="Snapshot missing required fields"):
        Snapshot.from_json('{"format_version":"1"}')


def test_snapshot_from_json_rejects_extra_fields():
    from alscan.versioner import Snapshot
    data = '{"format_version":"1","project_name":"x","timestamp":1.0,"structural_fingerprint":"abc","creator":"","major_version":"","minor_version":"","tempo":120.0,"time_signature":[4,4],"tracks":[],"locators":[],"extra":"bad"}'
    with pytest.raises(ValueError, match="has unknown fields"):
        Snapshot.from_json(data)


def test_snapshot_from_json_rejects_type_mismatch():
    from alscan.versioner import Snapshot
    data = '{"format_version":"1","project_name":"x","timestamp":"not_a_number","structural_fingerprint":"abc","creator":"","major_version":"","minor_version":"","tempo":120.0,"time_signature":[4,4],"tracks":[],"locators":[]}'
    with pytest.raises(TypeError, match="expected.*got str"):
        Snapshot.from_json(data)


def test_snapshot_filename_includes_uuid(tmp_path):
    from alscan.versioner import build_snapshot, save_snapshot
    proj = parse_als(FIXTURES / "clean.als")
    p1 = save_snapshot(proj, tmp_path)
    parts = p1.stem.split("-")
    assert len(parts) >= 3
    assert len(parts[-1]) == 12


def test_save_snapshot_is_not_overwritten(tmp_path):
    from alscan.versioner import build_snapshot, save_snapshot
    proj = parse_als(FIXTURES / "clean.als")
    p1 = save_snapshot(proj, tmp_path)
    p2 = save_snapshot(proj, tmp_path)
    assert p1.name != p2.name


def test_find_snapshots_ignores_corrupt_files(tmp_path):
    from alscan.versioner import save_snapshot, find_snapshots
    proj = parse_als(FIXTURES / "clean.als")
    save_snapshot(proj, tmp_path)
    bad = tmp_path / ".alscan" / "snapshots" / "corrupt.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("not valid json")
    snaps = find_snapshots(tmp_path)
    # Should still find the valid one, ignore corrupt
    assert len(snaps) == 1


def test_find_snapshots_chronological_order(tmp_path):
    from alscan.versioner import build_snapshot, save_snapshot, find_snapshots
    proj = parse_als(FIXTURES / "clean.als")
    p1 = save_snapshot(proj, tmp_path)
    import time as ttime
    ttime.sleep(0.01)
    p2 = save_snapshot(proj, tmp_path)
    snaps = find_snapshots(tmp_path)
    # Most recent first
    assert snaps[0].name == p2.name
    assert snaps[1].name == p1.name


def test_diff_track_added():
    from alscan.versioner import build_snapshot, diff_snapshots
    clean = build_snapshot(parse_als(FIXTURES / "clean.als"))
    all_chk = build_snapshot(parse_als(FIXTURES / "all_checks.als"))
    result = diff_snapshots(clean, all_chk)
    added = [t for t in result.track_changes if t.kind == "added"]
    assert len(added) > 0
    assert any(t.name == "Warped Track" for t in added)


# -- Report output / atomic write tests --

def test_atomic_write_report_concurrent_writers(tmp_path):
    """Verify atomic no-clobber: exactly one of N concurrent writers succeeds."""
    from concurrent.futures import ThreadPoolExecutor
    from alscan.cli import _atomic_write_report

    dest = tmp_path / "report.html"
    num_writers = 10

    def writer(worker_id: int) -> bool:
        content = f"Report from worker {worker_id}"
        try:
            _atomic_write_report(dest, content)
            return True
        except FileExistsError:
            return False

    with ThreadPoolExecutor(max_workers=num_writers) as pool:
        results = list(pool.map(writer, range(num_writers)))

    success_count = sum(results)
    assert success_count == 1, f"Expected 1 writer to succeed, got {success_count}"

    assert dest.exists(), "Destination file was not created"
    content = dest.read_text()
    assert content.startswith("Report from worker "), f"Unexpected content: {content}"
    worker_id = content.replace("Report from worker ", "").strip()
    assert worker_id.isdigit()

    stale = list(tmp_path.glob(".*.tmp.*"))
    assert len(stale) == 0, f"Stale temporary files remain: {stale}"


def test_atomic_write_report_existing_fails(tmp_path):
    """Writing to an existing destination raises FileExistsError."""
    from alscan.cli import _atomic_write_report
    dest = tmp_path / "report.html"
    dest.write_text("original content")
    with pytest.raises(FileExistsError):
        _atomic_write_report(dest, "new content")
    assert dest.read_text() == "original content"


def test_atomic_write_report_creates_parent_dirs(tmp_path):
    """Parent directories are created automatically."""
    from alscan.cli import _atomic_write_report
    dest = tmp_path / "sub" / "nested" / "report.html"
    _atomic_write_report(dest, "hello")
    assert dest.read_text() == "hello"
    stale = list(tmp_path.glob("**/.*.tmp.*"))
    assert len(stale) == 0
