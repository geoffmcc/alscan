from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from alscan.cli import cli
from alscan.merge.analysis import build_merge_plan
from alscan.merge.inputs import LineageResult
from alscan.versioner import Snapshot


RUNNER = CliRunner()


def tr(track_id: int, name: str, track_type: str = "audio", **overrides) -> dict:
    data = {
        "track_id": track_id,
        "name": name,
        "track_type": track_type,
        "is_frozen": False,
        "color_index": 1,
        "group_id": None,
        "volume": 0.75,
        "device_count": 1,
        "clip_count": 1,
        "devices": [{"name": "EQ", "device_type": "native", "plugin_name": None, "plugin_type": None}],
        "samples": [],
    }
    data.update(overrides)
    return data


def snap(tracks=None, locators=None, name="song") -> Snapshot:
    tracks = tracks or []
    return Snapshot(
        format_version="1",
        structural_fingerprint="fp",
        project_name=name,
        timestamp=1.0,
        creator="test",
        major_version="12",
        minor_version="1",
        tempo=120.0,
        time_signature=[4, 4],
        tracks=tracks,
        locators=locators or [],
    )


def inputs(base: Snapshot, ours: Snapshot, theirs: Snapshot):
    def ident(label):
        return SimpleNamespace(sha256=f"sha-{label}", size=100, path=Path(f"{label}.json"))
    return SimpleNamespace(
        mode="snapshot",
        base_snapshot=base,
        ours_snapshot=ours,
        theirs_snapshot=theirs,
        base_identity=ident("base"),
        ours_identity=ident("ours"),
        theirs_identity=ident("theirs"),
        lineage=LineageResult(level="strong", fingerprint_match=True, track_overlap_pct=1.0, project_name_match=True),
    )


def plan_for(base_tracks, ours_tracks, theirs_tracks, base_locs=None, ours_locs=None, theirs_locs=None):
    return build_merge_plan(inputs(
        snap(base_tracks, base_locs),
        snap(ours_tracks, ours_locs),
        snap(theirs_tracks, theirs_locs),
    ))


def conflicts(plan, field: str) -> list:
    return [c for c in plan.conflicts if c.field == field]


def identities(plan, classification: str) -> list:
    return [m for m in plan.identity_matches if m.classification == classification]


