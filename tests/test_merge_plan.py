"""Tests for alscan.merge.plan — MergePlan dataclass and JSON serialization."""

import json

from alscan.merge.plan import MergePlan, Conflict, AutoResolved, IdentityMatch


def test_merge_plan_defaults():
    plan = MergePlan()
    assert plan.document_type == "alscan-merge-plan"
    assert plan.format_version == "2"
    assert plan.conflict_count == 0
    assert plan.warning_count == 0


def test_merge_plan_to_json():
    plan = MergePlan(
        input_mode="als",
        lineage_confidence="strong",
        conflict_count=0,
    )
    raw = plan.to_json()
    d = json.loads(raw)
    assert d["document_type"] == "alscan-merge-plan"
    assert d["format_version"] == "2"
    assert d["input_mode"] == "als"
    assert d["lineage_confidence"] == "strong"
    assert d["conflict_count"] == 0
    assert "created_at_utc" in d


def test_merge_plan_with_conflict():
    plan = MergePlan(conflict_count=1)
    plan.conflicts.append(Conflict(
        id="conflict-tempo",
        field="tempo",
        base_value=120.0,
        ours_value=130.0,
        theirs_value=128.0,
        reason="Both sides changed tempo to different values",
    ))
    raw = plan.to_json()
    d = json.loads(raw)
    assert d["conflict_count"] == 1
    assert len(d["conflicts"]) == 1
    assert d["conflicts"][0]["field"] == "tempo"
    assert d["conflicts"][0]["base_value"] == 120.0


def test_merge_plan_with_auto_resolved():
    plan = MergePlan()
    plan.auto_resolved.append(AutoResolved(
        id="resolve-tempo",
        field="tempo",
        base_value=120.0,
        resolved_value=128.0,
        resolution="accept_theirs",
    ))
    raw = plan.to_json()
    d = json.loads(raw)
    assert len(d["auto_resolved"]) == 1
    assert d["auto_resolved"][0]["resolved_value"] == 128.0


def test_merge_plan_with_identity_matches():
    plan = MergePlan()
    plan.identity_matches.append(IdentityMatch(
        track_id=0, name="Synth",
        base_track_id=0, ours_track_id=0, theirs_track_id=0,
        confidence="exact",
    ))
    raw = plan.to_json()
    d = json.loads(raw)
    assert len(d["identity_matches"]) == 1
    assert d["identity_matches"][0]["confidence"] == "exact"


def test_merge_plan_sources():
    plan = MergePlan()
    plan.sources = {
        "base": {"sha256": "abc", "size": 100, "label": "base.als"},
        "ours": {"sha256": "def", "size": 101, "label": "ours.als"},
        "theirs": {"sha256": "ghi", "size": 99, "label": "theirs.als"},
    }
    raw = plan.to_json()
    d = json.loads(raw)
    assert d["sources"]["base"]["label"] == "base.als"
    assert d["sources"]["ours"]["sha256"] == "def"


def test_merge_plan_supported_field_scope():
    plan = MergePlan()
    assert "tempo" in plan.supported_field_scope
    assert "track_devices" in plan.supported_field_scope
    assert len(plan.supported_field_scope) == 13


def test_merge_plan_warnings():
    plan = MergePlan(warning_count=2)
    plan.warnings = ["warning 1", "warning 2"]
    raw = plan.to_json()
    d = json.loads(raw)
    assert d["warning_count"] == 2
    assert len(d["warnings"]) == 2


def test_utc_now_populated():
    plan = MergePlan()
    raw = plan.to_json()
    d = json.loads(raw)
    assert d["created_at_utc"] != ""
    assert d["created_at_utc"].endswith("Z")
