# SPDX-License-Identifier: GPL-3.0-only
"""Merge plan data model (v2).

The AutoResolved dataclass records changes that ALScan can automatically
reconcile from the three-way analysis. It does NOT indicate that a change
was automatically *applied* — ALScan is read-only and never modifies source
.als files. In user-facing output, prefer terms such as "Automatically
reconcilable," "Suggested resolution," or "No direct conflict detected."

The AutoResolved class is retained for serialization backward compatibility
with existing v2 merge plan JSON output.
"""

from __future__ import annotations

import json
import time
import warnings
from dataclasses import dataclass, field, asdict
from typing import Literal

from alscan import __version__


@dataclass
class AutoResolved:
    """A change that ALScan can automatically reconcile from three-way analysis.

    **Deprecation note**: The name "AutoResolved" is misleading — ALScan does
    not modify .als files. The preferred term for user-facing output is
    "Automatically reconcilable" or "Suggested resolution." This class is
    retained for backward compatibility with existing v2 plan JSON.

    When generating new user-facing output, map these fields:
    - "Auto-resolved changes" → "Automatically reconcilable changes"
    - "Auto resolved" → "Suggested resolution"
    - "Auto-resolved count" → "Automatically reconcilable count"
    """
    id: str
    field: str
    base_value: object = None
    resolved_value: object = None
    resolution: str = ""
    description: str = ""


@dataclass
class Conflict:
    id: str
    field: str
    base_value: object = None
    ours_value: object = None
    theirs_value: object = None
    reason: str = ""
    risk: str = "medium"
    available_resolutions: list[str] = field(default_factory=list)
    auto_blocked: bool = True


@dataclass
class IdentityMatch:
    track_id: int = 0
    name: str = ""
    base_track_id: int = 0
    ours_track_id: int | None = None
    theirs_track_id: int | None = None
    confidence: str = "exact"
    classification: str = "exact"
    evidence: list[str] = field(default_factory=list)
    auto_resolved: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class TrackChange:
    id: str
    kind: str
    branch: str
    track_id: int | None = None
    base_track_id: int | None = None
    branch_track_id: int | None = None
    name: str = ""
    auto_resolved: bool = False
    proposed_position: dict | None = None
    details: dict = field(default_factory=dict)


@dataclass
class LocatorChange:
    id: str
    kind: str
    name: str
    branch: str = "both"
    base_time: object = None
    ours_time: object = None
    theirs_time: object = None
    auto_resolved: bool = False
    details: dict = field(default_factory=dict)


InputMode = Literal["als", "snapshot"]
LineageLevel = Literal["strong", "plausible", "weak", "no_meaningful_relationship"]


@dataclass
class MergePlan:
    document_type: str = "alscan-merge-plan"
    # v1 = Phase 1 minimal plan schema.
    # v2 = Phase 2 identity, track-change, locator-change, and ordering schema.
    format_version: str = "2"
    alscan_version: str = __version__
    created_at_utc: str = ""

    input_mode: InputMode = "als"

    sources: dict = field(default_factory=dict)
    source_structural_fingerprints: dict = field(default_factory=dict)

    supported_field_scope: list[str] = field(default_factory=lambda: [
        "tempo", "time_signature", "locators",
        "track_identity", "track_name", "track_type", "track_frozen",
        "track_color", "track_group", "track_volume", "track_devices",
        "track_clip_count", "track_sample_names",
    ])

    lineage_confidence: LineageLevel = "no_meaningful_relationship"
    conflict_count: int = 0
    warning_count: int = 0

    auto_resolved: list[AutoResolved] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    identity_matches: list[IdentityMatch] = field(default_factory=list)
    track_changes: list[TrackChange] = field(default_factory=list)
    locator_changes: list[LocatorChange] = field(default_factory=list)
    proposed_track_order: list[dict] = field(default_factory=list)

    file_differences_detected: bool = False
    warnings: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        d = asdict(self)
        d["created_at_utc"] = self.created_at_utc or _utc_now()
        return json.dumps(d, indent=2, ensure_ascii=False, allow_nan=False)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
