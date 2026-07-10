# SPDX-License-Identifier: GPL-3.0-only
"""Merge session domain model — durable session tracking for guided merge workflow."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

SUPPORTED_LIVE_GENERATION = "Live 12"
SUPPORTED_MAJOR_VERSIONS = {"5"}
SUPPORTED_MINOR_VERSIONS = {"12", "11", "10"}

WORKFLOW_STATES = frozenset({
    "preflight",
    "analyzing",
    "choosing_foundation",
    "reviewing_decisions",
    "preparing_destination",
    "performing_merge",
    "collect_and_save",
    "verifying",
    "completed",
    "cancelled",
    "error",
})

VERIFICATION_STATES = frozenset({
    "not_started",
    "in_progress",
    "passed",
    "failed",
    "deferred",
})

COMPLETION_STATES = frozenset({
    "incomplete",
    "completed_verified",
    "completed_unverifiable",
    "completed_with_warnings",
    "abandoned",
})

SESSION_VALID_TRANSITIONS: dict[str, set[str]] = {
    "preflight": {"analyzing"},
    "analyzing": {"choosing_foundation", "error"},
    "choosing_foundation": {"reviewing_decisions", "error"},
    "reviewing_decisions": {"preparing_destination", "error"},
    "preparing_destination": {"performing_merge", "error"},
    "performing_merge": {"collect_and_save", "error"},
    "collect_and_save": {"verifying", "error"},
    "verifying": {"completed", "error"},
    "completed": set(),
    "cancelled": set(),
    "error": {"preflight"},
}


@dataclass
class SourceRecord:
    path: str
    resolved: str = ""
    label: str = ""
    sha256: str = ""
    size: int = 0
    mtime: float = 0.0
    detected_live_version: str = ""
    major_version: str = ""
    minor_version: str = ""
    structural_fingerprint: str = ""
    version_supported: bool = True
    version_warnings: list[str] = field(default_factory=list)


@dataclass
class SafetyPreflight:
    captured_at_utc: str = ""
    sources: dict[str, SourceRecord] = field(default_factory=dict)
    path_collision_check: bool = False
    path_collision_details: list[str] = field(default_factory=list)
    all_hashes_stable: bool = False
    hash_stability_details: list[str] = field(default_factory=list)
    version_check: bool = False
    version_details: list[str] = field(default_factory=list)
    lineage_confidence: str = "no_meaningful_relationship"
    accepted_risk_overrides: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def passed(self) -> bool:
        # Version check is skipped when there is no meaningful relationship
        # between the source files (unrelated files can't be validated against
        # a supported version policy).
        return (
            self.path_collision_check
            and self.all_hashes_stable
            and (self.version_check or self.lineage_confidence == "no_meaningful_relationship")
        )


@dataclass
class FoundationRecommendation:
    recommended: str = ""
    confidence: str = "low"
    explanation: str = ""
    comparisons: dict[str, dict[str, object]] = field(default_factory=dict)
    rejected_candidates: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manual_only_warning: str = ""


@dataclass
class MergeSession:
    session_id: str = ""
    created_at_utc: str = ""
    alscan_version: str = ""
    supported_live_generation: str = SUPPORTED_LIVE_GENERATION

    sources: dict[str, SourceRecord] = field(default_factory=dict)
    safety_preflight: SafetyPreflight | None = None
    foundation_recommendation: FoundationRecommendation | None = None
    selected_foundation: str = ""
    destination_path: str = ""

    workflow_state: str = "preflight"
    verification_status: str = "not_started"
    completion_state: str = "incomplete"

    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.session_id:
            self.session_id = uuid.uuid4().hex[:16]
        if not self.created_at_utc:
            self.created_at_utc = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

    def transition_to(self, new_state: str) -> None:
        if new_state not in WORKFLOW_STATES:
            raise ValueError(
                f"Invalid workflow state '{new_state}'. "
                f"Valid states: {sorted(WORKFLOW_STATES)}"
            )
        allowed = SESSION_VALID_TRANSITIONS.get(self.workflow_state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid session state transition: "
                f"'{self.workflow_state}' -> '{new_state}'. "
                f"Allowed transitions from '{self.workflow_state}': "
                f"{sorted(allowed)}"
            )
        self.workflow_state = new_state

    def is_active(self) -> bool:
        return self.workflow_state not in {"completed", "cancelled", "error"}

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)
