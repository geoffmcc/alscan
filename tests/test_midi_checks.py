# SPDX-License-Identifier: GPL-3.0-only
"""Tests for MIDI content health checks."""

from pathlib import Path

import pytest

from alscan.checks import get_check, list_checks
from alscan.models import Clip, Finding, Project, Track

FIXTURES = Path(__file__).parent / "fixtures"


def _make_clip(name="clip", clip_type="midi", duration=4.0, notes=None):
    return Clip(
        name=name, clip_type=clip_type, duration=duration,
        notes=notes if notes is not None else [],
    )


def _make_track(name="Track", track_id=1, track_type="midi", clips=None):
    return Track(
        name=name, track_id=track_id, track_type=track_type,
        clips=clips if clips is not None else [],
    )


def _make_project(tracks=None):
    return Project(
        path=Path("."), creator="test", major_version="12", minor_version="0",
        tracks=tracks if tracks is not None else [],
    )


# ---------------------------------------------------------------------------
# empty_midi_clips
# ---------------------------------------------------------------------------

class TestEmptyMidiClips:
    def test_empty_midi_clip_detected(self):
        track = _make_track(clips=[
            _make_clip(name="Empty MIDI", duration=4.0, notes=[]),
        ])
        proj = _make_project(tracks=[track])
        check = get_check("empty_midi_clips")
        findings = check.func(proj)
        assert len(findings) == 1
        assert findings[0].check_name == "empty_midi_clips"
        assert findings[0].severity == "info"
        assert "Empty MIDI" in findings[0].message
        assert "Track" in findings[0].message

    def test_populated_midi_clip_ignored(self):
        track = _make_track(clips=[
            _make_clip(name="Has Notes", duration=4.0, notes=[
                {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 100},
            ]),
        ])
        proj = _make_project(tracks=[track])
        check = get_check("empty_midi_clips")
        findings = check.func(proj)
        assert len(findings) == 0

    def test_audio_clip_ignored(self):
        track = _make_track(clips=[
            Clip(name="Audio Clip", clip_type="audio", duration=4.0),
        ])
        proj = _make_project(tracks=[track])
        check = get_check("empty_midi_clips")
        findings = check.func(proj)
        assert len(findings) == 0

    def test_zero_duration_midi_clip_ignored(self):
        """Ableton sometimes creates zero-duration placeholder clips — ignore."""
        track = _make_track(clips=[
            _make_clip(name="Zero Duration", clip_type="midi", duration=0.0, notes=[]),
        ])
        proj = _make_project(tracks=[track])
        check = get_check("empty_midi_clips")
        findings = check.func(proj)
        assert len(findings) == 0

    def test_multiple_empty_clips(self):
        track = _make_track(clips=[
            _make_clip(name="Empty 1", duration=4.0, notes=[]),
            _make_clip(name="Populated", duration=2.0, notes=[
                {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 100},
            ]),
            _make_clip(name="Empty 2", duration=8.0, notes=[]),
        ])
        proj = _make_project(tracks=[track])
        check = get_check("empty_midi_clips")
        findings = check.func(proj)
        assert len(findings) == 2
        clip_names = {f.location for f in findings}
        assert len(clip_names) == 2

    def test_unnamed_clip_handled(self):
        track = _make_track(clips=[
            _make_clip(name="", duration=4.0, notes=[]),
        ])
        proj = _make_project(tracks=[track])
        check = get_check("empty_midi_clips")
        findings = check.func(proj)
        assert len(findings) == 1
        assert "(unnamed)" in findings[0].message


# ---------------------------------------------------------------------------
# overlapping_notes
# ---------------------------------------------------------------------------

