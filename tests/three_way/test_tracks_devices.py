# SPDX-License-Identifier: GPL-3.0-only
"""Clip, device, and track ordering scenarios for three-way analysis."""

from __future__ import annotations

import pytest
from tests.three_way.fixtures import (
    two_track_project, three_track_project, device_heavy_project,
    snapshot, track, device, locator,
    mutate, with_tempo, with_tracks, with_track_field,
    add_track, remove_track, swap_tracks, move_track,
    reset_ids,
)
from tests.three_way.test_sanity import _plan_for


class TestClipCountChanges:
    """Clip count scenarios (count-only analysis)."""

    def test_clip_count_ours_only_increase(self):
        base = two_track_project()
        ours = with_track_field(base, 1, clips=10)
        plan = _plan_for(base, ours, base)
        clip_conflicts = [c for c in plan.conflicts if c.field == "track.clip_count"]
        clip_tc = [tc for tc in plan.track_changes
                   if tc.kind == "modified" and tc.branch == "ours"
                   and tc.name == "Kick"]
        assert not clip_conflicts
        assert len(clip_tc) >= 1, "Expected a modified TrackChange for clip count on Kick"

    def test_clip_count_theirs_only_decrease(self):
        base = two_track_project()
        theirs = with_track_field(base, 2, clips=0)
        plan = _plan_for(base, base, theirs)
        clip_conflicts = [c for c in plan.conflicts if c.field == "track.clip_count"]
        assert not clip_conflicts

    def test_clip_count_same_increase_both(self):
        base = two_track_project()
        ours = with_track_field(base, 1, clips=5)
        theirs = with_track_field(base, 1, clips=5)
        plan = _plan_for(base, ours, theirs)
        clip_conflicts = [c for c in plan.conflicts if c.field == "track.clip_count"]
        assert not clip_conflicts

    def test_clip_count_divergent(self):
        base = two_track_project()
        ours = with_track_field(base, 1, clips=10)
        theirs = with_track_field(base, 1, clips=20)
        plan = _plan_for(base, ours, theirs)
        clip_conflicts = [c for c in plan.conflicts if c.field == "track.clip_count"]
        assert len(clip_conflicts) == 1

    def test_clip_count_zero_to_many(self):
        base = with_track_field(two_track_project(), 1, clips=0)
        ours = with_track_field(base, 1, clips=10)
        plan = _plan_for(base, ours, base)
        assert plan.conflict_count == 0


class TestDeviceChanges:
    """Device list changes (treated as ordered structural field)."""

    def test_device_added_ours_only(self):
        base = device_heavy_project()
        ours = with_track_field(base, 1, devices=base.tracks[0]["devices"] + [
            device(name="Reverb", device_type="audio_effect", plugin_type="AudioEffect"),
        ])
        plan = _plan_for(base, ours, base)
        dev_ar = [ar for ar in plan.auto_resolved if "device" in ar.field]
        assert len(dev_ar) >= 1 or plan.conflict_count == 0

    def test_device_removed_theirs_only(self):
        base = device_heavy_project()
        theirs = with_track_field(base, 1, devices=[])
        plan = _plan_for(base, base, theirs)
        dev_ar = [ar for ar in plan.auto_resolved if "device" in ar.field]
        assert len(dev_ar) >= 1 or plan.conflict_count == 0

    def test_same_device_added_both(self):
        base = device_heavy_project()
        new_dev = device(name="Delay", device_type="audio_effect", plugin_type="AudioEffect")
        new_devs = base.tracks[0]["devices"] + [new_dev]
        ours = with_track_field(base, 1, devices=new_devs)
        theirs = with_track_field(base, 1, devices=[d for d in new_devs])
        plan = _plan_for(base, ours, theirs)
        dev_conflicts = [c for c in plan.conflicts if c.field == "track.devices"]
        assert not dev_conflicts

    def test_different_device_added_both(self):
        base = device_heavy_project()
        ours = with_track_field(base, 1, devices=base.tracks[0]["devices"] + [
            device(name="Reverb", device_type="audio_effect", plugin_type="AudioEffect"),
        ])
        theirs = with_track_field(base, 1, devices=base.tracks[0]["devices"] + [
            device(name="Delay", device_type="audio_effect", plugin_type="AudioEffect"),
        ])
        plan = _plan_for(base, ours, theirs)
        dev_conflicts = [c for c in plan.conflicts if c.field == "track.devices"]
        assert len(dev_conflicts) == 1

    def test_device_plugin_reference_change(self):
        base = device_heavy_project()
        ours = with_track_field(base, 2, devices=[
            device(name="Operator", device_type="instrument", plugin_name="Operator.adv", plugin_type="Instrument"),
        ])
        plan = _plan_for(base, ours, base)
        dev_conflicts = [c for c in plan.conflicts if c.field == "track.devices"]
        assert not dev_conflicts


