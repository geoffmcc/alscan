# SPDX-License-Identifier: GPL-3.0-only
"""Baseline invariants and scalar metadata tests for three-way analysis.

Validates that the merge analysis engine produces correct results for:
- Base == Ours == Theirs (no-op)
- Single-branch changes
- Convergent same changes
- Swapped Ours/Theirs symmetry
- Determinism
- Tempo and time signature scalar fields
"""

from __future__ import annotations

import json

import pytest

from alscan.merge.analysis import build_merge_plan
from alscan.merge.inputs import validate_three_way
from alscan.merge.plan import MergePlan
from alscan.services import create_merge_plan

from tests.three_way.fixtures import (
    two_track_project, three_track_project,
    snapshot, track,
    mutate, with_tempo, with_time_signature,
    reset_ids,
)


def _plan_for(base, ours, theirs):
    """Build a MergePlan from three Snapshots without file I/O."""
    from pathlib import Path
    from types import SimpleNamespace
    from alscan.merge.inputs import assess_lineage

    lineage = assess_lineage(base, ours, theirs)
    inputs = SimpleNamespace(
        mode="snapshot",
        base_snapshot=base,
        ours_snapshot=ours,
        theirs_snapshot=theirs,
        base_identity=SimpleNamespace(sha256="b" * 40, size=100, path=Path("base.json")),
        ours_identity=SimpleNamespace(sha256="o" * 40, size=100, path=Path("ours.json")),
        theirs_identity=SimpleNamespace(sha256="t" * 40, size=100, path=Path("theirs.json")),
        lineage=lineage,
        allow_plausible=False,
    )
    return build_merge_plan(inputs)


# ---------------------------------------------------------------------------
# Baseline invariants
# ---------------------------------------------------------------------------


class TestIdentityNoOp:
    """Base == Ours == Theirs: should produce no changes."""

    def test_identical_triple_no_changes(self):
        base = two_track_project()
        plan = _plan_for(base, base, base)
        assert plan.conflict_count == 0
        assert not plan.auto_resolved
        assert not plan.track_changes
        json_out = json.loads(plan.to_json())
        assert json_out["conflict_count"] == 0

    def test_identical_triple_empty_tracks(self):
        reset_ids()
        base = snapshot(tempo=120.0, tracks=[])
        plan = _plan_for(base, base, base)
        assert plan.conflict_count == 0
        assert not plan.track_changes

    def test_identical_triple_with_devices(self):
        from tests.three_way.fixtures import device_heavy_project
        base = device_heavy_project()
        plan = _plan_for(base, base, base)
        assert plan.conflict_count == 0
        assert not plan.auto_resolved

    def test_identical_triple_with_locators(self):
        from tests.three_way.fixtures import locator_project
        base = locator_project()
        plan = _plan_for(base, base, base)
        assert plan.conflict_count == 0
        # Unchanged locators may appear in the list but should have kind 'unchanged'
        any_changed = [lc for lc in plan.locator_changes if lc.kind != "unchanged"]
        assert not any_changed, f"Expected only unchanged locators, got: {any_changed}"


class TestSingleBranchChanges:
    """Verify changes are attributed to the correct branch."""

    def test_ours_only_tempo_change(self):
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        plan = _plan_for(base, ours, base)
        assert plan.conflict_count == 0
        assert len(plan.auto_resolved) >= 1
        tempo_ar = next(ar for ar in plan.auto_resolved if ar.field == "tempo")
        assert tempo_ar.resolution == "accept_ours"
        assert tempo_ar.base_value == 120.0
        assert tempo_ar.resolved_value == 128.0

    def test_theirs_only_tempo_change(self):
        base = two_track_project()
        theirs = with_tempo(base, 132.0)
        plan = _plan_for(base, base, theirs)
        assert plan.conflict_count == 0
        tempo_ar = next(ar for ar in plan.auto_resolved if ar.field == "tempo")
        assert tempo_ar.resolution == "accept_theirs"

    def test_ours_only_time_sig_change(self):
        base = two_track_project()
        ours = with_time_signature(base, 3, 4)
        plan = _plan_for(base, ours, base)
        assert plan.conflict_count == 0
        ts_ar = next(ar for ar in plan.auto_resolved if ar.field == "time_signature")
        assert ts_ar.resolution == "accept_ours"

    def test_ours_only_track_addition(self):
        base = two_track_project()
        from tests.three_way.fixtures import add_track
        ours = add_track(base, name="New Track", track_type="audio", clips=1)
        plan = _plan_for(base, ours, base)
        assert plan.conflict_count == 0
        additions = [tc for tc in plan.track_changes if tc.kind == "added"]
        assert len(additions) == 1
        assert additions[0].branch == "ours"

    def test_theirs_only_track_removal(self):
        base = two_track_project()
        from tests.three_way.fixtures import remove_track
        theirs = remove_track(base, 2)
        plan = _plan_for(base, base, theirs)
        removals = [tc for tc in plan.track_changes if tc.kind == "removed"]
        assert len(removals) == 1
        assert removals[0].branch == "theirs"