class TestOverlappingNotes:
    def test_true_overlap_detected(self):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 100},
            {"pitch": 60, "time": 0.5, "duration": 1.0, "velocity": 100},
        ]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert "overlapping" in findings[0].message.lower()
        assert "60" in findings[0].message

    def test_adjacent_notes_not_overlap(self):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 100},
            {"pitch": 60, "time": 1.0, "duration": 1.0, "velocity": 100},
        ]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 0

    def test_different_pitches_not_overlap(self):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 2.0, "velocity": 100},
            {"pitch": 64, "time": 0.5, "duration": 1.0, "velocity": 100},
        ]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 0

    def test_floating_point_tolerance(self):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 100},
            {"pitch": 60, "time": 1.0 + 1e-10, "duration": 1.0, "velocity": 100},
        ]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 0, "Miniscule overlap should be within tolerance"

    def test_clear_overlap_beyond_tolerance(self):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 100},
            {"pitch": 60, "time": 0.99999, "duration": 1.0, "velocity": 100},
        ]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 1

    def test_duplicate_notes_exact_same_time(self):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 100},
            {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 100},
        ]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 1
        assert "overlapping" in findings[0].message.lower()
        assert "60" in findings[0].message

    def test_multiple_pitches_overlap(self):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 2.0, "velocity": 100},
            {"pitch": 60, "time": 1.0, "duration": 2.0, "velocity": 100},
            {"pitch": 64, "time": 0.0, "duration": 2.0, "velocity": 100},
            {"pitch": 64, "time": 1.0, "duration": 2.0, "velocity": 100},
        ]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 1
        msg = findings[0].message
        assert "60" in msg
        assert "64" in msg

    def test_many_pitches_truncated(self):
        notes = []
        for p in range(20):
            notes.append({"pitch": p, "time": 0.0, "duration": 2.0, "velocity": 100})
            notes.append({"pitch": p, "time": 1.0, "duration": 2.0, "velocity": 100})
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 1
        assert "10 more" in findings[0].message

    def test_single_note_no_overlap(self):
        notes = [{"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 100}]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 0

    def test_audio_clip_ignored(self):
        track = _make_track(clips=[
            Clip(name="Audio", clip_type="audio", duration=4.0),
        ])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 0

    def test_empty_notes_ignored(self):
        track = _make_track(clips=[_make_clip(notes=[])])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 0

    def test_three_consecutive_overlaps(self):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 1.5, "velocity": 100},
            {"pitch": 60, "time": 1.0, "duration": 1.5, "velocity": 100},
            {"pitch": 60, "time": 2.0, "duration": 1.5, "velocity": 100},
        ]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 1
        assert "2 overlapping" in findings[0].message  # 2 overlap pairs: (0-1), (1-2)

    def test_large_clip_performance(self):
        notes = []
        for i in range(1000):
            notes.append({"pitch": 60, "time": float(i) * 0.5, "duration": 0.5, "velocity": 100})
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("overlapping_notes")
        findings = check.func(proj)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# extreme_velocity
# ---------------------------------------------------------------------------

