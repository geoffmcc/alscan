# SPDX-License-Identifier: GPL-3.0-only
"""Foundation recommendation engine — evaluates which Set should be used as the merge destination."""

from __future__ import annotations

from dataclasses import dataclass, field

from alscan.merge.inputs import ThreeWayInput, LineageLevel
from alscan.merge.plan import MergePlan, Conflict, TrackChange, LocatorChange, IdentityMatch
from alscan.merge.session import FoundationRecommendation, SUPPORTED_MAJOR_VERSIONS, SUPPORTED_MINOR_VERSIONS
from alscan.versioner import Snapshot


@dataclass
class CandidateScore:
    label: str
    track_imports: int = 0
    track_deletions: int = 0
    set_level_changes: int = 0
    conflicts: int = 0
    low_confidence_matches: int = 0
    device_reviews: int = 0
    routing_reviews: int = 0
    unsupported_changes: int = 0
    lineage_confidence: str = "strong"
    state_preservation: str = "good"
    total_manual_actions: int = 0
    is_blank: bool = False
    is_advanced_only: bool = False

    def penalty_score(self) -> int:
        score = self.track_imports * 3
        score += self.track_deletions * 2
        score += self.set_level_changes * 2
        score += self.conflicts * 5
        score += self.low_confidence_matches * 3
        score += self.device_reviews * 2
        score += self.routing_reviews * 1
        score += self.unsupported_changes * 10
        if self.lineage_confidence == "weak":
            score += 15
        elif self.lineage_confidence == "no_meaningful_relationship":
            score += 30
        if self.state_preservation == "poor":
            score += 20
        if self.is_blank:
            score += 40
        return score


def recommend_foundation(
    plan: MergePlan,
    inputs: ThreeWayInput,
    scan_ours: bool = True,
    scan_theirs: bool = True,
) -> FoundationRecommendation:
    candidates: dict[str, CandidateScore] = {}

    if scan_ours:
        candidates["ours"] = _score_candidate(
            "ours",
            inputs.ours_snapshot,
            plan,
            inputs.lineage.level,
            is_blank=False,
        )
    if scan_theirs:
        candidates["theirs"] = _score_candidate(
            "theirs",
            inputs.theirs_snapshot,
            plan,
            inputs.lineage.level,
            is_blank=False,
        )

    blank = CandidateScore(
        label="Blank Set",
        is_blank=True,
        is_advanced_only=True,
        track_imports=len(plan.identity_matches) + len(plan.track_changes),
        set_level_changes=2,
        state_preservation="poor",
        conflicts=len(plan.conflicts),
        low_confidence_matches=sum(
            1 for m in plan.identity_matches if m.classification != "exact"
        ),
        device_reviews=len(plan.identity_matches),
        unsupported_changes=0,
        lineage_confidence=plan.lineage_confidence,
    )
    candidates["blank"] = blank

    sorted_candidates = sorted(
        candidates.items(),
        key=lambda item: (
            item[1].penalty_score(),
            item[1].is_advanced_only,
            item[1].label,
        ),
    )

    recommended_key = sorted_candidates[0][0]
    recommended = candidates[recommended_key]
    runner_up = candidates[sorted_candidates[1][0]] if len(sorted_candidates) > 1 else None

    confidence = _determine_confidence(recommended, runner_up)
    explanation = _build_explanation(recommended, recommended_key, runner_up, plan)

    comparisons = {}
    for key, score in candidates.items():
        comparisons[key] = {
            "label": score.label,
            "estimated_manual_actions": score.total_manual_actions,
            "conflicts": score.conflicts,
            "unsupported_operations": score.unsupported_changes,
            "risk_level": _describe_risk(score),
            "recommendation_explanation": (
                explanation if key == recommended_key else _rejection_reason(score, recommended)
            ),
            "is_blank": score.is_blank,
            "is_advanced_only": score.is_advanced_only,
            "penalty_score": score.penalty_score(),
        }

    warnings: list[str] = []
    rejected = []
    for key, score in sorted_candidates[1:]:
        rejected.append({
            "candidate": key,
            "label": score.label,
            "reason": _rejection_reason(score, recommended),
        })
        if score.state_preservation == "poor" and not score.is_blank:
            warnings.append(
                f"'{score.label}' preserves fewer project properties than the "
                f"recommended candidate."
            )

    if recommended.penalty_score() > 20:
        warnings.append(
            "No candidate avoids significant manual work. Review the comparison "
            "table carefully before proceeding."
        )

    if recommended.is_blank:
        warnings.append(
            "Blank Set is recommended only as an advanced option. A blank Set loses "
            "return tracks, master settings, routing, locators, group structures, and "
            "other project-global state. Prefer an existing Set when possible."
        )

    manual_warning = ""
    if recommended.is_blank:
        manual_warning = (
            "Starting from a blank Set requires manually recreating all global "
            "project settings and importing every track. This is the most work-intensive "
            "option and should only be used when neither branch Set is viable."
        )

    return FoundationRecommendation(
        recommended=recommended_key,
        confidence=confidence,
        explanation=explanation,
        comparisons=comparisons,
        rejected_candidates=rejected,
        warnings=warnings,
        manual_only_warning=manual_warning,
    )


