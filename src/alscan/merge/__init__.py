# SPDX-License-Identifier: GPL-3.0-only
"""Three-way structural merge analysis for Ableton Live projects."""

from alscan.merge.inputs import validate_three_way, normalize_snapshot_json, assess_lineage, ThreeWayInput, LineageResult, DocumentType
from alscan.merge.plan import MergePlan, Conflict, AutoResolved, IdentityMatch
from alscan.merge.semantics import three_way_scalar, three_way_device_list, merge_sample_name_union, track_exact_identity

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
    "three_way_scalar",
    "three_way_device_list",
    "merge_sample_name_union",
    "track_exact_identity",
]