class TestExtremeVelocity:
    def test_silent_velocity_zero(self):
        notes = [{"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 0}]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("extreme_velocity")
        findings = check.func(proj)
        assert len(findings) == 1
        assert findings[0].severity == "info"
        assert "velocity 0" in findings[0].message.lower()

    def test_near_silent_velocity(self):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 1},
            {"pitch": 60, "time": 1.0, "duration": 1.0, "velocity": 5},
            {"pitch": 60, "time": 2.0, "duration": 1.0, "velocity": 9},
        ]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("extreme_velocity")
        findings = check.func(proj)
        assert len(findings) == 1
        assert "nearly silent" in findings[0].message.lower()
        assert "3" in findings[0].message

    def test_max_velocity(self):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 127},
        ]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("extreme_velocity")
        findings = check.func(proj)
        assert len(findings) == 1
        assert "maximum" in findings[0].message.lower()

    def test_normal_velocity_ignored(self):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 80},
            {"pitch": 64, "time": 1.0, "duration": 1.0, "velocity": 100},
            {"pitch": 67, "time": 2.0, "duration": 1.0, "velocity": 64},
        ]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("extreme_velocity")
        findings = check.func(proj)
        assert len(findings) == 0

    def test_mixed_velocities(self):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 0},
            {"pitch": 60, "time": 1.0, "duration": 1.0, "velocity": 127},
            {"pitch": 60, "time": 2.0, "duration": 1.0, "velocity": 100},
        ]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("extreme_velocity")
        findings = check.func(proj)
        assert len(findings) == 1
        msg = findings[0].message
        assert "velocity 0" in msg.lower()
        assert "maximum" in msg.lower()

    def test_audio_clip_ignored(self):
        track = _make_track(clips=[
            Clip(name="Audio", clip_type="audio", duration=4.0),
        ])
        proj = _make_project(tracks=[track])
        check = get_check("extreme_velocity")
        findings = check.func(proj)
        assert len(findings) == 0

    def test_empty_notes_ignored(self):
        track = _make_track(clips=[_make_clip(notes=[])])
        proj = _make_project(tracks=[track])
        check = get_check("extreme_velocity")
        findings = check.func(proj)
        assert len(findings) == 0

    def test_velocity_10_boundary(self):
        notes = [{"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 10}]
        track = _make_track(clips=[_make_clip(notes=notes)])
        proj = _make_project(tracks=[track])
        check = get_check("extreme_velocity")
        findings = check.func(proj)
        assert len(findings) == 0, "Velocity 10 is at boundary, should be normal"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_midi_checks_registered():
    checks = list_checks()
    names = {c.name for c in checks}
    assert "empty_midi_clips" in names
    assert "overlapping_notes" in names
    assert "extreme_velocity" in names


# ---------------------------------------------------------------------------
# Fixture integration: clean project should not trigger new checks
# ---------------------------------------------------------------------------

def test_clean_project_no_midi_findings():
    from alscan.parser import parse_als
    proj = parse_als(FIXTURES / "clean.als")
    check_empty = get_check("empty_midi_clips")
    check_overlap = get_check("overlapping_notes")
    check_velocity = get_check("extreme_velocity")
    assert len(check_empty.func(proj)) == 0
    assert len(check_overlap.func(proj)) == 0
    assert len(check_velocity.func(proj)) == 0


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

def test_cli_list_checks_includes_midi():
    from click.testing import CliRunner
    from alscan.cli import cli
    result = CliRunner().invoke(cli, ["list-checks"])
    assert result.exit_code == 0
    assert "empty_midi_clips" in result.output
    assert "overlapping_notes" in result.output
    assert "extreme_velocity" in result.output
    assert "22 checks" in result.output


def test_cli_scan_includes_midi_findings(tmp_path):
    from click.testing import CliRunner
    from alscan.cli import cli
    import shutil
    dest = tmp_path / "test_project"
    dest.mkdir()
    src = FIXTURES / "clean.als"
    shutil.copy2(str(src), str(dest / "clean.als"))
    result = CliRunner().invoke(cli, ["scan", str(dest)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# JSON / HTML output
# ---------------------------------------------------------------------------

def test_json_output_includes_midi_checks():
    from alscan.report.json import generate_json_report
    from alscan.models import ScanResult
    notes = [
        {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 0},
        {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 100},
    ]
    empty_clip = _make_clip(name="Empty", clip_type="midi", duration=4.0, notes=[])
    midi_clip = _make_clip(notes=notes)
    track = _make_track(clips=[empty_clip, midi_clip])
    proj = _make_project(tracks=[track])
    from alscan.checks import list_checks as lc
    findings = []
    for check in lc():
        findings.extend(check.func(proj))
    result = ScanResult(project=proj, findings=findings, scan_time_ms=1.0)
    json_str = generate_json_report(result, pretty=True)
    assert '"check_name": "empty_midi_clips"' in json_str
    assert '"check_name": "extreme_velocity"' in json_str


def test_html_output_includes_midi_checks():
    from alscan.report.html import generate_html_report
    from alscan.models import ScanResult
    notes = [
        {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 0},
        {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 100},
    ]
    empty_clip = _make_clip(name="Empty", clip_type="midi", duration=4.0, notes=[])
    midi_clip = _make_clip(notes=notes)
    track = _make_track(clips=[empty_clip, midi_clip])
    proj = _make_project(tracks=[track])
    from alscan.checks import list_checks as lc
    findings = []
    for check in lc():
        findings.extend(check.func(proj))
    result = ScanResult(project=proj, findings=findings, scan_time_ms=1.0)
    html = generate_html_report(result)
    assert "empty_midi_clips" in html
    assert "extreme_velocity" in html
