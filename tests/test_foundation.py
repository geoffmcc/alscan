# SPDX-License-Identifier: GPL-3.0-only
"""Tests for foundation recommendation and version support."""

import pytest
from alscan.merge.foundation import version_is_supported
from alscan.merge.session import FoundationRecommendation


class TestVersionSupport:
    def test_supported_version(self):
        supported, warnings = version_is_supported("5", "12")
        assert supported is True
        assert warnings == []

    def test_unsupported_version(self):
        supported, warnings = version_is_supported("4", "10")
        assert supported is False
        assert len(warnings) > 0
        assert any(
            "major version '4'" in w
            for w in warnings
        )


class TestFoundationRecommendation:
    def _make_comparison(self, **overrides):
        base = {
            "label": "ours",
            "estimated_manual_actions": 5,
            "conflicts": 2,
            "unsupported_operations": 0,
            "risk_level": "low",
            "recommendation_explanation": "Preferred candidate.",
            "is_blank": False,
            "is_advanced_only": False,
            "penalty_score": 15,
        }
        base.update(overrides)
        return base

    def test_recommendation_structure(self):
        comparisons = {
            "ours": self._make_comparison(label="ours"),
            "theirs": self._make_comparison(label="theirs", penalty_score=30),
            "blank": self._make_comparison(
                label="Blank Set",
                is_blank=True,
                penalty_score=45,
            ),
        }
        rejected = [
            {"candidate": "theirs", "label": "theirs", "reason": "More conflicts."},
            {"candidate": "blank", "label": "Blank Set", "reason": "Blank set."},
        ]
        rec = FoundationRecommendation(
            recommended="ours",
            confidence="high",
            explanation="Ours is the best candidate.",
            comparisons=comparisons,
            rejected_candidates=rejected,
        )
        assert rec.recommended == "ours"
        assert rec.confidence == "high"
        assert len(rec.comparisons) == 3
        assert len(rec.rejected_candidates) == 2

    def test_comparison_has_required_fields(self):
        comparisons = {
            "ours": self._make_comparison(),
            "theirs": self._make_comparison(label="theirs", penalty_score=30),
        }
        rec = FoundationRecommendation(
            recommended="ours",
            confidence="high",
            explanation="Fine.",
            comparisons=comparisons,
            rejected_candidates=[],
        )
        required = {"estimated_manual_actions", "conflicts", "risk_level",
                     "penalty_score", "is_blank"}
        for key, comp in rec.comparisons.items():
            missing = required - set(comp.keys())
            assert not missing, f"Comparison '{key}' missing fields: {missing}"
            assert isinstance(comp["estimated_manual_actions"], int)
            assert isinstance(comp["conflicts"], int)
            assert isinstance(comp["risk_level"], str)
            assert isinstance(comp["penalty_score"], int)
            assert isinstance(comp["is_blank"], bool)

    def test_blank_set_has_manual_only_warning(self):
        rec = FoundationRecommendation(
            recommended="blank",
            confidence="medium",
            explanation="Blank is chosen as fallback.",
            comparisons={},
            rejected_candidates=[],
            manual_only_warning=(
                "Starting from a blank Set requires manually recreating all global "
                "project settings and importing every track."
            ),
        )
        assert rec.manual_only_warning != ""
        assert "manual" in rec.manual_only_warning.lower()
        assert "blank" in rec.manual_only_warning.lower()

    def test_low_confidence_when_no_clear_winner(self):
        rec = FoundationRecommendation(
            recommended="ours",
            confidence="low",
            explanation="No clear winner among candidates.",
            comparisons={},
            rejected_candidates=[],
        )
        assert rec.confidence == "low"
