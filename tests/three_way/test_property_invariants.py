# SPDX-License-Identifier: GPL-3.0-only
"""Property invariants for three-way merge analysis."""

from __future__ import annotations

import json

import pytest

from tests.three_way.fixtures import (
    two_track_project, three_track_project,
    device_heavy_project, locator_project,
    with_tempo, with_time_signature, with_track_field,
    add_track, remove_track, add_locator, move_locator, remove_locator,
    reset_ids,
)
from tests.three_way.test_sanity import _plan_for


class TestIdentityNoChanges:
    """analyze(Base, Base, Base) has no changes/conflicts."""

    def test_no_changes_identical_triple(self):
        base = two_track_project()
        plan = _plan_for(base, base, base)
        assert plan.conflict_count == 0
        assert not plan.auto_resolved
        assert not plan.track_changes

    def test_no_changes_device_heavy(self):
        base = device_heavy_project()
        plan = _plan_for(base, base, base)
        assert plan.conflict_count == 0

    def test_no_changes_locator_project(self):
        base = locator_project()
        plan = _plan_for(base, base, base)
        assert plan.conflict_count == 0

    def test_no_changes_empty_project(self):
        reset_ids()
        from tests.three_way.fixtures import snapshot
        base = snapshot(tempo=140.0, tracks=[], locators=[])
        plan = _plan_for(base, base, base)
        assert plan.conflict_count == 0


class TestOursOnlyNoTheirsAttribution:
    """analyze(Base, Modified, Base) attributes nothing to Theirs."""

    def test_tempo_change_no_theirs_attribution(self):
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        plan = _plan_for(base, ours, base)
        ar_theirs = [ar for ar in plan.auto_resolved if ar.resolution == "accept_theirs"]
        assert not ar_theirs

    def test_time_sig_change_no_theirs_attribution(self):
        base = two_track_project()
        ours = with_time_signature(base, 3, 4)
        plan = _plan_for(base, ours, base)
        ar_theirs = [ar for ar in plan.auto_resolved if ar.resolution == "accept_theirs"]
        assert not ar_theirs

    def test_track_addition_no_theirs_attribution(self):
        base = two_track_project()
        ours = add_track(base, name="Bass", track_type="midi", clips=1)
        plan = _plan_for(base, ours, base)
        theirs_additions = [tc for tc in plan.track_changes if tc.kind == "added" and tc.branch == "theirs"]
        assert not theirs_additions

    def test_track_field_change_no_theirs_attribution(self):
        base = two_track_project()
        ours = with_track_field(base, 1, name="New Name")
        plan = _plan_for(base, ours, base)
        theirs_tc = [tc for tc in plan.track_changes if tc.branch == "theirs"]
        assert not theirs_tc


class TestConvergentNoConflict:
    """analyze(Base, Modified, Modified) for identical changes does not conflict."""

    def test_identical_tempo_change_no_conflict(self):
        base = two_track_project()
        ours = with_tempo(base, 140.0)
        theirs = with_tempo(base, 140.0)
        plan = _plan_for(base, ours, theirs)
        assert plan.conflict_count == 0

    def test_identical_time_sig_change_no_conflict(self):
        base = two_track_project()
        ours = with_time_signature(base, 6, 8)
        theirs = with_time_signature(base, 6, 8)
        plan = _plan_for(base, ours, theirs)
        assert plan.conflict_count == 0

    def test_identical_track_field_change_no_conflict(self):
        base = two_track_project()
        ours = with_track_field(base, 1, name="Renamed", volume=0.5)
        theirs = with_track_field(base, 1, name="Renamed", volume=0.5)
        plan = _plan_for(base, ours, theirs)
        assert plan.conflict_count == 0

    def test_identical_device_change_no_conflict(self):
        base = device_heavy_project()
        from tests.three_way.fixtures import device
        ours = with_track_field(base, 1, devices=[
            device(name="Comp", device_type="audio_effect", plugin_type="AudioEffect"),
            device(name="EQ Eight", device_type="audio_effect", plugin_type="AudioEffect"),
            device(name="Reverb", device_type="audio_effect", plugin_type="AudioEffect"),
        ])
        theirs = with_track_field(base, 1, devices=[
            device(name="Comp", device_type="audio_effect", plugin_type="AudioEffect"),
            device(name="EQ Eight", device_type="audio_effect", plugin_type="AudioEffect"),
            device(name="Reverb", device_type="audio_effect", plugin_type="AudioEffect"),
        ])
        plan = _plan_for(base, ours, theirs)
        dev_conflicts = [c for c in plan.conflicts if c.field == "track.devices"]
        assert not dev_conflicts

    def test_identical_locator_move_no_conflict(self):
        base = locator_project()
        ours = move_locator(base, "Intro", 5.0)
        theirs = move_locator(base, "Intro", 5.0)
        plan = _plan_for(base, ours, theirs)
        assert plan.conflict_count == 0


