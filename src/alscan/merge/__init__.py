# SPDX-License-Identifier: GPL-3.0-only
"""Three-way structural merge analysis for Ableton Live projects."""

from alscan.merge.inputs import validate_three_way, normalize_snapshot_json, assess_lineage, ThreeWayInput, LineageResult, DocumentType
from alscan.merge.plan import MergePlan, Conflict, AutoResolved, IdentityMatch, TrackChange, LocatorChange
from alscan.merge.semantics import three_way_scalar, three_way_device_list, merge_sample_name_union, track_exact_identity
from alscan.merge.session import MergeSession, SourceRecord, SafetyPreflight, FoundationRecommendation
from alscan.merge.operation import MergeOperation, MergeInstruction, VerificationRule, VerificationResult, ExecutionMode, OperationState, RiskLevel, SupportClassification, ActivityCategory
from alscan.merge.manifest import MergeManifest
from alscan.merge.foundation import recommend_foundation, version_is_supported
from alscan.merge.verification import verify_destination, VerificationReport
from alscan.merge.executor import OperationExecutor, ManualInstructionExecutor, VerificationOnlyExecutor, ExecutorRegistry, get_executor_registry
from alscan.merge.guided import create_merge_session, build_merge_operations, GuidedMergeError

__all__ = [
    "validate_three_way",
    "normalize_snapshot_json",
    "assess_lineage",
    "ThreeWayInput",
    "LineageResult",
    "DocumentType",
    "MergePlan",
    "Conflict",
    "AutoResolved",
    "IdentityMatch",
    "TrackChange",
    "LocatorChange",
    "three_way_scalar",
    "three_way_device_list",
    "merge_sample_name_union",
    "track_exact_identity",
    "MergeSession",
    "SourceRecord",
    "SafetyPreflight",
    "FoundationRecommendation",
    "MergeOperation",
    "MergeInstruction",
    "VerificationRule",
    "VerificationResult",
    "ExecutionMode",
    "OperationState",
    "RiskLevel",
    "SupportClassification",
    "ActivityCategory",
    "MergeManifest",
    "recommend_foundation",
    "version_is_supported",
    "verify_destination",
    "VerificationReport",
    "OperationExecutor",
    "ManualInstructionExecutor",
    "VerificationOnlyExecutor",
    "ExecutorRegistry",
    "get_executor_registry",
    "create_merge_session",
    "build_merge_operations",
    "GuidedMergeError",
]