class TestPhase2TrackIdentity:
    def test_same_id_compatible_type_exact(self):
        p = plan_for([tr(1, "Kick")], [tr(1, "Kick")], [tr(1, "Kick")])
        assert identities(p, "exact")

    def test_same_id_incompatible_type_ambiguous(self):
        p = plan_for([tr(1, "Kick", "audio")], [tr(1, "Kick", "midi")], [tr(1, "Kick")])
        assert identities(p, "ambiguous")
        assert conflicts(p, "track.identity")

    def test_different_id_three_fields_plausible(self):
        p = plan_for([tr(1, "Kick")], [tr(10, "Kick")], [tr(20, "Kick")])
        match = identities(p, "plausible")[0]
        assert {"name", "track_type", "devices"}.issubset(set(match.evidence))
        assert match.auto_resolved is False

    def test_only_name_matches_is_ambiguous(self):
        ours = tr(10, "Kick", track_type="midi", is_frozen=True, color_index=7, volume=0.1, clip_count=9, devices=[])
        theirs = tr(20, "Kick", track_type="midi", is_frozen=True, color_index=8, volume=0.2, clip_count=8, devices=[])
        p = plan_for([tr(1, "Kick")], [ours], [theirs])
        assert identities(p, "ambiguous")

    def test_duplicate_candidate_matches_are_ambiguous(self):
        base = [tr(1, "Kick"), tr(2, "Kick")]
        p = plan_for(base, [tr(10, "Kick")], [tr(20, "Kick")])
        assert len(identities(p, "ambiguous")) == 2
        assert conflicts(p, "track.identity")

    def test_one_exact_and_one_plausible_branch_match(self):
        p = plan_for([tr(1, "Kick")], [tr(1, "Kick")], [tr(20, "Kick")])
        match = identities(p, "plausible")[0]
        assert match.ours_track_id == 1
        assert match.theirs_track_id == 20

    def test_both_branches_plausible_with_different_branch_ids(self):
        p = plan_for([tr(1, "Kick")], [tr(10, "Kick")], [tr(20, "Kick")])
        match = identities(p, "plausible")[0]
        assert (match.ours_track_id, match.theirs_track_id) == (10, 20)

    def test_samples_do_not_strengthen_identity(self):
        base = tr(1, "Kick", samples=["same.wav"])
        ours = tr(10, "Other", track_type="midi", is_frozen=True, color_index=7, volume=0.1, clip_count=9, devices=[], samples=["same.wav"])
        theirs = tr(20, "Other", track_type="midi", is_frozen=True, color_index=8, volume=0.2, clip_count=8, devices=[], samples=["same.wav"])
        p = plan_for([base], [ours], [theirs])
        assert not identities(p, "plausible")

    def test_unrelated_default_audio_tracks_are_not_plausible(self):
        base = tr(1, "Kick", devices=[], clip_count=0)
        ours = tr(10, "Unrelated", devices=[], clip_count=0)
        theirs = tr(20, "Other", devices=[], clip_count=0)
        p = plan_for([base], [ours], [theirs])
        assert not identities(p, "plausible")
        assert any(c.kind == "added" for c in p.track_changes)

    def test_empty_device_lists_provide_no_evidence(self):
        base = tr(1, "Kick", devices=[], clip_count=0)
        ours = tr(10, "Other", devices=[], clip_count=0)
        theirs = tr(20, "Other2", devices=[], clip_count=0)
        p = plan_for([base], [ours], [theirs])
        assert all("devices" not in m.evidence for m in p.identity_matches)

    def test_type_frozen_default_volume_is_insufficient(self):
        base = tr(1, "Kick", is_frozen=True, volume=0.75, devices=[], clip_count=0)
        ours = tr(10, "Other", is_frozen=True, volume=0.75, devices=[], clip_count=0)
        theirs = tr(20, "Other2", is_frozen=True, volume=0.75, devices=[], clip_count=0)
        p = plan_for([base], [ours], [theirs])
        assert not identities(p, "plausible")

    def test_one_strong_field_plus_supporting_fields_is_plausible(self):
        base = tr(1, "Distinct", clip_count=3, volume=0.9)
        ours = tr(10, "Distinct", clip_count=3, volume=0.9)
        theirs = tr(20, "Distinct", clip_count=3, volume=0.9)
        p = plan_for([base], [ours], [theirs])
        match = identities(p, "plausible")[0]
        assert "name" in match.evidence
        assert match.auto_resolved is False

    def test_duplicate_ids_in_base_are_ambiguous(self):
        p = plan_for([tr(1, "A"), tr(1, "B")], [tr(1, "A")], [tr(1, "A")])
        assert conflicts(p, "track.identity")

    def test_duplicate_ids_in_ours_are_ambiguous(self):
        p = plan_for([tr(1, "A")], [tr(1, "A"), tr(1, "A", track_type="midi")], [tr(1, "A")])
        assert conflicts(p, "track.identity")

    def test_duplicate_ids_in_theirs_are_ambiguous(self):
        p = plan_for([tr(1, "A")], [tr(1, "A")], [tr(1, "A"), tr(1, "A", track_type="midi")])
        assert conflicts(p, "track.identity")

    def test_mixed_compatible_duplicate_id_does_not_become_exact(self):
        p = plan_for([tr(1, "A")], [tr(1, "A"), tr(1, "A", track_type="midi")], [tr(1, "A")])
        assert not identities(p, "exact")