class TestSwapSymmetry:
    """Swap Ours/Theirs preserves conflict count."""

    def test_swap_tempo_conflict_same_count(self):
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        theirs = with_tempo(base, 132.0)
        plan_fwd = _plan_for(base, ours, theirs)
        plan_swapped = _plan_for(base, theirs, ours)
        assert plan_fwd.conflict_count == plan_swapped.conflict_count

    def test_swap_complex_same_count(self):
        base = three_track_project()
        ours = add_track(with_tempo(base, 128.0), name="Bass", track_type="midi", clips=1)
        theirs = remove_track(with_time_signature(base, 3, 4), 3)
        plan_fwd = _plan_for(base, ours, theirs)
        plan_swapped = _plan_for(base, theirs, ours)
        assert plan_fwd.conflict_count == plan_swapped.conflict_count

    def test_swap_locator_conflict_same_count(self):
        base = locator_project()
        ours = add_locator(move_locator(base, "Intro", 5.0), "Drop", 41.0)
        theirs = move_locator(base, "Chorus", 20.0)
        plan_fwd = _plan_for(base, ours, theirs)
        plan_swapped = _plan_for(base, theirs, ours)
        assert plan_fwd.conflict_count == plan_swapped.conflict_count

    def test_swap_single_branch_change_no_conflict(self):
        base = two_track_project()
        ours = with_tempo(base, 100.0)
        plan_fwd = _plan_for(base, ours, base)
        plan_swapped = _plan_for(base, base, ours)
        assert plan_fwd.conflict_count == plan_swapped.conflict_count
        assert plan_fwd.warning_count == plan_swapped.warning_count


class TestDeterminism:
    """Repeated analysis is deterministic."""

    def test_identical_plan_json(self):
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        theirs = with_tempo(base, 132.0)
        plan1 = _plan_for(base, ours, theirs)
        plan2 = _plan_for(base, ours, theirs)
        assert json.loads(plan1.to_json()) == json.loads(plan2.to_json())

    def test_deterministic_with_track_changes(self):
        base = three_track_project()
        ours = add_track(with_tempo(base, 140.0), name="Pad", track_type="midi", clips=1)
        theirs = remove_track(with_time_signature(base, 6, 8), 2)
        plan1 = _plan_for(base, ours, theirs)
        plan2 = _plan_for(base, ours, theirs)
        assert json.loads(plan1.to_json()) == json.loads(plan2.to_json())

    def test_deterministic_with_locators(self):
        base = locator_project()
        ours = move_locator(add_locator(base, "Bridge", 33.0), "Intro", 5.0)
        theirs = remove_locator(base, "Outro")
        plan1 = _plan_for(base, ours, theirs)
        plan2 = _plan_for(base, ours, theirs)
        assert json.loads(plan1.to_json()) == json.loads(plan2.to_json())

    def test_deterministic_device_heavy(self):
        base = device_heavy_project()
        from tests.three_way.fixtures import device
        ours = with_track_field(base, 1, devices=[
            device(name="Saturator", device_type="audio_effect", plugin_type="AudioEffect"),
        ])
        theirs = with_track_field(base, 2, name="Sub Bass")
        plan1 = _plan_for(base, ours, theirs)
        plan2 = _plan_for(base, ours, theirs)
        assert json.loads(plan1.to_json()) == json.loads(plan2.to_json())


class TestProposedOrderNoDuplicates:
    """Proposed order contains no duplicate track references."""

    def test_no_duplicate_track_ids_in_order(self):
        base = three_track_project()
        ours = add_track(base, name="Extra", track_type="audio", clips=1)
        plan = _plan_for(base, ours, base)
        track_ids = [
            e.get("track", {}).get("track_id")
            for e in plan.proposed_track_order
            if e.get("track", {}).get("track_id") is not None
        ]
        assert len(track_ids) == len(set(track_ids))

    def test_no_duplicates_complex_ordering(self):
        base = three_track_project()
        ours = add_track(base, name="A", track_type="audio", clips=1)
        theirs = add_track(base, name="B", track_type="midi", clips=2)
        plan = _plan_for(base, ours, theirs)
        track_ids = [
            e.get("track", {}).get("track_id")
            for e in plan.proposed_track_order
            if e.get("track", {}).get("track_id") is not None
        ]
        assert len(track_ids) == len(set(track_ids))

    def test_no_order_duplicates_unchanged(self):
        base = two_track_project()
        plan = _plan_for(base, base, base)
        track_ids = [
            e.get("track", {}).get("track_id")
            for e in plan.proposed_track_order
            if e.get("track", {}).get("track_id") is not None
        ]
        assert len(track_ids) == len(set(track_ids))


class TestInputBytesUnchanged:
    """Input bytes remain unchanged for file-based tests (snapshot mode)."""

    def test_snapshots_unmodified_by_analysis(self):
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        theirs = with_tempo(base, 132.0)
        base_json = base.to_json()
        ours_json = ours.to_json()
        theirs_json = theirs.to_json()
        _plan_for(base, ours, theirs)
        assert base.to_json() == base_json
        assert ours.to_json() == ours_json
        assert theirs.to_json() == theirs_json

    def test_mutated_snapshot_serialization_stable(self):
        base = locator_project()
        ours = add_locator(base, "Drop", 41.0)
        base_json = base.to_json()
        ours_json = ours.to_json()
        _plan_for(base, ours, base)
        assert base.to_json() == base_json
        assert ours.to_json() == ours_json
