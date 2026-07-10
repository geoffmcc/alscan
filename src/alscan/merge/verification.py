# SPDX-License-Identifier: GPL-3.0-only
"""Destination verification engine — verifies a destination .als against an accepted merge plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alscan.io_safety import capture_identity, are_same_file
from alscan.merge.operation import (
    MergeOperation,
    OperationState,
    VerificationResult,
    ActivityCategory,
)
from alscan.merge.session import MergeSession, SourceRecord
from alscan.parser import parse_als
from alscan.versioner import build_snapshot, Snapshot


@dataclass
class VerificationReport:
    destination_path: str = ""
    total_operations: int = 0
    passed: int = 0
    failed: int = 0
    partial: int = 0
    unverifiable: int = 0
    blocked: int = 0
    source_hashes_stable: bool = False
    source_hash_details: list[dict] = field(default_factory=list)
    results: list[VerificationResult] = field(default_factory=list)
    operation_results: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def success_rate(self) -> float:
        verifiable = self.passed + self.failed + self.partial
        if verifiable == 0:
            return 0.0
        return self.passed / verifiable


def verify_destination(
    destination_path: str | Path,
    manifest: Any,
    source_paths: dict[str, str],
    source_hashes: dict[str, str],
) -> VerificationReport:
    dest_p = Path(destination_path).resolve()
    report = VerificationReport(destination_path=str(dest_p))

    if not dest_p.exists():
        report.errors.append(f"Destination file not found: {dest_p}")
        return report

    if not dest_p.suffix.lower() == ".als":
        report.errors.append(
            f"Destination is not an .als file: {dest_p}"
        )
        return report

    for role, spath in source_paths.items():
        src_p = Path(spath)
        if are_same_file(dest_p, src_p):
            report.errors.append(
                f"Destination is the same file as source '{role}': {spath}"
            )
            return report

    try:
        dest_proj = parse_als(dest_p)
        dest_snap = build_snapshot(dest_proj)
    except Exception as e:
        report.errors.append(f"Failed to parse destination: {e}")
        return report

    source_problems = _check_source_stability(source_paths, source_hashes)
    report.source_hashes_stable = len(source_problems) == 0
    report.source_hash_details = source_problems

    operations = _extract_operations(manifest)
    report.total_operations = len(operations)

    for op in operations:
        if op.state in {OperationState.REJECTED, OperationState.DEFERRED}:
            continue
        result = _verify_operation(op, dest_snap)
        op.verification_result = result
        report.results.append(result)
        report.operation_results[op.operation_id] = result.status
        if result.status == "pass":
            report.passed += 1
        elif result.status == "fail":
            report.failed += 1
        elif result.status == "partial":
            report.partial += 1
        elif result.status == "blocked":
            report.blocked += 1
        else:
            report.unverifiable += 1

    return report


def _extract_operations(manifest: Any) -> list[MergeOperation]:
    if hasattr(manifest, "get_operations"):
        return manifest.get_operations()
    ops = getattr(manifest, "operations", [])
    if isinstance(ops, list):
        return [MergeOperation(**o) if isinstance(o, dict) else o for o in ops]
    return []


def _check_source_stability(
    source_paths: dict[str, str],
    captured_hashes: dict[str, str],
) -> list[dict]:
    problems = []
    for role, spath in source_paths.items():
        try:
            identity = capture_identity(spath)
        except Exception as e:
            problems.append({
                "role": role,
                "path": spath,
                "status": "unreadable",
                "detail": str(e),
            })
            continue
        expected = captured_hashes.get(role, "")
        if not expected:
            problems.append({
                "role": role,
                "path": spath,
                "status": "no_captured_hash",
                "sha256": identity.sha256[:16],
            })
        elif identity.sha256 != expected:
            problems.append({
                "role": role,
                "path": spath,
                "status": "changed",
                "expected_sha256": expected[:16],
                "observed_sha256": identity.sha256[:16],
                "observed_mtime": identity.mtime,
            })
        else:
            problems.append({
                "role": role,
                "path": spath,
                "status": "stable",
                "sha256": identity.sha256[:16],
            })
    return problems


def _verify_operation(op: MergeOperation, dest_snap: Snapshot) -> VerificationResult:
    cat = op.category
    if cat == ActivityCategory.SAFETY:
        return VerificationResult(
            status="unverifiable",
            expected=None,
            observed=None,
            explanation="Safety preflight operations must be manually confirmed. They are not verified against a destination snapshot.",
        )
    elif cat == ActivityCategory.SET_LEVEL:
        return _verify_set_level(op, dest_snap)
    elif cat in {
        ActivityCategory.TRACK_ADDITION,
        ActivityCategory.TRACK_REMOVAL,
        ActivityCategory.TRACK_MODIFICATION,
        ActivityCategory.TRACK_ORDERING,
    }:
        return _verify_track_operation(op, dest_snap)
    elif cat == ActivityCategory.LOCATOR:
        return _verify_locator_operation(op, dest_snap)
    elif cat == ActivityCategory.DEVICE_REVIEW:
        return _verify_device_operation(op, dest_snap)
    else:
        return VerificationResult(
            status="unverifiable",
            expected=op.recommended_result,
            explanation="No specific verification rule is defined for this operation category.",
            next_manual_step="Open the destination in Ableton Live and confirm manually.",
        )


def _verify_set_level(op: MergeOperation, dest_snap: Snapshot) -> VerificationResult:
    title_lower = op.title.lower()
    if "tempo" in title_lower:
        expected = float(op.recommended_result) if op.recommended_result is not None else None
        observed = dest_snap.tempo
        if expected is not None:
            if abs(observed - expected) < 0.01:
                return VerificationResult(
                    status="pass",
                    expected=expected,
                    observed=observed,
                    explanation=f"Tempo matches expected value ({expected} BPM).",
                )
            return VerificationResult(
                status="fail",
                expected=expected,
                observed=observed,
                explanation=f"Tempo is {observed} BPM, expected {expected} BPM.",
                likely_cause="Tempo was not set in Ableton Live.",
                next_manual_step="Open the destination project and set the tempo manually.",
            )
    if "time signature" in title_lower or "time_sig" in title_lower:
        expected = op.recommended_result
        observed = dest_snap.time_signature
        if expected is not None:
            if observed == expected:
                return VerificationResult(
                    status="pass",
                    expected=expected,
                    observed=observed,
                    explanation="Time signature matches expected value.",
                )
            return VerificationResult(
                status="fail",
                expected=expected,
                observed=observed,
                explanation=f"Time signature is {observed}, expected {expected}.",
                likely_cause="Time signature was not set in Ableton Live.",
                next_manual_step="Open the destination project and set the time signature manually.",
            )
    return VerificationResult(
        status="unverifiable",
        expected=op.recommended_result,
        explanation="No automated verification available for this set-level operation.",
        next_manual_step="Open the destination in Ableton Live and confirm manually.",
    )


def _verify_track_operation(op: MergeOperation, dest_snap: Snapshot) -> VerificationResult:
    track_name = op.affected_track_name or op.title
    if not track_name or not track_name.strip():
        return VerificationResult(
            status="unverifiable",
            explanation="Operation has no track name — verification not possible.",
            next_manual_step="Review the operation manually in Ableton Live.",
        )
    dest_tracks = {
        t.get("name", ""): t for t in dest_snap.tracks
    }
    title_lower = op.title.lower()

    if "remove" in title_lower or "removal" in title_lower:
        if track_name not in dest_tracks or track_name == "":
            return VerificationResult(
                status="pass",
                expected="absent",
                observed="absent",
                explanation=f"Track '{track_name}' was successfully removed.",
            )
        return VerificationResult(
            status="fail",
            expected="absent",
            observed=f"Track '{track_name}' still present",
            explanation=f"Track '{track_name}' should have been removed but still exists.",
            likely_cause="Track was not deleted in Ableton Live.",
            next_manual_step="Delete the track in the destination project.",
        )

    if "add" in title_lower or "addition" in title_lower:
        if track_name in dest_tracks:
            return VerificationResult(
                status="pass",
                expected="present",
                observed="present",
                explanation=f"Track '{track_name}' was successfully added.",
            )
        return VerificationResult(
            status="fail",
            expected="present",
            observed="absent",
            explanation=f"Track '{track_name}' was not found in destination.",
            likely_cause="Track was not imported into Ableton Live.",
            next_manual_step="Import the track from the source Set into the destination.",
        )

    if "rename" in title_lower:
        if track_name in dest_tracks:
            return VerificationResult(
                status="pass",
                expected=track_name,
                observed=track_name,
                explanation=f"Track renamed to '{track_name}'.",
            )
        return VerificationResult(
            status="partial",
            expected=track_name,
            observed="absent",
            explanation=f"Track '{track_name}' not found by name.",
            next_manual_step="Rename the track in Ableton Live.",
        )

    if "order" in title_lower or "ordering" in title_lower:
        dest_names = [t.get("name", "") for t in dest_snap.tracks]
        return VerificationResult(
            status="unverifiable",
            expected=op.recommended_result,
            observed=dest_names,
            explanation="Full track order verification requires the accepted plan order.",
            next_manual_step="Visually confirm track order in Ableton Live.",
        )

    return VerificationResult(
        status="unverifiable",
        expected=op.recommended_result,
        explanation="No specific automated verification available for this track operation.",
        next_manual_step="Open the destination in Ableton Live and confirm manually.",
    )


def _verify_locator_operation(op: MergeOperation, dest_snap: Snapshot) -> VerificationResult:
    locator_name = op.affected_locator_name or op.title
    dest_locators = {
        l.get("name", ""): l for l in dest_snap.locators
    }
    title_lower = op.title.lower()

    if "remove" in title_lower:
        if locator_name not in dest_locators or locator_name == "":
            return VerificationResult(
                status="pass",
                expected="absent",
                observed="absent",
                explanation=f"Locator '{locator_name}' removed successfully.",
            )
        return VerificationResult(
            status="fail",
            expected="absent",
            observed="present",
            explanation=f"Locator '{locator_name}' still exists.",
            next_manual_step="Delete the locator in Ableton Live.",
        )

    if "add" in title_lower:
        if locator_name in dest_locators:
            return VerificationResult(
                status="pass",
                expected="present",
                observed="present",
                explanation=f"Locator '{locator_name}' added successfully.",
            )
        return VerificationResult(
            status="fail",
            expected="present",
            observed="absent",
            explanation=f"Locator '{locator_name}' not found.",
            next_manual_step="Add the locator in Ableton Live.",
        )

    if "move" in title_lower:
        if locator_name in dest_locators:
            observed_time = dest_locators[locator_name].get("time")
            expected_time = op.recommended_result
            if expected_time is not None and observed_time is not None:
                try:
                    if abs(float(observed_time) - float(expected_time)) < 0.1:
                        return VerificationResult(
                            status="pass",
                            expected=expected_time,
                            observed=observed_time,
                            explanation=f"Locator '{locator_name}' moved to expected position.",
                        )
                except (ValueError, TypeError):
                    pass
            return VerificationResult(
                status="partial",
                expected=expected_time,
                observed=observed_time,
                explanation=f"Locator '{locator_name}' exists. Verify time manually in Ableton Live.",
                next_manual_step="Check locator position in Ableton Live.",
            )
        return VerificationResult(
            status="fail",
            expected="present",
            observed="absent",
            explanation=f"Locator '{locator_name}' not found.",
            next_manual_step="Re-add the locator in Ableton Live.",
        )

    return VerificationResult(
        status="unverifiable",
        explanation="No automated verification available for this locator operation.",
        next_manual_step="Check locators in Ableton Live.",
    )


def _verify_device_operation(op: MergeOperation, dest_snap: Snapshot) -> VerificationResult:
    return VerificationResult(
        status="unverifiable",
        expected=op.recommended_result,
        explanation="Device-level verification is not automated. Review the device chain in Ableton Live.",
        next_manual_step="Open the destination, inspect the device chain on the relevant track, and confirm or correct manually.",
    )
