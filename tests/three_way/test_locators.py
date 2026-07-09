# SPDX-License-Identifier: GPL-3.0-only
"""Locator scenarios for three-way merge analysis."""

from __future__ import annotations

import pytest

from tests.three_way.fixtures import (
    locator_project,
    add_locator,
    remove_locator,
    move_locator,
    reset_ids,
)
from tests.three_way.test_sanity import _plan_for


class TestLocatorUnchanged:
    def test_all_identical_locators_unchanged(self):
        base = locator_project()
        plan = _plan_for(base, base, base)
        assert plan.conflict_count == 0
        changed = [lc for lc in plan.locator_changes if lc.kind != "unchanged"]
        assert not changed

    def test_no_locators_in_any(self):
        reset_ids()
        from tests.three_way.fixtures import snapshot
        base = snapshot(tempo=120.0, tracks=[])
        plan = _plan_for(base, base, base)
        assert not plan.locator_changes


class TestLocatorOursOnlyMove:
    def test_ours_only_move(self):
        base = locator_project()
        ours = move_locator(base, "Intro", 5.0)
        plan = _plan_for(base, ours, base)
        assert plan.conflict_count == 0
        moved = [lc for lc in plan.locator_changes if lc.kind == "moved"]
        assert len(moved) == 1
        assert moved[0].branch == "ours"
        assert moved[0].name == "Intro"
        assert moved[0].base_time == 1.0
        assert moved[0].ours_time == 5.0

    def test_theirs_only_move(self):
        base = locator_project()
        theirs = move_locator(base, "Chorus", 25.0)
        plan = _plan_for(base, base, theirs)
        assert plan.conflict_count == 0
        moved = [lc for lc in plan.locator_changes if lc.kind == "moved"]
        assert len(moved) == 1
        assert moved[0].branch == "theirs"
        assert moved[0].name == "Chorus"
        assert moved[0].theirs_time == 25.0


class TestLocatorBothMoveIdentically:
    def test_both_move_identically(self):
        base = locator_project()
        ours = move_locator(base, "Verse", 12.0)
        theirs = move_locator(base, "Verse", 12.0)
        plan = _plan_for(base, ours, theirs)
        assert plan.conflict_count == 0
        moved = [lc for lc in plan.locator_changes if lc.kind == "moved"]
        assert len(moved) >= 1
        both = [lc for lc in moved if lc.name == "Verse" and lc.branch == "both"]
        assert len(both) == 1


class TestLocatorBothMoveDifferently:
    def test_both_move_differently(self):
        base = locator_project()
        ours = move_locator(base, "Intro", 3.0)
        theirs = move_locator(base, "Intro", 7.0)
        plan = _plan_for(base, ours, theirs)
        assert plan.conflict_count >= 1
        conflicts = [c for c in plan.conflicts if c.field == "locator.movement"]
        assert len(conflicts) == 1
        assert conflicts[0].ours_value == 3.0
        assert conflicts[0].theirs_value == 7.0


class TestLocatorOneSidedRemoval:
    def test_ours_only_removed(self):
        base = locator_project()
        ours = remove_locator(base, "Outro")
        plan = _plan_for(base, ours, base)
        removed = [lc for lc in plan.locator_changes if lc.kind == "removed"]
        assert len(removed) == 1
        assert removed[0].name == "Outro"
        assert removed[0].branch == "ours"

    def test_theirs_only_removed(self):
        base = locator_project()
        theirs = remove_locator(base, "Intro")
        plan = _plan_for(base, base, theirs)
        removed = [lc for lc in plan.locator_changes if lc.kind == "removed"]
        assert len(removed) == 1
        assert removed[0].name == "Intro"
        assert removed[0].branch == "theirs"

    def test_both_removed_identically(self):
        base = locator_project()
        ours = remove_locator(base, "Outro")
        theirs = remove_locator(base, "Outro")
        plan = _plan_for(base, ours, theirs)
        removed_both = [lc for lc in plan.locator_changes if lc.kind == "removed" and lc.branch == "both"]
        assert len(removed_both) >= 1


class TestLocatorRemoveVsMove:
    def test_ours_remove_theirs_move_conflicts(self):
        base = locator_project()
        ours = remove_locator(base, "Outro")
        theirs = move_locator(base, "Outro", 70.0)
        plan = _plan_for(base, ours, theirs)
        conflicts = [c for c in plan.conflicts if c.field == "locator.remove_vs_move"]
        assert len(conflicts) >= 1

    def test_ours_move_theirs_remove_conflicts(self):
        base = locator_project()
        ours = move_locator(base, "Chorus", 20.0)
        theirs = remove_locator(base, "Chorus")
        plan = _plan_for(base, ours, theirs)
        conflicts = [c for c in plan.conflicts if c.field == "locator.remove_vs_move"]
        assert len(conflicts) >= 1


class TestLocatorOneSidedAddition:
    def test_ours_only_addition(self):
        base = locator_project()
        ours = add_locator(base, "Bridge", 33.0)
        plan = _plan_for(base, ours, base)
        added = [lc for lc in plan.locator_changes if lc.kind == "added"]
        assert len(added) == 1
        assert added[0].name == "Bridge"
        assert added[0].branch == "ours"
        assert added[0].ours_time == 33.0

    def test_theirs_only_addition(self):
        base = locator_project()
        theirs = add_locator(base, "Solo", 49.0)
        plan = _plan_for(base, base, theirs)
        added = [lc for lc in plan.locator_changes if lc.kind == "added"]
        assert len(added) == 1
        assert added[0].name == "Solo"
        assert added[0].branch == "theirs"


class TestLocatorIdenticalTwoSidedAddition:
    def test_both_added_identically(self):
        base = locator_project()
        ours = add_locator(base, "Drop", 41.0)
        theirs = add_locator(base, "Drop", 41.0)
        plan = _plan_for(base, ours, theirs)
        assert plan.conflict_count == 0
        added = [lc for lc in plan.locator_changes if lc.kind == "added" and lc.name == "Drop"]
        assert len(added) == 1
        assert added[0].ours_time == 41.0
        assert added[0].theirs_time == 41.0


class TestLocatorSameNameDifferentTimeAddition:
    def test_same_name_different_time_conflicts(self):
        base = locator_project()
        ours = add_locator(base, "Marker", 10.0)
        theirs = add_locator(base, "Marker", 20.0)
        plan = _plan_for(base, ours, theirs)
        conflicts = [c for c in plan.conflicts if c.field == "locator.addition"]
        assert len(conflicts) == 1
        assert conflicts[0].ours_value == 10.0
        assert conflicts[0].theirs_value == 20.0


class TestLocatorDistinctNameIndependentAdditions:
    def test_distinct_name_additions_no_conflict(self):
        base = locator_project()
        ours = add_locator(base, "Breakdown", 50.0)
        theirs = add_locator(base, "Build", 55.0)
        plan = _plan_for(base, ours, theirs)
        assert plan.conflict_count == 0
        added = [lc for lc in plan.locator_changes if lc.kind == "added"]
        assert len(added) >= 2


class TestLocatorDuplicateNames:
    def test_duplicate_locator_names_conflict(self):
        reset_ids()
        from tests.three_way.fixtures import snapshot, locator
        base = snapshot(
            tempo=120.0,
            tracks=[],
            locators=[locator("Dup", 1.0)],
        )
        ours = snapshot(
            tempo=120.0,
            tracks=[],
            locators=[locator("Dup", 3.0), locator("Dup", 7.0)],
        )
        plan = _plan_for(base, ours, base)
        conflicts = [c for c in plan.conflicts if "duplicate-name" in c.id]
        assert len(conflicts) >= 1