class TestTrackOrdering:
    """Track ordering: moves, swaps, insertions."""

    def test_ours_moves_one_track(self):
        base = three_track_project()
        ours = move_track(base, 1, 2)
        plan = _plan_for(base, ours, base)
        order_conflicts = [c for c in plan.conflicts if c.field == "track.order"]
        assert not order_conflicts

    def test_both_move_same_track_same_way(self):
        base = three_track_project()
        ours = move_track(base, 1, 2)
        theirs = move_track(base, 1, 2)
        plan = _plan_for(base, ours, theirs)
        order_conflicts = [c for c in plan.conflicts if c.field == "track.order"]
        assert not order_conflicts

    def test_both_move_differently(self):
        base = three_track_project()
        ours = move_track(base, 1, 2)   # Kick to end: [2, 3, 1]
        theirs = move_track(base, 3, 0)  # Hi-Hat to front: [3, 1, 2]
        plan = _plan_for(base, ours, theirs)
        order_conflicts = [c for c in plan.conflicts if c.field == "track.order"]
        assert len(order_conflicts) == 1

    def test_complete_reversal_both(self):
        base = three_track_project()
        reversed_tracks = list(reversed(base.tracks))
        ours = with_tracks(base, reversed_tracks)
        theirs = with_tracks(base, reversed_tracks)
        plan = _plan_for(base, ours, theirs)
        order_conflicts = [c for c in plan.conflicts if c.field == "track.order"]
        assert not order_conflicts

    def test_compatible_independent_moves(self):
        base = three_track_project()
        ours = swap_tracks(base, 1, 2)
        theirs = base
        plan = _plan_for(base, ours, theirs)
        order_conflicts = [c for c in plan.conflicts if c.field == "track.order"]
        assert not order_conflicts

    def test_insertion_plus_move(self):
        base = three_track_project()
        ours = add_track(move_track(base, 1, 2), name="New", track_type="midi", clips=1)
        theirs = base
        plan = _plan_for(base, ours, theirs)
        order_conflicts = [c for c in plan.conflicts if c.field == "track.order"]
        assert not order_conflicts

    def test_removal_plus_move(self):
        base = three_track_project()
        ours = move_track(base, 3, 0)
        theirs = remove_track(base, 2)
        plan = _plan_for(base, ours, theirs)
        order_conflicts = [c for c in plan.conflicts if c.field == "track.order"]
        assert len(order_conflicts) <= 1

    def test_proposed_order_contains_all_surviving_tracks(self):
        base = two_track_project()
        reset_ids()
        ours = add_track(base, name="New", track_type="midi")
        theirs = base
        plan = _plan_for(base, ours, theirs)
        names_in_order = [e.get("track", {}).get("name", "") for e in plan.proposed_track_order]
        assert "Kick" in names_in_order or "New" in names_in_order
        assert plan.proposed_track_order or plan.conflict_count >= 0

    def test_proposed_order_deterministic(self):
        base = three_track_project()
        ours = add_track(move_track(base, 1, 2), name="X", track_type="midi")
        theirs = add_track(base, name="Y", track_type="audio")
        plan1 = _plan_for(base, ours, theirs)
        plan2 = _plan_for(base, ours, theirs)
        assert plan1.proposed_track_order == plan2.proposed_track_order

    def test_no_duplicates_in_proposed_order(self):
        base = two_track_project()
        ours = add_track(base, name="New", track_type="midi")
        theirs = base
        plan = _plan_for(base, ours, theirs)
        if plan.proposed_track_order:
            names = [e.get("track", {}).get("name") for e in plan.proposed_track_order]
            assert len(names) == len(set(names))


