# SPDX-License-Identifier: GPL-3.0-only
"""Guided merge service — converts three-way analysis into ordered merge operations."""

from __future__ import annotations

from pathlib import Path

from alscan.io_safety import capture_identity, check_aliases, are_same_file
from alscan.merge.analysis import build_merge_plan
from alscan.merge.foundation import recommend_foundation, version_is_supported
from alscan.merge.inputs import validate_three_way, ThreeWayInput
from alscan.merge.manifest import MergeManifest
from alscan.merge.operation import (
    MergeOperation,
    MergeInstruction,
    VerificationRule,
    ExecutionMode,
    OperationState,
    SupportClassification,
    RiskLevel,
    ActivityCategory,
)
from alscan.merge.plan import MergePlan
from alscan.merge.session import (
    MergeSession,
    SourceRecord,
    SafetyPreflight,
    FoundationRecommendation,
    SUPPORTED_LIVE_GENERATION,
)
from alscan.merge.executor import get_executor_registry


class GuidedMergeError(Exception):
    pass


def create_merge_session(
    base_path: str,
    ours_path: str,
    theirs_path: str,
    allow_unrelated: bool = False,
    allow_plausible: bool = False,
) -> tuple[MergeSession, MergePlan]:
    session = MergeSession()
    # Session starts in "preflight" state — no need to transition_to("preflight")

    base_p = Path(base_path).resolve()
    ours_p = Path(ours_path).resolve()
    theirs_p = Path(theirs_path).resolve()

    preflight = SafetyPreflight()
    source_paths = {"base": str(base_p), "ours": str(ours_p), "theirs": str(theirs_p)}

    for role, p in [("base", base_p), ("ours", ours_p), ("theirs", theirs_p)]:
        identity = capture_identity(p)
        src = SourceRecord(
            path=str(p),
            resolved=str(p),
            label=p.name,
            sha256=identity.sha256,
            size=identity.size,
            mtime=identity.mtime,
        )
        session.sources[role] = src

    aliases = check_aliases([base_p, ours_p, theirs_p])
    if aliases:
        details = []
        for a, b, reason in aliases:
            details.append(f"  {a} and {b} are the same file ({reason}).")
        preflight.path_collision_check = False
        preflight.path_collision_details = details
        session.safety_preflight = preflight
        session.errors.append("Source collision detected.")
        return session, MergePlan()
    preflight.path_collision_check = True

    inputs = validate_three_way(
        str(base_p), str(ours_p), str(theirs_p),
        allow_unrelated=allow_unrelated,
        allow_plausible=allow_plausible,
    )

    for role, identity in [
        ("base", inputs.base_identity),
        ("ours", inputs.ours_identity),
        ("theirs", inputs.theirs_identity),
    ]:
        if role in session.sources:
            src = session.sources[role]
            src.sha256 = identity.sha256
            src.size = identity.size

    snapshots = {
        "base": inputs.base_snapshot,
        "ours": inputs.ours_snapshot,
        "theirs": inputs.theirs_snapshot,
    }
    for role, snap in snapshots.items():
        if role in session.sources:
            src = session.sources[role]
            src.major_version = snap.major_version
            src.minor_version = snap.minor_version
            src.structural_fingerprint = snap.structural_fingerprint
            if snap.major_version and snap.minor_version:
                src.detected_live_version = (
                    f"Live {snap.major_version}.{snap.minor_version}"
                )
            else:
                src.detected_live_version = "unknown"
            supported, vw = version_is_supported(
                snap.major_version, snap.minor_version
            )
            src.version_supported = supported
            src.version_warnings = vw

    preflight.lineage_confidence = inputs.lineage.level
    preflight.warnings = inputs.lineage.warnings.copy()
    preflight.all_hashes_stable = True

    all_supported = all(
        session.sources.get(r) and session.sources[r].version_supported
        for r in ("base", "ours", "theirs")
    )
    preflight.version_check = all_supported
    if not all_supported:
        for role in ("base", "ours", "theirs"):
            src = session.sources.get(role)
            if src and not src.version_supported:
                preflight.version_details.append(
                    f"{role}: {src.label} — {src.detected_live_version} "
                    f"is not in the supported set."
                )

    session.safety_preflight = preflight
    session.transition_to("analyzing")

    plan = build_merge_plan(inputs)

    foundation = recommend_foundation(plan, inputs)
    session.foundation_recommendation = foundation
    session.selected_foundation = foundation.recommended
    session.transition_to("choosing_foundation")

    return session, plan