class TestConvergentChanges:
    """Both branches make the same change: should auto-resolve without conflict."""

    def test_same_tempo_change_both_branches(self):
        base = two_track_project()
        ours = with_tempo(base, 140.0)
        theirs = with_tempo(base, 140.0)
        plan = _plan_for(base, ours, theirs)
        assert plan.conflict_count == 0
        tempo_ar = next(ar for ar in plan.auto_resolved if ar.field == "tempo")
        assert tempo_ar.resolved_value == 140.0

    def test_same_time_sig_change_both_branches(self):
        base = two_track_project()
        ours = with_time_signature(base, 6, 8)
        theirs = with_time_signature(base, 6, 8)
        plan = _plan_for(base, ours, theirs)
        assert plan.conflict_count == 0


class TestSymmetry:
    """Swapping Ours/Theirs should preserve conflict count and swap attribution."""

    def test_swap_preserves_conflict_count(self):
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        theirs = with_tempo(base, 132.0)
        plan_fwd = _plan_for(base, ours, theirs)
        plan_swapped = _plan_for(base, theirs, ours)
        assert plan_fwd.conflict_count == plan_swapped.conflict_count
        assert plan_fwd.warning_count == plan_swapped.warning_count

    def test_swap_swaps_attribution(self):
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        theirs = base  # theirs unchanged
        plan_fwd = _plan_for(base, ours, theirs)
        plan_swapped = _plan_for(base, theirs, ours)  # swapped
        ar_fwd = next(ar for ar in plan_fwd.auto_resolved if ar.field == "tempo")
        ar_swapped = next(ar for ar in plan_swapped.auto_resolved if ar.field == "tempo")
        assert ar_fwd.resolution != ar_swapped.resolution


class TestDeterminism:
    """Repeated analysis should produce identical output."""

    def test_repeated_analysis_deterministic(self):
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        theirs = with_tempo(base, 132.0)
        plan1 = _plan_for(base, ours, theirs)
        plan2 = _plan_for(base, ours, theirs)
        assert json.loads(plan1.to_json()) == json.loads(plan2.to_json())

    def test_complex_deterministic(self):
        from tests.three_way.fixtures import (
            device_heavy_project, add_track, remove_track,
            with_track_field,
        )
        base = device_heavy_project()
        ours = with_track_field(add_track(base, name="New", track_type="midi", clips=1), 1, volume=0.5)
        theirs = remove_track(with_track_field(base, 2, name="Bass Synth"), 1)
        plan1 = _plan_for(base, ours, theirs)
        plan2 = _plan_for(base, ours, theirs)
        assert json.loads(plan1.to_json()) == json.loads(plan2.to_json())


# ---------------------------------------------------------------------------
# Scalar metadata conflicts
# ---------------------------------------------------------------------------


class TestTempoConflict:
    """Conflicting tempo changes across branches."""

    def test_divergent_tempo(self):
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        theirs = with_tempo(base, 132.0)
        plan = _plan_for(base, ours, theirs)
        conflicts = [c for c in plan.conflicts if c.field == "tempo"]
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c.base_value == 120.0
        assert c.ours_value == 128.0
        assert c.theirs_value == 132.0

    def test_tempo_revert_to_base_on_one_side(self):
        """Ours changes tempo, theirs changes and reverts it back."""
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        theirs = base  # no change = stayed at base
        plan = _plan_for(base, ours, theirs)
        assert plan.conflict_count == 0

    def test_tempo_both_different_from_base_and_different(self):
        base = two_track_project()
        ours = with_tempo(base, 100.0)
        theirs = with_tempo(base, 200.0)
        plan = _plan_for(base, ours, theirs)
        conflicts = [c for c in plan.conflicts if c.field == "tempo"]
        assert len(conflicts) == 1

    def test_tempo_triple_all_different(self):
        base = snapshot(tempo=120.0, tracks=[])
        ours = snapshot(tempo=100.0, tracks=[])
        theirs = snapshot(tempo=140.0, tracks=[])
        plan = _plan_for(base, ours, theirs)
        conflicts = [c for c in plan.conflicts if c.field == "tempo"]
        assert len(conflicts) == 1


class TestTimeSignatureConflict:
    """Conflicting time signature changes."""

    def test_divergent_time_sig(self):
        base = two_track_project()
        ours = with_time_signature(base, 3, 4)
        theirs = with_time_signature(base, 6, 8)
        plan = _plan_for(base, ours, theirs)
        conflicts = [c for c in plan.conflicts if c.field == "time_signature"]
        assert len(conflicts) == 1

    def test_time_sig_ours_only(self):
        base = two_track_project()
        ours = with_time_signature(base, 5, 4)
        plan = _plan_for(base, ours, base)
        assert plan.conflict_count == 0
        ts_ar = next(ar for ar in plan.auto_resolved if ar.field == "time_signature")
        assert ts_ar.resolved_value == [5, 4]

    def test_time_sig_convergent(self):
        base = two_track_project()
        ours = with_time_signature(base, 7, 8)
        theirs = with_time_signature(base, 7, 8)
        plan = _plan_for(base, ours, theirs)
        assert plan.conflict_count == 0