def _score_candidate(
    label: str,
    snapshot: Snapshot,
    plan: MergePlan,
    lineage_level: str,
    is_blank: bool = False,
) -> CandidateScore:
    score = CandidateScore(label=label)

    score.track_imports = sum(
        1 for c in plan.track_changes
        if c.kind == "added" and c.branch != label
    )
    score.track_deletions = sum(
        1 for c in plan.track_changes
        if c.kind == "removed" and c.branch == label
    )

    score.set_level_changes = len(plan.auto_resolved)
    score.conflicts = plan.conflict_count
    score.low_confidence_matches = sum(
        1 for m in plan.identity_matches
        if m.classification != "exact"
    )
    score.device_reviews = sum(
        1 for c in plan.conflicts if c.field.startswith("track")
    )
    score.lineage_confidence = lineage_level
    score.state_preservation = "good"

    total = (
        score.track_imports * 3
        + score.track_deletions * 2
        + score.set_level_changes * 2
        + score.conflicts * 5
        + score.low_confidence_matches * 3
        + score.device_reviews * 2
        + score.routing_reviews
        + score.unsupported_changes * 10
    )
    if score.lineage_confidence == "weak":
        total += 15
    elif score.lineage_confidence == "no_meaningful_relationship":
        total += 30
    score.total_manual_actions = total

    return score


def _determine_confidence(
    best: CandidateScore,
    runner_up: CandidateScore | None,
) -> str:
    if best.is_blank:
        return "low"
    margin = (runner_up.penalty_score() - best.penalty_score()) if runner_up else 1000
    if margin >= 15:
        return "high"
    if margin >= 5:
        return "medium"
    return "low"


def _build_explanation(
    best: CandidateScore,
    key: str,
    runner_up: CandidateScore | None,
    plan: MergePlan,
) -> str:
    if best.is_blank:
        return (
            "A blank Set is the safest option when neither branch preserves enough "
            "project state, but it requires the most manual work. Use only when both "
            "other candidates have significant conflicts or structural damage."
        )
    if runner_up and best.penalty_score() == runner_up.penalty_score():
        return (
            f"'{best.label}' is recommended by tie-break. Estimated manual actions are "
            f"similar to the next candidate. Review both before deciding."
        )
    return (
        f"'{best.label}' is recommended because it requires the fewest estimated manual "
        f"actions ({best.total_manual_actions}) and preserves the most project state. "
        f"This candidate has {best.conflicts} conflict(s) and "
        f"{best.low_confidence_matches} low-confidence identity match(es)."
    )


def _rejection_reason(
    candidate: CandidateScore,
    best: CandidateScore,
) -> str:
    reasons: list[str] = []
    if candidate.conflicts > best.conflicts:
        reasons.append(f"more conflicts ({candidate.conflicts} vs {best.conflicts})")
    if candidate.total_manual_actions > best.total_manual_actions:
        reasons.append(
            f"more estimated manual actions ({candidate.total_manual_actions} vs "
            f"{best.total_manual_actions})"
        )
    if candidate.is_advanced_only != best.is_advanced_only:
        if candidate.is_advanced_only:
            reasons.append("requires advanced manual setup")
        else:
            reasons.append("advanced-only option")
    if candidate.state_preservation != best.state_preservation:
        reasons.append(f"poorer state preservation ({candidate.state_preservation})")
    if candidate.is_blank:
        reasons.append("blank Set loses all global project state")
    if not reasons:
        reasons.append("higher penalty score than recommended candidate")
    return "; ".join(reasons)


def _describe_risk(score: CandidateScore) -> str:
    p = score.penalty_score()
    if p > 40:
        return "high"
    if p > 20:
        return "medium"
    return "low"


def version_is_supported(
    major_version: str,
    minor_version: str,
) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    supported = True
    if not major_version:
        supported = False
        warnings.append(
            "Live major version could not be detected. Automatic application is disabled."
        )
        return supported, warnings
    if major_version not in SUPPORTED_MAJOR_VERSIONS:
        supported = False
        warnings.append(
            f"Live major version '{major_version}' is not in the supported set "
            f"{SUPPORTED_MAJOR_VERSIONS}. Automatic application is disabled."
        )
    if minor_version and minor_version not in SUPPORTED_MINOR_VERSIONS:
        warnings.append(
            f"Live minor version '{minor_version}' is not in the validated set "
            f"{SUPPORTED_MINOR_VERSIONS}. Some features may be disabled."
        )
    return supported, warnings