def build_merge_operations(
    session: MergeSession,
    plan: MergePlan,
    selected_foundation: str,
) -> list[MergeOperation]:
    operations: list[MergeOperation] = []
    op_index = 0

    def next_id() -> str:
        nonlocal op_index
        op_index += 1
        return f"op-{op_index:04d}"

    version_unsupported = any(
        not (session.sources.get(r) and session.sources[r].version_supported)
        for r in ("base", "ours", "theirs")
    )
    weak_lineage = session.safety_preflight and (
        session.safety_preflight.lineage_confidence
        in ("weak", "no_meaningful_relationship")
    )

    _add_safety_operations(operations, next_id, session, selected_foundation)

    _add_foundation_operations(
        operations, next_id, session, selected_foundation, version_unsupported
    )

    source_labels = {
        role: session.sources[role].label
        for role in ("base", "ours", "theirs")
        if role in session.sources
    }

    _add_set_level_operations(
        operations, next_id, plan, source_labels, version_unsupported, weak_lineage
    )

    _add_track_operations(
        operations, next_id, plan, selected_foundation, source_labels,
        version_unsupported, weak_lineage,
    )

    _add_device_operations(
        operations, next_id, plan, selected_foundation, source_labels,
        version_unsupported,
    )

    _add_locator_operations(
        operations, next_id, plan, selected_foundation, source_labels,
        version_unsupported, weak_lineage,
    )

    _add_finalization_operations(
        operations, next_id, session, version_unsupported,
    )

    return operations


def _add_safety_operations(
    ops: list[MergeOperation],
    next_id,
    session: MergeSession,
    foundation: str,
) -> None:
    ops.append(MergeOperation(
        operation_id=next_id(),
        category=ActivityCategory.SAFETY,
        title="Confirm source files are unchanged",
        description=(
            "Before beginning, ALScan captures the hash of every source Set. "
            "These hashes will be re-checked after the merge to verify that no "
            "source was modified during the workflow."
        ),
        required_user_decision=False,
        execution_mode=ExecutionMode.MANUAL_ONLY,
        state=OperationState.COMPLETED_MANUAL,
        support_classification=SupportClassification.NO_DIRECT_CONFLICT,
        risk_level=RiskLevel.LOW,
        instructions=MergeInstruction(
            title="Source immutability confirmed",
            description="Source hashes captured. No action required.",
            warnings=["Do not modify, rename, or delete the source Sets during the merge workflow."],
        ),
    ))

    ops.append(MergeOperation(
        operation_id=next_id(),
        category=ActivityCategory.SAFETY,
        title="Verify destination path safety",
        description=(
            "The destination Set must be a separate path from all source Sets. "
            "It must not reside inside any source project directory."
        ),
        required_user_decision=False,
        execution_mode=ExecutionMode.MANUAL_ONLY,
        state=OperationState.AWAITING_DECISION,
        support_classification=SupportClassification.MANUAL_REVIEW_REQUIRED,
        risk_level=RiskLevel.HIGH,
        instructions=MergeInstruction(
            title="Choose destination path",
            description=(
                "The destination will be created using Save Live Set As in Ableton. "
                "Choose a new or empty Project folder outside all source Project folders."
            ),
            warnings=[
                "The destination path MUST differ from Base, Ours, and Theirs.",
                "Do NOT save the destination inside any source Project folder.",
            ],
        ),
    ))


def _add_foundation_operations(
    ops: list[MergeOperation],
    next_id,
    session: MergeSession,
    foundation: str,
    version_unsupported: bool,
) -> None:
    rec = session.foundation_recommendation
    explanation = rec.explanation if rec else ""

    mode = ExecutionMode.MANUAL_ONLY
    classification = SupportClassification.RECOMMENDED_RESULT
    if version_unsupported:
        classification = SupportClassification.UNSUPPORTED_FOR_AUTO

    source_label = ""
    if foundation in session.sources:
        source_label = session.sources[foundation].label

    ops.append(MergeOperation(
        operation_id=next_id(),
        category=ActivityCategory.FOUNDATION,
        title=f"Use '{source_label or foundation}' as the merge foundation",
        description=(
            f"ALScan recommends '{foundation}' as the foundation Set. "
            f"Open this file in Ableton Live and use Save Live Set As "
            f"to create the destination Set."
        ),
        recommended_result=foundation,
        recommendation_rationale=explanation,
        confidence=rec.confidence if rec else "medium",
        source_branch=foundation,
        required_user_decision=True,
        selected_user_decision=foundation,
        execution_mode=mode,
        state=OperationState.ACCEPTED,
        support_classification=classification,
        risk_level=RiskLevel.LOW,
        instructions=MergeInstruction(
            title=f"Open {foundation} in Ableton Live",
            description=(
                f"Open the {foundation} Set ({source_label}) in Ableton Live. "
                f"Do not make changes yet. You will save it as the destination "
                f"in the next step."
            ),
            source_set_label=source_label,
        ),
    ))