class TestPhase2TrackChanges:
    def test_one_branch_removes_other_unchanged(self):
        p = plan_for([tr(1, "Kick")], [], [tr(1, "Kick")])
        assert any(c.kind == "removed" and c.branch == "ours" for c in p.track_changes)

    def test_both_remove(self):
        p = plan_for([tr(1, "Kick")], [], [])
        assert any(c.kind == "removed" and c.branch == "both" and c.auto_resolved for c in p.track_changes)

    def test_one_removes_other_modifies_conflict(self):
        p = plan_for([tr(1, "Kick")], [], [tr(1, "Kick loud", volume=0.9)])
        assert conflicts(p, "track.delete_vs_modify")

    def test_one_sided_addition(self):
        p = plan_for([tr(1, "Kick")], [tr(1, "Kick"), tr(2, "Hat")], [tr(1, "Kick")])
        assert any(c.kind == "added" and c.branch == "ours" for c in p.track_changes)

    def test_identical_two_sided_addition(self):
        p = plan_for([tr(1, "Kick")], [tr(1, "Kick"), tr(2, "Hat")], [tr(1, "Kick"), tr(3, "Hat")])
        assert any(c.kind == "added" and c.branch == "both" for c in p.track_changes)

    def test_competing_two_sided_additions_conflict(self):
        p = plan_for([tr(1, "Kick"), tr(4, "Bass")], [tr(1, "Kick"), tr(2, "Hat"), tr(4, "Bass")], [tr(1, "Kick"), tr(3, "Snare"), tr(4, "Bass")])
        assert conflicts(p, "track.insertion_position")

    def test_divergent_base_track_reordering_conflict(self):
        p = plan_for([tr(1, "Kick"), tr(2, "Snare")], [tr(2, "Snare"), tr(1, "Kick")], [tr(1, "Kick"), tr(2, "Snare")])
        assert conflicts(p, "track.order")

    def test_unambiguous_insertion_position(self):
        p = plan_for([tr(1, "Kick"), tr(3, "Bass")], [tr(1, "Kick"), tr(2, "Hat"), tr(3, "Bass")], [tr(1, "Kick"), tr(3, "Bass")])
        added = [c for c in p.track_changes if c.kind == "added" and c.branch == "ours"][0]
        assert added.proposed_position == {"after_base_track_id": 1, "before_base_track_id": 3}

    def test_ambiguous_insertion_position(self):
        p = plan_for([], [tr(2, "Hat")], [])
        added = [c for c in p.track_changes if c.kind == "added"][0]
        assert added.details["position"] == "ambiguous"
        assert conflicts(p, "track.insertion_position")

    def test_insertion_before_first_base_track(self):
        p = plan_for([tr(1, "Kick")], [tr(2, "Hat"), tr(1, "Kick")], [tr(1, "Kick")])
        added = [c for c in p.track_changes if c.kind == "added"][0]
        assert added.proposed_position == {"after_base_track_id": None, "before_base_track_id": 1}

    def test_insertion_after_last_base_track(self):
        p = plan_for([tr(1, "Kick")], [tr(1, "Kick"), tr(2, "Hat")], [tr(1, "Kick")])
        added = [c for c in p.track_changes if c.kind == "added"][0]
        assert added.proposed_position == {"after_base_track_id": 1, "before_base_track_id": None}

    def test_two_one_sided_additions_same_branch_gap_are_deterministic(self):
        p = plan_for([tr(1, "Kick"), tr(4, "Bass")], [tr(1, "Kick"), tr(2, "Hat"), tr(3, "Clap"), tr(4, "Bass")], [tr(1, "Kick"), tr(4, "Bass")])
        assert not conflicts(p, "track.insertion_position")
        assert [c.name for c in p.track_changes if c.kind == "added"] == ["Hat", "Clap"]

    def test_same_name_different_additions_same_gap_conflict(self):
        p = plan_for([tr(1, "Kick"), tr(4, "Bass")], [tr(1, "Kick"), tr(2, "Hat", volume=0.8), tr(4, "Bass")], [tr(1, "Kick"), tr(3, "Hat", volume=0.9), tr(4, "Bass")])
        assert conflicts(p, "track.insertion_position")

    def test_plausible_identity_is_not_order_anchor(self):
        base = [tr(1, "Kick"), tr(4, "Bass")]
        ours = [tr(10, "Kick"), tr(2, "Hat"), tr(4, "Bass")]
        theirs = [tr(20, "Kick"), tr(4, "Bass")]
        p = plan_for(base, ours, theirs)
        added = [c for c in p.track_changes if c.name == "Hat"][0]
        assert added.proposed_position == {"after_base_track_id": None, "before_base_track_id": 4}


