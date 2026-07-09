# SPDX-License-Identifier: GPL-3.0-only
"""Tests for alscan.merge.semantics — three-way field semantics."""

from alscan.merge.semantics import (
    three_way_scalar,
    three_way_device_list,
    merge_sample_name_union,
    track_exact_identity,
    three_way_track_field,
)


class TestThreeWayScalar:
    def test_all_same(self):
        val, conflict = three_way_scalar(120, 120, 120)
        assert val == 120
        assert not conflict

    def test_ours_changed(self):
        val, conflict = three_way_scalar(120, 130, 120)
        assert val == 130
        assert not conflict

    def test_theirs_changed(self):
        val, conflict = three_way_scalar(120, 120, 130)
        assert val == 130
        assert not conflict

    def test_both_changed_same(self):
        val, conflict = three_way_scalar(120, 130, 130)
        assert val == 130
        assert not conflict

    def test_both_changed_different(self):
        val, conflict = three_way_scalar(120, 130, 128)
        assert val == 120
        assert conflict

    def test_all_different(self):
        val, conflict = three_way_scalar(120, 130, 140)
        assert val == 120
        assert conflict

    def test_strings(self):
        val, conflict = three_way_scalar("A", "A", "A")
        assert val == "A"
        assert not conflict

    def test_none_values(self):
        val, conflict = three_way_scalar(None, "X", None)
        assert val == "X"
        assert not conflict


class TestThreeWayDeviceList:
    def test_all_same(self):
        devs = [{"name": "Comp", "device_type": "audio_effect"}]
        result, conflict = three_way_device_list(devs, devs, devs)
        assert result == devs
        assert not conflict

    def test_ours_changed(self):
        base = [{"name": "Comp"}]
        ours = [{"name": "Limiter"}]
        result, conflict = three_way_device_list(base, ours, base)
        assert result == ours
        assert not conflict

    def test_both_changed_same(self):
        base = [{"name": "Comp"}]
        changed = [{"name": "Limiter"}, {"name": "EQ"}]
        result, conflict = three_way_device_list(base, changed, changed)
        assert result == changed
        assert not conflict

    def test_both_changed_different(self):
        base = [{"name": "Comp"}]
        ours = [{"name": "Limiter"}]
        theirs = [{"name": "EQ"}]
        result, conflict = three_way_device_list(base, ours, theirs)
        assert result == base
        assert conflict

    def test_empty_list(self):
        result, conflict = three_way_device_list([], [], [])
        assert result == []
        assert not conflict


class TestMergeSampleNameUnion:
    def test_all_same(self):
        samples = ["Kick.wav", "Snare.wav"]
        result, warnings = merge_sample_name_union(samples, samples, samples)
        assert result == samples
        assert warnings == []

    def test_one_side_adds(self):
        base = ["Kick.wav"]
        ours = ["Kick.wav", "Snare.wav"]
        result, warnings = merge_sample_name_union(base, ours, base)
        assert result == ["Kick.wav", "Snare.wav"]
        assert len(warnings) == 1
        assert "retention-biased" in warnings[0]

    def test_both_add_different(self):
        base = ["Kick.wav"]
        ours = ["Kick.wav", "Snare.wav"]
        theirs = ["Kick.wav", "HiHat.wav"]
        result, warnings = merge_sample_name_union(base, ours, theirs)
        assert result == ["HiHat.wav", "Kick.wav", "Snare.wav"]
        assert len(warnings) == 1

    def test_both_add_same(self):
        base = ["Kick.wav"]
        ours = ["Kick.wav", "Snare.wav"]
        theirs = ["Kick.wav", "Snare.wav"]
        result, warnings = merge_sample_name_union(base, ours, theirs)
        assert result == ["Kick.wav", "Snare.wav"]
        assert len(warnings) == 0

    def test_one_removes_other_keeps(self):
        base = ["Kick.wav", "Snare.wav"]
        ours = ["Kick.wav"]
        theirs = ["Kick.wav", "Snare.wav"]
        result, warnings = merge_sample_name_union(base, ours, theirs)
        assert result == ["Kick.wav", "Snare.wav"]
        assert len(warnings) == 1

    def test_both_remove(self):
        base = ["Kick.wav", "Snare.wav"]
        ours = ["Kick.wav"]
        theirs = ["Kick.wav"]
        result, warnings = merge_sample_name_union(base, ours, theirs)
        assert result == ["Kick.wav"]
        assert warnings == []

    def test_retention_biased_documented(self):
        base = ["A.wav"]
        ours = ["B.wav"]
        theirs = ["A.wav"]
        result, warnings = merge_sample_name_union(base, ours, theirs)
        assert "B.wav" in result
        assert any("retention-biased" in w for w in warnings)


class TestTrackExactIdentity:
    def make_track(self, tid, name="Track", ttype="audio"):
        return {"track_id": tid, "name": name, "track_type": ttype}

    def test_exact_match(self):
        bt = self.make_track(0, "Synth", "midi")
        ot = self.make_track(0, "Synth", "midi")
        tt = self.make_track(0, "Synth", "midi")
        is_exact, confidence, warnings = track_exact_identity(bt, ot, tt)
        assert is_exact
        assert confidence == "exact"
        assert warnings == []

    def test_same_id_incompatible_type(self):
        bt = self.make_track(0, "Synth", "midi")
        ot = self.make_track(0, "Synth", "audio")
        tt = self.make_track(0, "Synth", "midi")
        is_exact, confidence, warnings = track_exact_identity(bt, ot, tt)
        assert not is_exact
        assert confidence == "ambiguous"
        assert len(warnings) == 1
        assert "track type differs" in warnings[0]

    def test_different_id(self):
        bt = self.make_track(0, "Synth", "midi")
        ot = self.make_track(1, "Synth", "midi")
        tt = self.make_track(0, "Synth", "midi")
        is_exact, confidence, warnings = track_exact_identity(bt, ot, tt)
        assert not is_exact
        assert confidence == "unmatched"

    def test_absent_from_ours(self):
        bt = self.make_track(0)
        is_exact, confidence, warnings = track_exact_identity(bt, None, bt)
        assert not is_exact
        assert confidence == "unmatched"

    def test_absent_from_theirs(self):
        bt = self.make_track(0)
        is_exact, confidence, warnings = track_exact_identity(bt, bt, None)
        assert not is_exact
        assert confidence == "unmatched"

    def test_absent_from_both(self):
        bt = self.make_track(0)
        is_exact, confidence, warnings = track_exact_identity(bt, None, None)
        assert not is_exact
        assert confidence == "unmatched"


class TestThreeWayTrackField:
    def test_unchanged(self):
        bt = {"name": "Synth"}
        val, conflict = three_way_track_field(bt, bt, bt, "name")
        assert val == "Synth"
        assert not conflict

    def test_ours_changed(self):
        bt = {"name": "Synth"}
        ot = {"name": "Pad Synth"}
        val, conflict = three_way_track_field(bt, ot, bt, "name")
        assert val == "Pad Synth"
        assert not conflict

    def test_conflict(self):
        bt = {"name": "Synth"}
        ot = {"name": "Lead Synth"}
        tt = {"name": "Pad Synth"}
        val, conflict = three_way_track_field(bt, ot, tt, "name")
        assert conflict