def _add_set_level_operations(
    ops: list[MergeOperation],
    next_id,
    plan: MergePlan,
    source_labels: dict[str, str],
    version_unsupported: bool,
    weak_lineage: bool,
) -> None:
    mode = ExecutionMode.MANUAL_ONLY
    if version_unsupported or weak_lineage:
        mode = ExecutionMode.UNSUPPORTED

    for auto in plan.auto_resolved:
        field = auto.field
        category = ActivityCategory.SET_LEVEL
        title = f"Set {field.replace('_', ' ')}: use value from analysis"
        ops.append(MergeOperation(
            operation_id=next_id(),
            category=category,
            title=title,
            description=auto.description,
            base_value=auto.base_value,
            recommended_result=auto.resolved_value,
            recommendation_rationale=auto.resolution,
            confidence="high",
            source_branch=(
                "ours" if "ours" in auto.resolution.lower() else "theirs"
                if "theirs" in auto.resolution.lower() else "both"
            ),
            required_user_decision=False,
            execution_mode=mode,
            state=OperationState.ACCEPTED,
            support_classification=SupportClassification.AUTOMATICALLY_RECONCILABLE,
            risk_level=RiskLevel.LOW,
            instructions=MergeInstruction(
                title=f"Set {field.replace('_', ' ')}",
                description=(
                    f"Set the {field.replace('_', ' ')} to {auto.resolved_value} "
                    f"in the Ableton Live destination project."
                ),
                expected_value=auto.resolved_value,
                verification_hint=f"Check that {field} equals {auto.resolved_value}.",
            ),
            verification_rule=VerificationRule(
                rule_id=f"verify-{auto.id}",
                description=f"Verify {field} equals {auto.resolved_value}",
                expected=auto.resolved_value,
                field_path=field,
                comparison="equals",
            ),
        ))


def _add_track_operations(
    ops: list[MergeOperation],
    next_id,
    plan: MergePlan,
    foundation: str,
    source_labels: dict[str, str],
    version_unsupported: bool,
    weak_lineage: bool,
) -> None:
    mode = ExecutionMode.MANUAL_ONLY
    if version_unsupported:
        mode = ExecutionMode.UNSUPPORTED

    for tc in plan.track_changes:
        category: ActivityCategory
        title: str
        branch = tc.branch
        if tc.kind == "added":
            category = ActivityCategory.TRACK_ADDITION
            title = f"Add track '{tc.name}' from {branch} branch"
        elif tc.kind == "removed":
            category = ActivityCategory.TRACK_REMOVAL
            title = f"Remove track '{tc.name}' (deleted in {branch})"
        else:
            category = ActivityCategory.TRACK_MODIFICATION
            title = f"Modify track '{tc.name}'"

        source_label = source_labels.get(branch, "")
        source_folder = ""

        auto_resolved = tc.auto_resolved
        is_identity_sensitive = not auto_resolved
        if weak_lineage and is_identity_sensitive:
            mode = ExecutionMode.UNSUPPORTED

        ops.append(MergeOperation(
            operation_id=next_id(),
            category=category,
            title=title,
            description=f"Track change: {tc.kind} by {branch} branch.",
            affected_track_name=tc.name,
            base_track_id=tc.base_track_id,
            branch_track_id=tc.branch_track_id,
            recommendation_rationale=(
                "Same change in both branches; no conflict."
                if auto_resolved else
                "Manual review required — track identity or change is ambiguous."
            ),
            confidence=(
                "high" if auto_resolved else
                "medium" if "plausible" in str(tc.details) else "low"
            ),
            source_branch=branch,
            required_user_decision=not auto_resolved,
            execution_mode=mode,
            state=(
                OperationState.ACCEPTED if auto_resolved
                else OperationState.AWAITING_DECISION
            ),
            support_classification=(
                SupportClassification.AUTOMATICALLY_RECONCILABLE
                if auto_resolved else
                SupportClassification.MANUAL_REVIEW_REQUIRED
            ),
            risk_level=RiskLevel.LOW if auto_resolved else RiskLevel.MEDIUM,
            instructions=MergeInstruction(
                title=title,
                description=_track_instruction_text(tc, source_label, foundation),
                source_set_label=source_label,
                source_track_name=tc.name,
                base_track_id=tc.base_track_id,
                branch_track_id=tc.branch_track_id,
                destination_position=tc.proposed_position,
                warnings=(
                    ["Track identity is not exact. Verify this is the correct track before importing."]
                    if not auto_resolved else []
                ),
                verification_hint=_track_verification_hint(tc),
            ),
            verification_rule=VerificationRule(
                rule_id=f"verify-track-{tc.id}",
                description=f"Verify track '{tc.name}' {tc.kind}",
                expected=tc.name,
                field_path=f"tracks.{tc.name}",
                comparison="track_operation",
            ),
            warnings=tc.details.get("warnings", []) if isinstance(tc.details, dict) else [],
        ))