class TestPhase2Locators:
    def test_unchanged_locator(self):
        p = plan_for([], [], [], [{"name": "A", "time": 1}], [{"name": "A", "time": 1}], [{"name": "A", "time": 1}])
        assert any(c.kind == "unchanged" for c in p.locator_changes)

    def test_one_sided_movement(self):
        p = plan_for([], [], [], [{"name": "A", "time": 1}], [{"name": "A", "time": 2}], [{"name": "A", "time": 1}])
        assert any(c.kind == "moved" and c.branch == "ours" for c in p.locator_changes)

    def test_both_move_identically(self):
        p = plan_for([], [], [], [{"name": "A", "time": 1}], [{"name": "A", "time": 2}], [{"name": "A", "time": 2}])
        assert any(c.kind == "moved" and c.branch == "both" for c in p.locator_changes)

    def test_both_move_differently(self):
        p = plan_for([], [], [], [{"name": "A", "time": 1}], [{"name": "A", "time": 2}], [{"name": "A", "time": 3}])
        assert conflicts(p, "locator.movement")

    def test_one_removes_other_leaves_unchanged(self):
        p = plan_for([], [], [], [{"name": "A", "time": 1}], [], [{"name": "A", "time": 1}])
        assert any(c.kind == "removed" and c.branch == "ours" for c in p.locator_changes)

    def test_one_removes_other_moves(self):
        p = plan_for([], [], [], [{"name": "A", "time": 1}], [], [{"name": "A", "time": 2}])
        assert conflicts(p, "locator.remove_vs_move")

    def test_duplicate_name_ambiguity(self):
        p = plan_for([], [], [], [{"name": "A", "time": 1}, {"name": "A", "time": 2}], [], [])
        assert conflicts(p, "locator.identity")

    def test_one_sided_addition(self):
        p = plan_for([], [], [], [], [{"name": "A", "time": 1}], [])
        assert any(c.kind == "added" and c.branch == "ours" for c in p.locator_changes)

    def test_identical_two_sided_addition(self):
        p = plan_for([], [], [], [], [{"name": "A", "time": 1}], [{"name": "A", "time": 1}])
        assert any(c.kind == "added" and c.branch == "both" for c in p.locator_changes)

    def test_same_name_different_time_addition_conflict(self):
        p = plan_for([], [], [], [], [{"name": "A", "time": 1}], [{"name": "A", "time": 2}])
        assert conflicts(p, "locator.addition")

    def test_distinct_name_independent_additions(self):
        p = plan_for([], [], [], [], [{"name": "A", "time": 1}], [{"name": "B", "time": 2}])
        assert len([c for c in p.locator_changes if c.kind == "added"]) == 2
        assert not p.conflicts

    def test_duplicate_names_with_one_exact_tuple_match(self):
        p = plan_for([], [], [],
            [{"name": "A", "time": 1}],
            [{"name": "A", "time": 1}, {"name": "A", "time": 2}, {"name": "A", "time": 3}],
            [{"name": "A", "time": 1}],
        )
        assert any(c.kind == "unchanged" for c in p.locator_changes)
        assert any(c.field == "locator.identity" for c in p.conflicts)

    def test_exact_duplicate_tuples_leave_ambiguity(self):
        locs = [{"name": "A", "time": 1}, {"name": "A", "time": 1}]
        p = plan_for([], [], [], locs, locs, locs)
        assert len([c for c in p.locator_changes if c.kind == "unchanged"]) == 2
        assert not p.conflicts

    def test_near_equal_locator_time_uses_numeric_policy(self):
        p = plan_for([], [], [], [{"name": "A", "time": 1.0000001}], [{"name": "A", "time": 1.0000002}], [{"name": "A", "time": 1.0000003}])
        assert any(c.kind == "unchanged" for c in p.locator_changes)


