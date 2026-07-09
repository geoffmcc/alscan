# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

from alscan.io_safety import capture_identity, verify_stable, validate_parent, check_aliases, SourceIdentity
from alscan.parser import parse_als
from alscan.versioner import build_snapshot, load_snapshot, Snapshot, SNAPSHOT_FORMAT_VERSION


class DocumentType(Enum):
    SNAPSHOT_V1 = "alscan-snapshot"
    MERGED_SNAPSHOT = "alscan-merged-snapshot"
    MERGE_PLAN = "alscan-merge-plan"
    UNKNOWN = "unknown"


def detect_document_type(raw: str) -> DocumentType:
    d = json.loads(raw)
    dt = d.get("document_type")
    if dt == "alscan-snapshot":
        return DocumentType.SNAPSHOT_V1
    if dt == "alscan-merged-snapshot":
        return DocumentType.MERGED_SNAPSHOT
    if dt == "alscan-merge-plan":
        return DocumentType.MERGE_PLAN
    if dt is not None:
        return DocumentType.UNKNOWN
    try:
        Snapshot.from_json(raw)
        return DocumentType.SNAPSHOT_V1
    except (ValueError, TypeError):
        return DocumentType.UNKNOWN


def normalize_snapshot_json(raw: str) -> str:
    d = json.loads(raw)
    if "document_type" in d:
        if d["document_type"] == "alscan-snapshot":
            del d["document_type"]
            raw = json.dumps(d, ensure_ascii=False)
        else:
            raise ValueError(
                f"Expected a Snapshot but received "
                f"'{d['document_type']}' document"
            )
    Snapshot.from_json(raw)
    return raw


def load_snapshot_any(path: Path) -> Snapshot:
    raw = path.read_text(encoding="utf-8")
    normalized = normalize_snapshot_json(raw)
    return Snapshot.from_json(normalized)


InputMode = Literal["als", "snapshot"]
LineageLevel = Literal["strong", "plausible", "weak", "no_meaningful_relationship"]


@dataclass
class LineageResult:
    level: LineageLevel
    fingerprint_match: bool = False
    track_overlap_pct: float = 0.0
    project_name_match: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ThreeWayInput:
    mode: InputMode
    base_snapshot: Snapshot
    ours_snapshot: Snapshot
    theirs_snapshot: Snapshot
    base_identity: SourceIdentity
    ours_identity: SourceIdentity
    theirs_identity: SourceIdentity
    lineage: LineageResult


def _parse_input(path: Path, mode: InputMode) -> Snapshot:
    if mode == "snapshot":
        return load_snapshot_any(path)
    proj = parse_als(path)
    return build_snapshot(proj)


def validate_three_way(
    base_path: str,
    ours_path: str,
    theirs_path: str,
    allow_unrelated: bool = False,
    allow_plausible: bool = False,
) -> ThreeWayInput:
    base_p = Path(base_path)
    ours_p = Path(ours_path)
    theirs_p = Path(theirs_path)

    for p, label in [(base_p, "base"), (ours_p, "ours"), (theirs_p, "theirs")]:
        validate_parent(p)
        if not p.exists():
            raise FileNotFoundError(f"{label} input not found: {p}")

    suffixes = {p.suffix.lower() for p in (base_p, ours_p, theirs_p)}
    if len(suffixes) > 1:
        raise ValueError(
            "Mixed input types: expected all three inputs to have the same "
            f"extension (.als or .json), got: {', '.join(sorted(suffixes))}"
        )

    suffix = suffixes.pop()
    if suffix == ".als":
        mode: InputMode = "als"
    elif suffix == ".json":
        mode = "snapshot"
    else:
        raise ValueError(
            f"Unsupported input type '{suffix}'. "
            f"Expected .als (Ableton project) or .json (alscan snapshot)"
        )

    if mode == "snapshot":
        for p, label in [(base_p, "base"), (ours_p, "theirs"), (theirs_p, "theirs")]:
            try:
                raw = p.read_text(encoding="utf-8")
                normalize_snapshot_json(raw)
            except ValueError as e:
                raise ValueError(f"{label} input is not a valid snapshot: {p} — {e}")
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"{label} input is not valid JSON: {p} — {e}"
                )

    aliases = check_aliases([base_p, ours_p, theirs_p])
    if aliases:
        a, b, reason = aliases[0]
        raise ValueError(
            "Duplicate physical input detected: base, ours, and theirs "
            "must be independent files representing three different versions.\n"
            f"  {a} and {b} are the same file ({reason})."
        )

    base_id = capture_identity(base_p)
    ours_id = capture_identity(ours_p)
    theirs_id = capture_identity(theirs_p)

    base_snap = _parse_input(base_p, mode)
    ours_snap = _parse_input(ours_p, mode)
    theirs_snap = _parse_input(theirs_p, mode)

    verify_stable(base_id)
    verify_stable(ours_id)
    verify_stable(theirs_id)

    lineage = assess_lineage(base_snap, ours_snap, theirs_snap)

    if lineage.level == "no_meaningful_relationship" and not allow_unrelated:
        raise ValueError(
            "No meaningful structural relationship detected between the inputs. "
            "The three files do not appear to be related project versions. "
            "Use --allow-unrelated to analyze unrelated projects (results "
            "will be marked with low confidence and may not be meaningful)."
        )

    if lineage.level == "weak" and not allow_unrelated:
        raise ValueError(
            "Weak structural relationship detected. "
            "Use --allow-unrelated to proceed with low-confidence analysis."
        )

    return ThreeWayInput(
        mode=mode,
        base_snapshot=base_snap,
        ours_snapshot=ours_snap,
        theirs_snapshot=theirs_snap,
        base_identity=base_id,
        ours_identity=ours_id,
        theirs_identity=theirs_id,
        lineage=lineage,
    )


def assess_lineage(
    base: Snapshot, ours: Snapshot, theirs: Snapshot
) -> LineageResult:
    fp_match = (
        base.structural_fingerprint == ours.structural_fingerprint == theirs.structural_fingerprint
    )
    name_match = base.project_name == ours.project_name == theirs.project_name

    base_ids = {t["track_id"] for t in base.tracks}
    ours_ids = {t["track_id"] for t in ours.tracks}
    theirs_ids = {t["track_id"] for t in theirs.tracks}

    our_overlap = len(base_ids & ours_ids)
    their_overlap = len(base_ids & theirs_ids)
    total_base = len(base_ids) if base_ids else 1
    overlap_pct = min(our_overlap, their_overlap) / total_base

    warnings: list[str] = []

    if fp_match and overlap_pct >= 0.5:
        level: LineageLevel = "strong"
    elif fp_match or (name_match and overlap_pct >= 0.25):
        level = "plausible"
        if not fp_match:
            warnings.append(
                "Structural fingerprints differ — lineage based on project "
                "name and track ID overlap"
            )
    elif name_match or overlap_pct > 0:
        level = "weak"
    else:
        level = "no_meaningful_relationship"

    if not fp_match:
        warnings.append(
            "Structural fingerprints do not match. Template-derived or "
            "structurally similar unrelated projects may share fingerprints, "
            "but differing fingerprints indicate structural changes."
        )

    return LineageResult(
        level=level,
        fingerprint_match=fp_match,
        track_overlap_pct=overlap_pct,
        project_name_match=name_match,
        warnings=warnings,
    )