def _track_instruction_text(tc, source_label: str, foundation: str) -> str:
    kind = tc.kind
    name = tc.name
    branch = tc.branch
    if kind == "added":
        if branch == "both":
            return (
                f"The same track '{name}' was added in both branches. "
                f"Open the source Set ('{source_label or branch}'), locate "
                f"'{name}', and drag it into the destination Set. "
                f"Position it after the preceding base-derived track."
            )
        return (
            f"Track '{name}' was added in the {branch} branch. "
            f"Open the {branch} source Set ('{source_label}'), locate "
            f"'{name}', and drag or copy it into the destination Set."
        )
    elif kind == "removed":
        return (
            f"Track '{name}' was removed in the {branch} branch. "
            f"In the destination Set, delete track '{name}'."
        )
    else:
        return (
            f"Track '{name}' was modified in the {branch} branch. "
            f"Review '{name}' in the destination Set and apply the "
            f"corresponding changes from the {branch} source Set."
        )


def _track_verification_hint(tc) -> str:
    kind = tc.kind
    name = tc.name
    if kind == "added":
        return f"ALScan will verify that track '{name}' exists in the destination."
    elif kind == "removed":
        return f"ALScan will verify that track '{name}' is absent from the destination."
    return f"ALScan will compare track '{name}' metadata against the expected values."


def _add_device_operations(
    ops: list[MergeOperation],
    next_id,
    plan: MergePlan,
    foundation: str,
    source_labels: dict[str, str],
    version_unsupported: bool,
) -> None:
    for conflict in plan.conflicts:
        if "device" in conflict.field.lower():
            ops.append(MergeOperation(
                operation_id=next_id(),
                category=ActivityCategory.DEVICE_REVIEW,
                title=f"Review device changes: {conflict.field}",
                description=conflict.reason,
                base_value=conflict.base_value,
                ours_value=conflict.ours_value,
                theirs_value=conflict.theirs_value,
                recommendation_rationale="Device changes must be reviewed manually. ALScan cannot reconstruct device internals.",
                confidence="low",
                required_user_decision=True,
                execution_mode=ExecutionMode.MANUAL_ONLY,
                state=OperationState.AWAITING_DECISION,
                support_classification=SupportClassification.MANUAL_REVIEW_REQUIRED,
                risk_level=RiskLevel.MEDIUM,
                instructions=MergeInstruction(
                    title="Review device chain",
                    description=(
                        "Device chains differ between branches. Open both source "
                        "Sets in Ableton, compare the device chains on the affected "
                        "track, and manually replicate the desired configuration "
                        "in the destination Set."
                    ),
                    warnings=[
                        "Device parameter values, automation, and plugin state "
                        "are not modeled. Review these in Ableton Live directly."
                    ],
                ),
                warnings=["Device internals require manual review in Ableton Live."],
            ))


def _add_locator_operations(
    ops: list[MergeOperation],
    next_id,
    plan: MergePlan,
    foundation: str,
    source_labels: dict[str, str],
    version_unsupported: bool,
    weak_lineage: bool,
) -> None:
    mode = ExecutionMode.MANUAL_ONLY
    if version_unsupported:
        mode = ExecutionMode.UNSUPPORTED

    for lc in plan.locator_changes:
        auto_resolved = lc.auto_resolved
        branch = lc.branch
        source_label = source_labels.get(branch, "")

        if lc.kind == "added":
            category = ActivityCategory.LOCATOR
            title = f"Add locator '{lc.name}' at {lc.ours_time or lc.theirs_time}"
        elif lc.kind == "removed":
            category = ActivityCategory.LOCATOR
            title = f"Remove locator '{lc.name}'"
        else:
            category = ActivityCategory.LOCATOR
            title = f"Move locator '{lc.name}' to {lc.ours_time or lc.theirs_time}"

        ops.append(MergeOperation(
            operation_id=next_id(),
            category=category,
            title=title,
            description=f"Locator change: {lc.kind} by {branch} branch.",
            affected_locator_name=lc.name,
            base_value=lc.base_time,
            ours_value=lc.ours_time,
            theirs_value=lc.theirs_time,
            recommended_result=lc.ours_time or lc.theirs_time,
            recommendation_rationale=(
                "Convergent or single-branch change; no conflict."
                if auto_resolved else
                "Locator change requires manual review."
            ),
            confidence="high" if auto_resolved else "medium",
            source_branch=branch,
            required_user_decision=not auto_resolved,
            execution_mode=mode,
            state=(
                OperationState.ACCEPTED if auto_resolved
                else OperationState.AWAITING_DECISION
            ),
            support_classification=(
                SupportClassification.AUTOMATICALLY_RECONCILABLE
                if auto_resolved else
                SupportClassification.MANUAL_REVIEW_REQUIRED
            ),
            risk_level=RiskLevel.LOW,
            instructions=MergeInstruction(
                title=title,
                description=_locator_instruction_text(lc, source_label),
                source_set_label=source_label,
                verification_hint=f"Verify locator '{lc.name}' at expected position.",
            ),
            verification_rule=VerificationRule(
                rule_id=f"verify-locator-{lc.id}",
                description=f"Verify locator '{lc.name}' {lc.kind}",
                expected=lc.ours_time or lc.theirs_time,
                field_path=f"locators.{lc.name}",
                comparison="locator_operation",
            ),
        ))


