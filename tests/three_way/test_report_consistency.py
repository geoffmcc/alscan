# SPDX-License-Identifier: GPL-3.0-only
"""Consistency tests across MergePlan JSON and HTML report."""

from __future__ import annotations

import json
import re

import pytest

from alscan.merge.report import render_merge_report

from tests.three_way.fixtures import (
    two_track_project, three_track_project,
    locator_project, device_heavy_project,
    with_tempo, with_time_signature, with_track_field,
    add_track, remove_track, add_locator, move_locator,
    reset_ids,
)
from tests.three_way.test_sanity import _plan_for


def _plan_to_dict(base, ours, theirs):
    plan = _plan_for(base, ours, theirs)
    return json.loads(plan.to_json())


class TestJsonRoundTrip:
    def test_counts_match_after_json_round_trip(self):
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        theirs = with_tempo(base, 132.0)
        plan = _plan_for(base, ours, theirs)
        d = json.loads(plan.to_json())
        assert d["conflict_count"] == plan.conflict_count
        assert d["warning_count"] == plan.warning_count
        assert len(d["auto_resolved"]) == len(plan.auto_resolved)
        assert len(d["conflicts"]) == len(plan.conflicts)
        assert len(d["track_changes"]) == len(plan.track_changes)
        assert len(d["locator_changes"]) == len(plan.locator_changes)
        assert len(d["identity_matches"]) == len(plan.identity_matches)
        assert len(d["proposed_track_order"]) == len(plan.proposed_track_order)

    def test_track_changes_count_consistent(self):
        base = three_track_project()
        ours = add_track(base, name="Bass", track_type="midi", clips=2)
        theirs = remove_track(base, 3)
        plan = _plan_for(base, ours, theirs)
        d = json.loads(plan.to_json())
        assert len(d["track_changes"]) == len(plan.track_changes)

    def test_locator_changes_count_consistent(self):
        base = locator_project()
        ours = move_locator(base, "Intro", 5.0)
        theirs = add_locator(base, "Drop", 41.0)
        plan = _plan_for(base, ours, theirs)
        d = json.loads(plan.to_json())
        assert len(d["locator_changes"]) == len(plan.locator_changes)

    def test_complex_scenario_counts(self):
        base = device_heavy_project()
        ours = add_track(with_tempo(base, 128.0), name="New MIDI", track_type="midi", clips=1)
        theirs = with_time_signature(remove_track(base, 2), 3, 4)
        plan = _plan_for(base, ours, theirs)
        d = json.loads(plan.to_json())
        assert d["conflict_count"] == plan.conflict_count
        assert len(d["conflicts"]) == len(plan.conflicts)
        assert len(d["auto_resolved"]) == len(plan.auto_resolved)


class TestHtmlReportConsistency:
    def test_no_external_resources(self):
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        plan = _plan_for(base, ours, base)
        html = render_merge_report(plan)
        assert "http://" not in html
        assert "https://" not in html
        assert ".css" not in html or '<link' not in html
        assert ".js" not in html or '<script src=' not in html

    def test_no_script_injection(self):
        base = two_track_project()
        ours = with_track_field(base, 1, name='<script>alert("xss")</script>')
        plan = _plan_for(base, ours, base)
        html = render_merge_report(plan)
        assert '<script>alert' not in html.lower()
        assert '&lt;script&gt;alert' in html

    def test_content_security_safe(self):
        base = locator_project()
        ours = add_locator(base, '<img src=x onerror=alert(1)>', 10.0)
        plan = _plan_for(base, ours, base)
        html = render_merge_report(plan)
        assert '<img src=' not in html.lower()
        assert '&lt;img' in html.lower()

    def test_summary_counts_match_plan(self):
        base = two_track_project()
        ours = with_tempo(base, 140.0)
        theirs = with_tempo(base, 128.0)
        plan = _plan_for(base, ours, theirs)
        html = render_merge_report(plan)
        assert f'>{plan.conflict_count}<' in html
        assert f'>{plan.warning_count}<' in html
        assert f'>{len(plan.auto_resolved)}<' in html

    def test_html_has_required_sections(self):
        base = two_track_project()
        ours = with_tempo(base, 100.0)
        plan = _plan_for(base, ours, base)
        html = render_merge_report(plan)
        assert "Summary" in html
        assert "Sources" in html
        assert "Conflicts" in html
        assert "Auto-resolved" in html
        assert "Privacy warning" in html

    def test_conflict_vs_auto_resolved_consistent(self):
        base = two_track_project()
        ours = with_tempo(base, 128.0)
        theirs = with_tempo(base, 140.0)
        plan = _plan_for(base, ours, theirs)
        conflict_items = plan.conflicts
        auto_items = plan.auto_resolved
        assert len(conflict_items) == plan.conflict_count
        assert len(auto_items) >= 0

    def test_identity_matches_present_when_expected(self):
        base = three_track_project()
        ours = with_track_field(base, 1, volume=0.5)
        plan = _plan_for(base, ours, base)
        d = json.loads(plan.to_json())
        assert len(d["identity_matches"]) >= 1

    def test_proposed_order_no_duplicates(self):
        base = three_track_project()
        ours = add_track(base, name="Extra", track_type="audio", clips=1)
        plan = _plan_for(base, ours, base)
        d = json.loads(plan.to_json())
        order_ids = []
        for entry in d.get("proposed_track_order", []):
            tr = entry.get("track", {})
            if tr and tr.get("track_id") is not None:
                order_ids.append(tr["track_id"])
        assert len(order_ids) == len(set(order_ids))

    def test_lineage_level_present(self):
        base = two_track_project()
        plan = _plan_for(base, base, base)
        d = json.loads(plan.to_json())
        assert d["lineage_confidence"] in ("strong", "plausible", "weak", "no_meaningful_relationship")
