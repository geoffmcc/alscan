# SPDX-License-Identifier: GPL-3.0-only
"""Performance tests for three-way merge analysis."""

from __future__ import annotations

import time

import pytest

from tests.three_way.fixtures import (
    large_project, with_tempo, with_time_signature, with_track_field,
    reset_ids,
)
from tests.three_way.test_sanity import _plan_for

PERF_TIMEOUT = 5.0


def _time_analysis(base, ours, theirs) -> float:
    start = time.perf_counter()
    _plan_for(base, ours, theirs)
    return time.perf_counter() - start


class TestPerformanceByTrackCount:
    def test_1_track_performance(self):
        base = large_project(n_tracks=1)
        ours = with_tempo(base, 140.0)
        theirs = with_time_signature(base, 3, 4)
        elapsed = _time_analysis(base, ours, theirs)
        assert elapsed < PERF_TIMEOUT, f"1-track analysis took {elapsed:.2f}s"

    def test_10_track_performance(self):
        base = large_project(n_tracks=10)
        ours = with_tempo(base, 140.0)
        theirs = with_track_field(base, 5, name="Renamed")
        elapsed = _time_analysis(base, ours, theirs)
        assert elapsed < PERF_TIMEOUT, f"10-track analysis took {elapsed:.2f}s"

    def test_50_track_performance(self):
        base = large_project(n_tracks=50)
        ours = add_half_tracks(base)
        theirs = with_tempo(base, 140.0)
        elapsed = _time_analysis(base, ours, theirs)
        assert elapsed < PERF_TIMEOUT, f"50-track analysis took {elapsed:.2f}s"

    def test_100_track_performance(self):
        base = large_project(n_tracks=100)
        ours = with_tempo(base, 140.0)
        theirs = with_tempo(base, 160.0)
        elapsed = _time_analysis(base, ours, theirs)
        assert elapsed < PERF_TIMEOUT, f"100-track analysis took {elapsed:.2f}s"


class TestPerformanceIdenticalLargeProjects:
    def test_identical_50_track_no_op(self):
        base = large_project(n_tracks=50)
        elapsed = _time_analysis(base, base, base)
        assert elapsed < PERF_TIMEOUT, f"50-track no-op analysis took {elapsed:.2f}s"

    def test_identical_100_track_no_op(self):
        base = large_project(n_tracks=100)
        elapsed = _time_analysis(base, base, base)
        assert elapsed < PERF_TIMEOUT, f"100-track no-op analysis took {elapsed:.2f}s"


class TestPerformanceComplexChanges:
    def test_complex_50_track_changes(self):
        base = large_project(n_tracks=50)
        ours = add_quarter_tracks(with_tempo(base, 128.0))
        theirs = rename_half_tracks(with_time_signature(base, 3, 4))
        elapsed = _time_analysis(base, ours, theirs)
        assert elapsed < PERF_TIMEOUT, f"50-track complex analysis took {elapsed:.2f}s"

    def test_complex_100_track_changes(self):
        base = large_project(n_tracks=100)
        ours = with_tempo(base, 128.0)
        theirs = rename_quarter_tracks(with_time_signature(base, 6, 8))
        elapsed = _time_analysis(base, ours, theirs)
        assert elapsed < PERF_TIMEOUT, f"100-track complex analysis took {elapsed:.2f}s"


def add_half_tracks(snap):
    from tests.three_way.fixtures import add_track
    result = snap
    n = len(snap.tracks)
    for i in range(1, max(1, n // 2) + 1):
        result = add_track(result, name=f"Added {i}", track_type="midi", clips=1)
    return result


def add_quarter_tracks(snap):
    from tests.three_way.fixtures import add_track
    result = snap
    n = len(snap.tracks)
    for i in range(1, max(1, n // 4) + 1):
        result = add_track(result, name=f"Qtr {i}", track_type="audio", clips=1)
    return result


def rename_half_tracks(snap):
    tracks = list(snap.tracks)
    for i in range(0, len(tracks), 2):
        tracks[i] = dict(tracks[i])
        tracks[i]["name"] = f"Renamed-{tracks[i].get('name', '')}"
    from tests.three_way.fixtures import with_tracks
    return with_tracks(snap, tracks)


def rename_quarter_tracks(snap):
    tracks = list(snap.tracks)
    for i in range(0, len(tracks), 4):
        tracks[i] = dict(tracks[i])
        tracks[i]["name"] = f"QRenamed-{tracks[i].get('name', '')}"
    from tests.three_way.fixtures import with_tracks
    return with_tracks(snap, tracks)