def _locator_instruction_text(lc, source_label: str) -> str:
    kind = lc.kind
    name = lc.name
    branch = lc.branch
    if kind == "added":
        return (
            f"Add a locator named '{name}' at position {lc.ours_time or lc.theirs_time} "
            f"in the destination Set. This locator was added in the {branch} branch."
        )
    elif kind == "removed":
        return (
            f"Delete the locator named '{name}' from the destination Set. "
            f"It was removed in the {branch} branch."
        )
    return (
        f"Move the locator '{name}' to position {lc.ours_time or lc.theirs_time} "
        f"in the destination Set."
    )


def _add_finalization_operations(
    ops: list[MergeOperation],
    next_id,
    session: MergeSession,
    version_unsupported: bool,
) -> None:
    ops.append(MergeOperation(
        operation_id=next_id(),
        category=ActivityCategory.FINALIZATION,
        title="Collect All and Save",
        description=(
            "In Ableton Live, use File > Collect All and Save to ensure all "
            "referenced samples and media are copied into the destination Project. "
            "Then save and close the Set."
        ),
        required_user_decision=False,
        execution_mode=ExecutionMode.MANUAL_ONLY,
        state=OperationState.AWAITING_DECISION,
        support_classification=SupportClassification.NO_DIRECT_CONFLICT,
        risk_level=RiskLevel.LOW,
        instructions=MergeInstruction(
            title="Collect All and Save",
            description=(
                "1. In Ableton Live, select File > Collect All and Save.\n"
                "2. Ensure all media files are collected.\n"
                "3. Save the Set (Ctrl+S / Cmd+S).\n"
                "4. Close the Set.\n"
                "5. Reopen the Set to verify it loads correctly."
            ),
            warnings=[
                "Large sample libraries or multisample content may take time to collect.",
                "Max for Live devices may reference external files.",
            ],
        ),
    ))

    ops.append(MergeOperation(
        operation_id=next_id(),
        category=ActivityCategory.FINALIZATION,
        title="ALScan final verification",
        description=(
            "ALScan will scan the destination Set and compare it against the "
            "accepted merge plan. Any mismatches will be reported with clear "
            "next steps."
        ),
        required_user_decision=False,
        execution_mode=ExecutionMode.MANUAL_ONLY,
        state=OperationState.AWAITING_DECISION,
        support_classification=SupportClassification.NO_DIRECT_CONFLICT,
        risk_level=RiskLevel.LOW,
        instructions=MergeInstruction(
            title="Run verification",
            description=(
                "After all manual steps are completed and the destination Set "
                "is saved, run the verification command to confirm the result."
            ),
        ),
    ))

    ops.append(MergeOperation(
        operation_id=next_id(),
        category=ActivityCategory.FINALIZATION,
        title="Re-check source file hashes",
        description=(
            "ALScan re-reads all source files and verifies that their hashes "
            "match the values captured at the start of the workflow."
        ),
        required_user_decision=False,
        execution_mode=ExecutionMode.MANUAL_ONLY,
        state=OperationState.AWAITING_DECISION,
        support_classification=SupportClassification.NO_DIRECT_CONFLICT,
        risk_level=RiskLevel.LOW,
        instructions=MergeInstruction(
            title="Source hash verification",
            description=(
                "Source hashes are automatically compared against the initial "
                "capture. No user action is required for this step."
            ),
        ),
    ))
