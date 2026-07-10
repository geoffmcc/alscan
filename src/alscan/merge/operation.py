# SPDX-License-Identifier: GPL-3.0-only
"""Merge operation domain model — individual operations in a guided merge plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ExecutionMode(Enum):
    MANUAL_ONLY = "manual_only"
    AUTOMATABLE_BUT_DISABLED = "automatable_but_disabled"
    AUTOMATIC_EXPERIMENTAL = "automatic_experimental"
    AUTOMATIC_SUPPORTED = "automatic_supported"
    UNSUPPORTED = "unsupported"


class OperationState(Enum):
    PROPOSED = "proposed"
    AWAITING_DECISION = "awaiting_decision"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED_MANUAL = "completed_manual"
    COMPLETED_AUTOMATIC = "completed_automatic"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    BLOCKED = "blocked"
    UNSUPPORTED = "unsupported"


class RiskLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SupportClassification(Enum):
    AUTOMATICALLY_RECONCILABLE = "automatically_reconcilable"
    SUGGESTED_RESOLUTION = "suggested_resolution"
    NO_DIRECT_CONFLICT = "no_direct_conflict"
    RECOMMENDED_RESULT = "recommended_result"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    UNSUPPORTED_FOR_AUTO = "unsupported_for_automatic_application"


class ActivityCategory(Enum):
    SAFETY = "safety"
    FOUNDATION = "foundation"
    SET_LEVEL = "set_level"
    TRACK_ADDITION = "track_addition"
    TRACK_REMOVAL = "track_removal"
    TRACK_MODIFICATION = "track_modification"
    TRACK_ORDERING = "track_ordering"
    DEVICE_REVIEW = "device_review"
    CLIP_SAMPLE = "clip_sample"
    ROUTING = "routing"
    LOCATOR = "locator"
    FINALIZATION = "finalization"
    VERIFICATION = "verification"


VALID_STATE_TRANSITIONS = {
    OperationState.PROPOSED: {
        OperationState.AWAITING_DECISION,
        OperationState.ACCEPTED,
        OperationState.REJECTED,
        OperationState.DEFERRED,
        OperationState.UNSUPPORTED,
    },
    OperationState.AWAITING_DECISION: {
        OperationState.ACCEPTED,
        OperationState.REJECTED,
        OperationState.DEFERRED,
    },
    OperationState.ACCEPTED: {
        OperationState.READY,
        OperationState.BLOCKED,
    },
    OperationState.REJECTED: set(),
    OperationState.DEFERRED: {
        OperationState.AWAITING_DECISION,
    },
    OperationState.READY: {
        OperationState.IN_PROGRESS,
        OperationState.BLOCKED,
    },
    OperationState.IN_PROGRESS: {
        OperationState.COMPLETED_MANUAL,
        OperationState.COMPLETED_AUTOMATIC,
        OperationState.BLOCKED,
    },
    OperationState.COMPLETED_MANUAL: {
        OperationState.VERIFICATION_PASSED,
        OperationState.VERIFICATION_FAILED,
    },
    OperationState.COMPLETED_AUTOMATIC: {
        OperationState.VERIFICATION_PASSED,
        OperationState.VERIFICATION_FAILED,
    },
    OperationState.VERIFICATION_PASSED: set(),
    OperationState.VERIFICATION_FAILED: {
        OperationState.IN_PROGRESS,
        OperationState.BLOCKED,
    },
    OperationState.BLOCKED: {
        OperationState.AWAITING_DECISION,
        OperationState.READY,
    },
    OperationState.UNSUPPORTED: set(),
}


@dataclass
class VerificationRule:
    rule_id: str
    description: str
    expected: object
    field_path: str = ""
    comparison: str = "equals"
    tolerance: float | None = None

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


@dataclass
class VerificationResult:
    status: str = "unverifiable"
    expected: object = None
    observed: object = None
    explanation: str = ""
    likely_cause: str = ""
    next_manual_step: str = ""
    timestamp_utc: str = ""


@dataclass
class MergeInstruction:
    title: str = ""
    description: str = ""
    source_set_label: str = ""
    source_project_folder: str = ""
    source_track_name: str = ""
    source_track_type: str = ""
    base_track_id: int | None = None
    branch_track_id: int | None = None
    destination_position: dict | None = None
    expected_value: object = None
    expected_device_name: str = ""
    expected_sample_name: str = ""
    steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    verification_hint: str = ""


@dataclass
class MergeOperation:
    operation_id: str = ""
    category: ActivityCategory = ActivityCategory.SAFETY
    title: str = ""
    description: str = ""
    affected_object_type: str = ""
    affected_track_name: str = ""
    affected_locator_name: str = ""

    base_value: object = None
    ours_value: object = None
    theirs_value: object = None
    recommended_result: object = None
    recommendation_rationale: str = ""
    confidence: str = "medium"

    risk_level: RiskLevel = RiskLevel.LOW
    support_classification: SupportClassification = SupportClassification.MANUAL_REVIEW_REQUIRED
    required_user_decision: bool = True
    selected_user_decision: str = ""

    execution_mode: ExecutionMode = ExecutionMode.MANUAL_ONLY
    state: OperationState = OperationState.PROPOSED

    instructions: MergeInstruction | None = None
    verification_rule: VerificationRule | None = None
    verification_result: VerificationResult | None = None

    completion_status: str = "pending"
    warnings: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    source_branch: str = ""
    destination_expectation: str = ""

    base_track_id: int | None = None
    branch_track_id: int | None = None
    ours_track_id: int | None = None
    theirs_track_id: int | None = None
    affected_track_type: str = ""

    def transition_to(self, new_state: OperationState) -> None:
        if new_state not in VALID_STATE_TRANSITIONS.get(self.state, set()):
            raise ValueError(
                f"Invalid state transition: {self.state.value} -> {new_state.value}"
            )
        self.state = new_state

    def can_automate(self) -> bool:
        return self.execution_mode in {
            ExecutionMode.AUTOMATIC_EXPERIMENTAL,
            ExecutionMode.AUTOMATIC_SUPPORTED,
        }

    def is_completed(self) -> bool:
        return self.state in {
            OperationState.COMPLETED_MANUAL,
            OperationState.COMPLETED_AUTOMATIC,
        }

    def is_verified(self) -> bool:
        return self.state == OperationState.VERIFICATION_PASSED

    def has_verification_result(self) -> bool:
        return self.state in {
            OperationState.VERIFICATION_PASSED,
            OperationState.VERIFICATION_FAILED,
        }

    def to_dict(self) -> dict:
        from dataclasses import asdict
        result = asdict(self)
        result["category"] = self.category.value
        result["risk_level"] = self.risk_level.value
        result["support_classification"] = self.support_classification.value
        result["execution_mode"] = self.execution_mode.value
        result["state"] = self.state.value
        return result