class TestPhase2SafetyCompatibility:
    def write_snap(self, path: Path, snapshot: Snapshot) -> None:
        path.write_text(snapshot.to_json(), encoding="utf-8")

    def test_conflicts_publish_merge_plan_and_exit_3(self, tmp_path):
        base = tmp_path / "base.json"
        ours = tmp_path / "ours.json"
        theirs = tmp_path / "theirs.json"
        out = tmp_path / "plan.json"
        self.write_snap(base, snap([tr(1, "Kick")]))
        self.write_snap(ours, snap([tr(1, "Kick", volume=0.1)]))
        self.write_snap(theirs, snap([tr(1, "Kick", volume=0.2)]))
        result = RUNNER.invoke(cli, ["merge-plan", str(base), str(ours), str(theirs), "--output", str(out)])
        assert result.exit_code == 3, result.output
        d = json.loads(out.read_text(encoding="utf-8"))
        assert d["document_type"] == "alscan-merge-plan"
        assert d["conflict_count"] == 1

    def test_validation_failure_publishes_nothing_and_exits_1(self, tmp_path):
        base = tmp_path / "base.json"
        missing = tmp_path / "missing.json"
        out = tmp_path / "plan.json"
        self.write_snap(base, snap([tr(1, "Kick")]))
        result = RUNNER.invoke(cli, ["merge-plan", str(base), str(missing), str(base), "--output", str(out)])
        assert result.exit_code == 1
        assert not out.exists()

    def test_output_collision_remains_no_clobber(self, tmp_path):
        base = tmp_path / "base.json"
        ours = tmp_path / "ours.json"
        theirs = tmp_path / "theirs.json"
        out = tmp_path / "plan.json"
        for p in (base, ours, theirs):
            self.write_snap(p, snap([tr(1, "Kick")]))
        out.write_text("existing", encoding="utf-8")
        result = RUNNER.invoke(cli, ["merge-plan", str(base), str(ours), str(theirs), "--output", str(out)])
        assert result.exit_code == 1
        assert out.read_text(encoding="utf-8") == "existing"

    def test_no_absolute_paths_in_plan_output(self, tmp_path):
        base = tmp_path / "base.json"
        ours = tmp_path / "ours.json"
        theirs = tmp_path / "theirs.json"
        for p in (base, ours, theirs):
            self.write_snap(p, snap([tr(1, "Kick")]))
        result = RUNNER.invoke(cli, ["merge-plan", str(base), str(ours), str(theirs)])
        assert result.exit_code == 0, result.output
        assert str(tmp_path) not in result.output

    def test_non_finite_values_remain_rejected(self):
        bad = snap([tr(1, "Kick")])
        bad.tempo = float("nan")
        try:
            bad.to_json()
        except ValueError as e:
            assert "Out of range float" in str(e)
        else:
            raise AssertionError("non-finite snapshot JSON was accepted")

    def test_schema_version_is_phase2(self):
        p = plan_for([tr(1, "Kick")], [tr(1, "Kick")], [tr(1, "Kick")])
        d = json.loads(p.to_json())
        assert d["format_version"] == "2"
        assert "track_changes" in d
        assert "locator_changes" in d
        assert "proposed_track_order" in d

    def test_near_equal_volume_uses_numeric_policy(self):
        p = plan_for([tr(1, "Kick", volume=0.7500001)], [tr(1, "Kick", volume=0.7500002)], [tr(1, "Kick", volume=0.7500003)])
        assert not conflicts(p, "track.volume")

    def test_plausible_identity_field_changes_are_not_auto_resolved(self):
        fields = {
            "name": ("Kick", "Kick 2"),
            "track_type": ("audio", "midi"),
            "is_frozen": (False, True),
            "color_index": (1, 7),
            "group_id": (None, 4),
            "volume": (0.9, 0.8),
            "clip_count": (3, 4),
        }
        for field, (base_value, changed_value) in fields.items():
            base_track = tr(1, "Distinct", clip_count=3, volume=0.9)
            ours_track = tr(10, "Distinct", clip_count=3, volume=0.9)
            theirs_track = tr(20, "Distinct", clip_count=3, volume=0.9)
            base_track[field] = base_value
            ours_track[field] = changed_value
            p = plan_for([base_track], [ours_track], [theirs_track])
            changes = [c for c in p.track_changes if c.details.get("field") == field]
            if changes:
                assert all(c.auto_resolved is False for c in changes)