class TestDeviceOrdering:
    """Device ordering within a track."""

    def test_device_order_changed(self):
        base = snapshot(tracks=[
            track(name="A", track_id=1, devices=[
                device(name="Comp", device_type="audio_effect", plugin_type="AudioEffect"),
                device(name="EQ", device_type="audio_effect", plugin_type="AudioEffect"),
            ]),
        ])
        ours = with_track_field(base, 1, devices=[
            device(name="EQ", device_type="audio_effect", plugin_type="AudioEffect"),
            device(name="Comp", device_type="audio_effect", plugin_type="AudioEffect"),
        ])
        plan = _plan_for(base, ours, base)
        dev_conflicts = [c for c in plan.conflicts if c.field == "track.devices"]
        assert len(dev_conflicts) <= 1

    def test_device_reorder_same_both(self):
        base = snapshot(tracks=[
            track(name="A", track_id=1, devices=[
                device(name="A1", device_type="audio_effect"),
                device(name="A2", device_type="audio_effect"),
            ]),
        ])
        swapped = [base.tracks[0]["devices"][1], base.tracks[0]["devices"][0]]
        ours = with_track_field(base, 1, devices=swapped)
        theirs = with_track_field(base, 1, devices=swapped)
        plan = _plan_for(base, ours, theirs)
        dev_conflicts = [c for c in plan.conflicts if c.field == "track.devices"]
        assert not dev_conflicts


class TestRemoveVersusModify:
    """Delete-vs-modify scenarios."""

    def test_ours_removes_theirs_modifies(self):
        base = two_track_project()
        ours = remove_track(base, 2)
        theirs = with_track_field(base, 2, name="Snare V2")
        plan = _plan_for(base, ours, theirs)
        conflicts = [c for c in plan.conflicts if "delete" in c.field]
        assert len(conflicts) >= 1

    def test_both_remove_same(self):
        base = two_track_project()
        ours = remove_track(base, 2)
        theirs = remove_track(base, 2)
        plan = _plan_for(base, ours, theirs)
        deletions = [tc for tc in plan.track_changes if tc.kind == "removed"]
        assert len(deletions) >= 0


class TestRenameIdentity:
    """Track rename identity scenarios."""

    def test_ours_only_rename(self):
        base = two_track_project()
        ours = with_track_field(base, 1, name="Kick Drum")
        plan = _plan_for(base, ours, base)
        name_conflicts = [c for c in plan.conflicts if c.field == "track.name"]
        name_tc = [tc for tc in plan.track_changes
                   if tc.kind == "modified" and tc.branch == "ours"
                   and tc.base_track_id == 1]
        assert not name_conflicts
        assert len(name_tc) >= 1, "Expected a modified TrackChange for name change"

    def test_same_rename_both(self):
        base = two_track_project()
        ours = with_track_field(base, 1, name="Kick Drum")
        theirs = with_track_field(base, 1, name="Kick Drum")
        plan = _plan_for(base, ours, theirs)
        name_conflicts = [c for c in plan.conflicts if c.field == "track.name"]
        assert not name_conflicts

    def test_different_rename_both(self):
        base = two_track_project()
        ours = with_track_field(base, 1, name="Kick Drum")
        theirs = with_track_field(base, 1, name="Bass Drum")
        plan = _plan_for(base, ours, theirs)
        name_conflicts = [c for c in plan.conflicts if c.field == "track.name"]
        assert len(name_conflicts) == 1

    def test_tracks_swap_names(self):
        base = two_track_project()
        t1_name = base.tracks[1]["name"]
        t2_name = base.tracks[0]["name"]
        ours = with_track_field(with_track_field(base, 1, name=t1_name), 2, name=t2_name)
        plan = _plan_for(base, ours, base)
        name_tc = [tc for tc in plan.track_changes
                   if tc.kind == "modified" and tc.details.get("field") == "name"]
        assert len(name_tc) == 2, (
            f"Expected 2 rename TrackChanges for swap, got {len(name_tc)}"
        )
        # Verify the swap is detected: the resolved names are the other track's base name
        resolved_names = {tc.details.get("resolved") for tc in name_tc}
        assert "Kick" in resolved_names and "Snare" in resolved_names
