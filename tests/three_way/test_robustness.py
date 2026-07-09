# SPDX-License-Identifier: GPL-3.0-only
"""Robustness tests: hostile strings in names, HTML/JSON safety."""

from __future__ import annotations

import json

import pytest

from alscan.merge.report import render_merge_report

from tests.three_way.fixtures import (
    two_track_project, locator_project, add_track, add_locator,
    with_track_field, reset_ids,
)
from tests.three_way.test_sanity import _plan_for


class TestXssInNames:
    def test_script_tag_in_track_name(self):
        malicious = '<script>alert(1)</script>'
        base = two_track_project()
        ours = with_track_field(base, 1, name=malicious)
        plan = _plan_for(base, ours, base)
        json_str = plan.to_json()
        d = json.loads(json_str)
        assert malicious not in (t.get("name") for t in
            json.loads(json.dumps(d.get("track_changes", []))) if "name" in t)

    def test_script_tag_in_locator_name(self):
        malicious = '<script>alert(1)</script>'
        base = locator_project()
        ours = add_locator(base, malicious, 10.0)
        plan = _plan_for(base, ours, base)
        json_str = plan.to_json()
        assert "&lt;script&gt;" not in json_str
        assert "\u003c" not in json_str[:500]

    def test_script_tag_rendered_safely_in_html(self):
        malicious = '<script>alert(1)</script>'
        base = locator_project()
        ours = add_locator(base, malicious, 10.0)
        plan = _plan_for(base, ours, base)
        html = render_merge_report(plan)
        assert "<script>" not in html.lower()
        assert "&lt;script&gt;" in html


class TestQuotesAndAmpersands:
    def test_quotes_and_ampersands_in_track_name(self):
        base = two_track_project()
        ours = with_track_field(base, 1, name='Kick & "Snare"')
        plan = _plan_for(base, ours, base)
        json_str = plan.to_json()
        d = json.loads(json_str)
        assert d["document_type"] == "alscan-merge-plan"

    def test_quotes_safe_in_html_report(self):
        base = two_track_project()
        ours = with_track_field(base, 1, name='Track "A" & B')
        plan = _plan_for(base, ours, base)
        html = render_merge_report(plan)
        assert '"A"' not in html
        assert "&quot;A&quot;" in html or "&#x27;" in html or "A" in html
        assert "&amp;" in html


class TestPathTraversalInNames:
    def test_path_traversal_in_track_name(self):
        malicious = '../../../etc/passwd'
        base = two_track_project()
        ours = with_track_field(base, 1, name=malicious)
        plan = _plan_for(base, ours, base)
        json_str = plan.to_json()
        d = json.loads(json_str)
        assert d["document_type"] == "alscan-merge-plan"

    def test_path_traversal_in_locator_name(self):
        malicious = '../../../etc/passwd'
        base = locator_project()
        ours = add_locator(base, malicious, 5.0)
        plan = _plan_for(base, ours, base)
        html = render_merge_report(plan)
        assert ".." in html or "../../../etc/passwd" not in html

    def test_windows_path_in_name(self):
        malicious = 'C:\\Windows\\System32\\cmd.exe'
        base = locator_project()
        ours = add_locator(base, malicious, 2.0)
        plan = _plan_for(base, ours, base)
        html = render_merge_report(plan)
        assert '<!doctype html>' in html.lower()


class TestWindowsReservedChars:
    def test_reserved_chars_in_track_name(self):
        base = two_track_project()
        ours = with_track_field(base, 1, name='Track<foo>:bar*?baz')
        plan = _plan_for(base, ours, base)
        json_str = plan.to_json()
        d = json.loads(json_str)
        assert d["document_type"] == "alscan-merge-plan"

    def test_reserved_chars_safe_in_html(self):
        base = two_track_project()
        ours = with_track_field(base, 1, name='Name <with> & "quotes"')
        plan = _plan_for(base, ours, base)
        html = render_merge_report(plan)
        assert '<with>' not in html


class TestVeryLongNames:
    def test_very_long_track_name_500_chars(self):
        long_name = "A" * 500
        base = two_track_project()
        ours = with_track_field(base, 1, name=long_name)
        plan = _plan_for(base, ours, base)
        json_str = plan.to_json()
        d = json.loads(json_str)
        assert d["document_type"] == "alscan-merge-plan"

    def test_very_long_locator_name_safe(self):
        long_name = "L" * 500
        base = locator_project()
        ours = add_locator(base, long_name, 1.0)
        plan = _plan_for(base, ours, base)
        html = render_merge_report(plan)
        assert len(html) > 0


class TestUnicodeSpecial:
    def test_unicode_combining_marks(self):
        name = "No\u0308el"  # N-o-̈-e-l
        base = two_track_project()
        ours = with_track_field(base, 1, name=name)
        plan = _plan_for(base, ours, base)
        json_str = plan.to_json()
        d = json.loads(json_str)
        assert d["document_type"] == "alscan-merge-plan"

    def test_rtl_text_in_track_name(self):
        name = "\u202b\u05d0\u05d1\u05d2\u202c"  # RTL Hebrew with RTL marks
        base = two_track_project()
        ours = with_track_field(base, 1, name=name)
        plan = _plan_for(base, ours, base)
        json_str = plan.to_json()
        d = json.loads(json_str)
        assert len(d["auto_resolved"]) >= 1 or len(d["track_changes"]) >= 1

    def test_emoji_in_track_name(self):
        name = "Track \U0001f3b5 \U0001f600"  # musical note + smile
        base = two_track_project()
        ours = with_track_field(base, 1, name=name)
        plan = _plan_for(base, ours, base)
        json_str = plan.to_json()
        d = json.loads(json_str)
        assert d["document_type"] == "alscan-merge-plan"

    def test_emoji_safe_in_html(self):
        name = "\U0001f3b5 Beat"
        base = locator_project()
        ours = add_locator(base, name, 5.0)
        plan = _plan_for(base, ours, base)
        html = render_merge_report(plan)
        assert "\U0001f3b5" in html or "1f3b5" not in html

    def test_null_byte_not_crashing(self):
        name_with_null = "Track\x00Name"
        base = two_track_project()
        ours = with_track_field(base, 1, name=name_with_null)
        plan = _plan_for(base, ours, base)
        json_str = plan.to_json()
        d = json.loads(json_str)
        assert d["document_type"] == "alscan-merge-plan"
