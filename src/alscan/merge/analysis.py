# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from alscan.merge.inputs import ThreeWayInput
from alscan.merge.plan import (
    AutoResolved,
    Conflict,
    IdentityMatch,
    LocatorChange,
    MergePlan,
    TrackChange,
)
from alscan.merge.semantics import (
    merge_sample_name_union,
    three_way_device_list,
)


NUMERIC_COMPARISON_PRECISION = 6


# Identity evidence is intentionally conservative. Strong evidence is required
# for plausible identity; common/default values can only support it.
COMMON_VOLUME = 0.75
COMMON_CLIP_COUNT = 0


def build_merge_plan(inputs: ThreeWayInput) -> MergePlan:
    plan = MergePlan(
        input_mode=inputs.mode,
        lineage_confidence=inputs.lineage.level,
        warnings=inputs.lineage.warnings.copy(),
    )
    plan.sources = {
        "base": {
            "sha256": inputs.base_identity.sha256,
            "size": inputs.base_identity.size,
            "label": inputs.base_identity.path.name,
        },
        "ours": {
            "sha256": inputs.ours_identity.sha256,
            "size": inputs.ours_identity.size,
            "label": inputs.ours_identity.path.name,
        },
        "theirs": {
            "sha256": inputs.theirs_identity.sha256,
            "size": inputs.theirs_identity.size,
            "label": inputs.theirs_identity.path.name,
        },
    }
    plan.source_structural_fingerprints = {
        "base": inputs.base_snapshot.structural_fingerprint,
        "ours": inputs.ours_snapshot.structural_fingerprint,
        "theirs": inputs.theirs_snapshot.structural_fingerprint,
    }

    if inputs.mode == "snapshot":
        plan.warnings.append(
            "Source hashes identify the alscan snapshot files, not the "
            "original Ableton projects. Original .als hashes are not "
            "available from snapshot data."
        )

    _analyze_scalar_fields(plan, inputs)
    branch_matches = _analyze_tracks(plan, inputs)
    _analyze_track_order(plan, inputs, branch_matches)
    _analyze_locators(plan, inputs)

    plan.conflict_count = len(plan.conflicts)
    plan.warning_count = len(plan.warnings)
    plan.file_differences_detected = bool(
        plan.auto_resolved
        or plan.conflicts
        or plan.track_changes
        or plan.locator_changes
        or plan.identity_matches
    )
    return plan


def _normalize_number(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, NUMERIC_COMPARISON_PRECISION)
    return value


def _values_equal(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return _normalize_number(float(a)) == _normalize_number(float(b))
    return a == b


def _three_way_value(base: Any, ours: Any, theirs: Any) -> tuple[Any, bool]:
    if _values_equal(ours, theirs):
        return ours, False
    if _values_equal(ours, base):
        return theirs, False
    if _values_equal(theirs, base):
        return ours, False
    return base, True


def _analyze_scalar_fields(plan: MergePlan, inputs: ThreeWayInput) -> None:
    if not _values_equal(inputs.base_snapshot.tempo, inputs.ours_snapshot.tempo) or not _values_equal(inputs.base_snapshot.tempo, inputs.theirs_snapshot.tempo):
        resolved, conflict = _three_way_value(
            inputs.base_snapshot.tempo,
            inputs.ours_snapshot.tempo,
            inputs.theirs_snapshot.tempo,
        )
        if conflict:
            plan.conflicts.append(Conflict(
                id="conflict-tempo",
                field="tempo",
                base_value=inputs.base_snapshot.tempo,
                ours_value=inputs.ours_snapshot.tempo,
                theirs_value=inputs.theirs_snapshot.tempo,
                reason="Both sides changed tempo to different values",
                risk="medium",
                available_resolutions=["accept_ours", "accept_theirs", "retain_base"],
            ))
        else:
            plan.auto_resolved.append(AutoResolved(
                id="resolve-tempo",
                field="tempo",
                base_value=inputs.base_snapshot.tempo,
                resolved_value=resolved,
                resolution="accept_ours" if resolved == inputs.ours_snapshot.tempo else "accept_theirs",
                description=f"Tempo changed from {inputs.base_snapshot.tempo} to {resolved}",
            ))

    if inputs.base_snapshot.time_signature != inputs.ours_snapshot.time_signature or inputs.base_snapshot.time_signature != inputs.theirs_snapshot.time_signature:
        resolved, conflict = _three_way_value(
            inputs.base_snapshot.time_signature,
            inputs.ours_snapshot.time_signature,
            inputs.theirs_snapshot.time_signature,
        )
        if conflict:
            plan.conflicts.append(Conflict(
                id="conflict-time-sig",
                field="time_signature",
                base_value=inputs.base_snapshot.time_signature,
                ours_value=inputs.ours_snapshot.time_signature,
                theirs_value=inputs.theirs_snapshot.time_signature,
                reason="Both sides changed time signature to different values",
                risk="medium",
                available_resolutions=["accept_ours", "accept_theirs", "retain_base"],
            ))
        else:
            plan.auto_resolved.append(AutoResolved(
                id="resolve-time-sig",
                field="time_signature",
                base_value=inputs.base_snapshot.time_signature,
                resolved_value=resolved,
                resolution="accept_ours" if resolved == inputs.ours_snapshot.time_signature else "accept_theirs",
                description=f"Time signature changed from {inputs.base_snapshot.time_signature} to {resolved}",
            ))


def _analyze_tracks(plan: MergePlan, inputs: ThreeWayInput) -> dict[str, dict[int, int | None]]:
    base_tracks = list(inputs.base_snapshot.tracks)
    ours_tracks = list(inputs.ours_snapshot.tracks)
    theirs_tracks = list(inputs.theirs_snapshot.tracks)
    duplicate_ids = {
        "base": _duplicate_track_ids(base_tracks),
        "ours": _duplicate_track_ids(ours_tracks),
        "theirs": _duplicate_track_ids(theirs_tracks),
    }
    matches = {
        "ours": _match_branch(base_tracks, ours_tracks, duplicate_ids["base"], duplicate_ids["ours"], exact_only=False),
        "theirs": _match_branch(base_tracks, theirs_tracks, duplicate_ids["base"], duplicate_ids["theirs"], exact_only=False),
    }
    exact_matches = {
        "ours": _match_branch(base_tracks, ours_tracks, duplicate_ids["base"], duplicate_ids["ours"], exact_only=True),
        "theirs": _match_branch(base_tracks, theirs_tracks, duplicate_ids["base"], duplicate_ids["theirs"], exact_only=True),
    }
    duplicate_base = {
        "ours": _ambiguous_branch_duplicates(base_tracks, ours_tracks, duplicate_ids["base"], duplicate_ids["ours"]),
        "theirs": _ambiguous_branch_duplicates(base_tracks, theirs_tracks, duplicate_ids["base"], duplicate_ids["theirs"]),
    }
    reverse = {
        "ours": _reverse_matches(matches["ours"]),
        "theirs": _reverse_matches(matches["theirs"]),
    }

    base_by_id = {t["track_id"]: t for t in base_tracks}
    ours_by_id = {t["track_id"]: t for t in ours_tracks}
    theirs_by_id = {t["track_id"]: t for t in theirs_tracks}

    for bt in base_tracks:
        bid = bt["track_id"]
        om = matches["ours"].get(bid)
        tm = matches["theirs"].get(bid)
        ot = ours_by_id.get(om) if om is not None else None
        tt = theirs_by_id.get(tm) if tm is not None else None
        oc = _classify_branch_match(bt, base_tracks, ours_tracks, duplicate_ids["base"], duplicate_ids["ours"])
        tc = _classify_branch_match(bt, base_tracks, theirs_tracks, duplicate_ids["base"], duplicate_ids["theirs"])
        if bid in duplicate_base["ours"]:
            oc = {"classification": "ambiguous", "track_id": None, "evidence": ["duplicate_base_identity_evidence"]}
        if bid in duplicate_base["theirs"]:
            tc = {"classification": "ambiguous", "track_id": None, "evidence": ["duplicate_base_identity_evidence"]}

        _record_identity(plan, bt, om, tm, oc, tc)
        if oc["classification"] == "ambiguous" or tc["classification"] == "ambiguous":
            plan.conflicts.append(Conflict(
                id=f"conflict-track-{bid}-identity",
                field="track.identity",
                base_value=_track_ref(bt),
                ours_value=_track_ref(ot) if ot else oc.get("candidates", []),
                theirs_value=_track_ref(tt) if tt else tc.get("candidates", []),
                reason="Track identity is ambiguous and must be resolved before metadata can be trusted",
                risk="high",
                available_resolutions=["manual_identity_mapping", "exclude_track"],
            ))
            continue

        if ot is None and tt is None:
            plan.track_changes.append(TrackChange(
                id=f"track-{bid}-removed-both",
                kind="removed",
                branch="both",
                track_id=bid,
                base_track_id=bid,
                name=bt.get("name", ""),
                auto_resolved=True,
            ))
            continue
        if ot is None or tt is None:
            branch = "ours" if ot is None else "theirs"
            other = tt if ot is None else ot
            if _track_metadata_changed(bt, other):
                plan.conflicts.append(Conflict(
                    id=f"conflict-track-{bid}-delete-vs-modify",
                    field="track.delete_vs_modify",
                    base_value=_track_ref(bt),
                    ours_value=_track_ref(ot) if ot else None,
                    theirs_value=_track_ref(tt) if tt else None,
                    reason="One branch removed a base track while the other modified it",
                    risk="high",
                    available_resolutions=["keep_modified", "accept_delete", "retain_base"],
                ))
            else:
                plan.track_changes.append(TrackChange(
                    id=f"track-{bid}-removed-{branch}",
                    kind="removed",
                    branch=branch,
                    track_id=bid,
                    base_track_id=bid,
                    name=bt.get("name", ""),
                    auto_resolved=False,
                ))
            continue

        if oc["classification"] == "plausible" or tc["classification"] == "plausible":
            plan.warnings.append(
                f"Track '{bt.get('name', bid)}' has plausible identity evidence only; "
                "identity-dependent suggestions are not auto-resolved."
            )

        identity_classification = "plausible" if oc["classification"] == "plausible" or tc["classification"] == "plausible" else "exact"
        _analyze_matched_track_fields(plan, bt, ot, tt, identity_classification)

    _analyze_additions(plan, base_tracks, ours_tracks, theirs_tracks, reverse)
    return exact_matches


def _duplicate_track_ids(tracks: list[dict]) -> set[int]:
    counts = Counter(t.get("track_id") for t in tracks)
    return {tid for tid, count in counts.items() if tid is not None and count > 1}


def _match_branch(
    base_tracks: list[dict],
    branch_tracks: list[dict],
    base_duplicate_ids: set[int],
    branch_duplicate_ids: set[int],
    exact_only: bool,
) -> dict[int, int | None]:
    result = {}
    for bt in base_tracks:
        c = _classify_branch_match(bt, base_tracks, branch_tracks, base_duplicate_ids, branch_duplicate_ids)
        allowed = ("exact",) if exact_only else ("exact", "plausible")
        result[bt["track_id"]] = c.get("track_id") if c["classification"] in allowed else None
    counts = Counter(tid for tid in result.values() if tid is not None)
    for bid, tid in list(result.items()):
        if tid is not None and counts[tid] > 1:
            result[bid] = None
    return result


def _ambiguous_branch_duplicates(
    base_tracks: list[dict],
    branch_tracks: list[dict],
    base_duplicate_ids: set[int],
    branch_duplicate_ids: set[int],
) -> set[int]:
    plausible_targets: dict[int, list[int]] = defaultdict(list)
    for bt in base_tracks:
        c = _classify_branch_match(bt, base_tracks, branch_tracks, base_duplicate_ids, branch_duplicate_ids)
        if c["classification"] in ("exact", "plausible") and c.get("track_id") is not None:
            plausible_targets[c["track_id"]].append(bt["track_id"])
    return {bid for bids in plausible_targets.values() if len(bids) > 1 for bid in bids}


def _reverse_matches(matches: dict[int, int | None]) -> dict[int, int]:
    return {tid: bid for bid, tid in matches.items() if tid is not None}


def _classify_branch_match(
    base_track: dict,
    base_tracks: list[dict],
    branch_tracks: list[dict],
    base_duplicate_ids: set[int],
    branch_duplicate_ids: set[int],
) -> dict[str, Any]:
    bid = base_track.get("track_id")
    btype = base_track.get("track_type")
    if bid in base_duplicate_ids:
        return {"classification": "ambiguous", "track_id": None, "evidence": ["duplicate_base_track_id"]}
    same_id = [t for t in branch_tracks if t.get("track_id") == bid]
    if same_id:
        if bid in branch_duplicate_ids or len(same_id) > 1:
            return {"classification": "ambiguous", "track_id": None, "evidence": ["duplicate_branch_track_id"], "candidates": [_track_ref(t) for t in same_id]}
        compatible = [t for t in same_id if t.get("track_type") == btype]
        if len(compatible) == 1:
            return {"classification": "exact", "track_id": compatible[0].get("track_id"), "evidence": ["same_track_id", "compatible_type"]}
        return {"classification": "ambiguous", "track_id": None, "evidence": ["same_track_id", "incompatible_type"], "candidates": [_track_ref(t) for t in same_id]}

    candidates = []
    for t in branch_tracks:
        if t.get("track_id") in branch_duplicate_ids:
            continue
        evidence, strong = _identity_evidence(base_track, t, base_tracks, branch_tracks)
        if strong and len(evidence) >= 3:
            candidates.append((t, evidence))
    if len(candidates) == 1:
        t, evidence = candidates[0]
        return {"classification": "plausible", "track_id": t.get("track_id"), "evidence": evidence}
    if len(candidates) > 1:
        return {"classification": "ambiguous", "track_id": None, "evidence": ["duplicate_plausible_candidates"], "candidates": [_track_ref(t) for t, _ in candidates]}
    name_matches = [t for t in branch_tracks if t.get("name") == base_track.get("name")]
    if name_matches:
        return {"classification": "ambiguous", "track_id": None, "evidence": ["name_only"], "candidates": [_track_ref(t) for t in name_matches]}
    return {"classification": "unmatched", "track_id": None, "evidence": []}


def _identity_evidence(
    base_track: dict,
    branch_track: dict,
    base_tracks: list[dict],
    branch_tracks: list[dict],
) -> tuple[list[str], list[str]]:
    evidence = []
    strong = []

    name = base_track.get("name")
    if name and name == branch_track.get("name"):
        evidence.append("name")
        strong.append("name")

    if base_track.get("track_type") == branch_track.get("track_type"):
        evidence.append("track_type")

    if base_track.get("is_frozen") is True and branch_track.get("is_frozen") is True:
        evidence.append("is_frozen")

    if base_track.get("color_index") not in (None, 0, 1) and base_track.get("color_index") == branch_track.get("color_index"):
        evidence.append("color_index")

    group_id = base_track.get("group_id")
    if group_id not in (None, "", 0, -1) and group_id == branch_track.get("group_id"):
        evidence.append("group_id")
        strong.append("group_id")

    if not _values_equal(base_track.get("volume"), COMMON_VOLUME) and _values_equal(base_track.get("volume"), branch_track.get("volume")):
        evidence.append("volume")

    if base_track.get("clip_count") not in (None, COMMON_CLIP_COUNT) and base_track.get("clip_count") == branch_track.get("clip_count"):
        evidence.append("clip_count")

    base_devices = _device_signature(base_track)
    branch_devices = _device_signature(branch_track)
    if base_devices and base_devices == branch_devices:
        evidence.append("devices")
        strong.append("devices")

    if _same_type_relative_position(base_track, branch_track, base_tracks, branch_tracks):
        evidence.append("same_type_relative_position")
        strong.append("same_type_relative_position")

    return evidence, strong


def _device_signature(track: dict) -> tuple:
    return tuple((d.get("name"), d.get("device_type"), d.get("plugin_name"), d.get("plugin_type")) for d in track.get("devices", []))


def _same_type_relative_position(base_track: dict, branch_track: dict, base_tracks: list[dict], branch_tracks: list[dict]) -> bool:
    track_type = base_track.get("track_type")
    if track_type != branch_track.get("track_type"):
        return False
    base_same_type = [t for t in base_tracks if t.get("track_type") == track_type]
    branch_same_type = [t for t in branch_tracks if t.get("track_type") == track_type]
    if len(base_same_type) < 2 or len(base_same_type) != len(branch_same_type):
        return False
    try:
        return base_same_type.index(base_track) == branch_same_type.index(branch_track)
    except ValueError:
        return False


def _record_identity(plan: MergePlan, bt: dict, ours_id: int | None, theirs_id: int | None, oc: dict, tc: dict) -> None:
    classifications = {oc["classification"], tc["classification"]}
    if "ambiguous" in classifications:
        classification = "ambiguous"
    elif "unmatched" in classifications:
        classification = "unmatched"
    elif "plausible" in classifications:
        classification = "plausible"
    else:
        classification = "exact"
    evidence = sorted(set(oc.get("evidence", [])) | set(tc.get("evidence", [])))
    warnings = []
    if classification == "plausible":
        warnings.append("Plausible identity is reported for review only and is not automatically safe.")
    if classification == "ambiguous":
        warnings.append("Ambiguous identity requires manual review.")
    plan.identity_matches.append(IdentityMatch(
        track_id=bt.get("track_id"),
        name=bt.get("name", ""),
        base_track_id=bt.get("track_id"),
        ours_track_id=ours_id,
        theirs_track_id=theirs_id,
        confidence=classification,
        classification=classification,
        evidence=evidence,
        auto_resolved=classification == "exact",
        warnings=warnings,
    ))


def _analyze_matched_track_fields(plan: MergePlan, bt: dict, ot: dict, tt: dict, identity_classification: str) -> None:
    tid = bt.get("track_id")
    for field in ("name", "track_type", "is_frozen", "color_index", "group_id", "volume", "clip_count"):
        resolved, conflict = _three_way_value(bt.get(field), ot.get(field), tt.get(field))
        if conflict:
            plan.conflicts.append(Conflict(
                id=f"conflict-track-{tid}-{field}",
                field=f"track.{field}",
                base_value=bt.get(field),
                ours_value=ot.get(field),
                theirs_value=tt.get(field),
                reason=f"Both sides changed track field '{field}' differently",
                risk="medium" if field != "color_index" else "low",
                available_resolutions=["accept_ours", "accept_theirs", "retain_base"],
            ))
        elif not _values_equal(resolved, bt.get(field)):
            plan.track_changes.append(TrackChange(
                id=f"track-{tid}-{field}",
                kind="modified",
                branch="ours" if resolved == ot.get(field) and tt.get(field) == bt.get(field) else "theirs" if resolved == tt.get(field) and ot.get(field) == bt.get(field) else "both",
                track_id=tid,
                base_track_id=tid,
                branch_track_id=ot.get("track_id") if resolved == ot.get(field) else tt.get("track_id"),
                name=bt.get("name", ""),
                auto_resolved=identity_classification == "exact",
                details={
                    "field": field,
                    "base": bt.get(field),
                    "resolved": resolved,
                    "identity_confidence": identity_classification,
                    "requires_review": identity_classification != "exact",
                },
            ))

    _, sample_warnings = merge_sample_name_union(bt.get("samples", []), ot.get("samples", []), tt.get("samples", []))
    plan.warnings.extend(sample_warnings)
    _, dev_conflict = three_way_device_list(bt.get("devices", []), ot.get("devices", []), tt.get("devices", []))
    if dev_conflict:
        plan.conflicts.append(Conflict(
            id=f"conflict-track-{tid}-devices",
            field="track.devices",
            base_value=[d.get("name") for d in bt.get("devices", [])],
            ours_value=[d.get("name") for d in ot.get("devices", [])],
            theirs_value=[d.get("name") for d in tt.get("devices", [])],
            reason="Both sides changed device list differently",
            risk="medium",
            available_resolutions=["accept_ours", "accept_theirs", "retain_base"],
        ))


def _analyze_additions(plan: MergePlan, base_tracks: list[dict], ours_tracks: list[dict], theirs_tracks: list[dict], reverse: dict[str, dict[int, int]]) -> None:
    ours_add = [t for t in ours_tracks if t["track_id"] not in reverse["ours"]]
    theirs_add = [t for t in theirs_tracks if t["track_id"] not in reverse["theirs"]]
    paired_theirs: set[int] = set()
    for ot in ours_add:
        match = next((tt for tt in theirs_add if tt["track_id"] not in paired_theirs and _addition_signature(ot) == _addition_signature(tt)), None)
        if match:
            paired_theirs.add(match["track_id"])
            plan.track_changes.append(TrackChange(
                id=f"track-added-both-{ot['track_id']}-{match['track_id']}",
                kind="added",
                branch="both",
                branch_track_id=ot["track_id"],
                name=ot.get("name", ""),
                auto_resolved=True,
                details={"ours_track_id": ot["track_id"], "theirs_track_id": match["track_id"]},
            ))
        else:
            plan.track_changes.append(TrackChange(
                id=f"track-added-ours-{ot['track_id']}",
                kind="added",
                branch="ours",
                branch_track_id=ot["track_id"],
                name=ot.get("name", ""),
                auto_resolved=False,
            ))
    for tt in theirs_add:
        if tt["track_id"] in paired_theirs:
            continue
        plan.track_changes.append(TrackChange(
            id=f"track-added-theirs-{tt['track_id']}",
            kind="added",
            branch="theirs",
            branch_track_id=tt["track_id"],
            name=tt.get("name", ""),
            auto_resolved=False,
        ))


def _addition_signature(track: dict) -> tuple:
    return (
        track.get("name"),
        track.get("track_type"),
        track.get("is_frozen"),
        track.get("color_index"),
        track.get("group_id"),
        track.get("volume"),
        track.get("clip_count"),
        _device_signature(track),
    )


def _track_metadata_changed(base: dict, branch: dict | None) -> bool:
    if branch is None:
        return False
    fields = ("name", "track_type", "is_frozen", "color_index", "group_id", "volume", "clip_count", "devices")
    return any(base.get(f) != branch.get(f) for f in fields)


def _analyze_track_order(plan: MergePlan, inputs: ThreeWayInput, matches: dict[str, dict[int, int | None]]) -> None:
    base_order = [t["track_id"] for t in inputs.base_snapshot.tracks]
    ours_branch_order = _base_order_seen(inputs.ours_snapshot.tracks, matches["ours"])
    theirs_branch_order = _base_order_seen(inputs.theirs_snapshot.tracks, matches["theirs"])

    ours_filtered = [bid for bid in base_order if bid in ours_branch_order]
    theirs_filtered = [bid for bid in base_order if bid in theirs_branch_order]

    ours_changed = ours_branch_order != ours_filtered
    theirs_changed = theirs_branch_order != theirs_filtered

    if ours_changed and theirs_changed and ours_branch_order != theirs_branch_order:
        plan.conflicts.append(Conflict(
            id="conflict-track-order-base-derived",
            field="track.order",
            base_value=base_order,
            ours_value=ours_branch_order,
            theirs_value=theirs_branch_order,
            reason="Base-derived tracks were reordered divergently",
            risk="medium",
            available_resolutions=["accept_ours_order", "accept_theirs_order", "retain_base_order"],
        ))

    positions = []
    for branch, tracks in (("ours", inputs.ours_snapshot.tracks), ("theirs", inputs.theirs_snapshot.tracks)):
        rev = _reverse_matches(matches[branch])
        for index, t in enumerate(tracks):
            if t["track_id"] in rev:
                continue
            pos = _insertion_position(tracks, index, rev)
            change = next((c for c in plan.track_changes if c.branch in (branch, "both") and c.branch_track_id == t["track_id"]), None)
            if pos and change:
                change.proposed_position = pos
                positions.append((pos.get("after_base_track_id"), pos.get("before_base_track_id"), branch, t))
            elif change:
                change.details["position"] = "ambiguous"
                plan.conflicts.append(Conflict(
                    id=f"conflict-track-order-insertion-unanchored-{branch}-{t['track_id']}",
                    field="track.insertion_position",
                    base_value=None,
                    ours_value=_track_ref(t) if branch == "ours" else None,
                    theirs_value=_track_ref(t) if branch == "theirs" else None,
                    reason="Track insertion cannot be anchored between exact base-derived tracks",
                    risk="medium",
                    available_resolutions=["manual_order"],
                ))
    grouped = defaultdict(list)
    for after, before, branch, track in positions:
        grouped[(after, before)].append((branch, track))
    for (after, before), items in grouped.items():
        branches = {branch for branch, _ in items}
        signatures = {(_addition_signature(track), track.get("track_id")) for _, track in items}
        if len(branches) > 1 and len(signatures) > 1:
            plan.conflicts.append(Conflict(
                id=f"conflict-track-order-insertion-{after}-{before}",
                field="track.insertion_position",
                base_value={"after_base_track_id": after, "before_base_track_id": before},
                ours_value=[_track_ref(t) for branch, t in items if branch == "ours"],
                theirs_value=[_track_ref(t) for branch, t in items if branch == "theirs"],
                reason="Competing track insertions target the same base-order position",
                risk="medium",
                available_resolutions=["manual_order"],
            ))
    plan.proposed_track_order = [
        {"branch": branch, "track": _track_ref(track), "position": {"after_base_track_id": after, "before_base_track_id": before}}
        for after, before, branch, track in positions
    ]


def _base_order_seen(branch_tracks: list[dict], matches: dict[int, int | None]) -> list[int]:
    rev = _reverse_matches(matches)
    return [rev[t["track_id"]] for t in branch_tracks if t["track_id"] in rev]


def _common_order(a: list[int], b: list[int]) -> bool:
    common = [x for x in a if x in set(b)]
    return common == [x for x in b if x in set(a)]


def _insertion_position(tracks: list[dict], index: int, reverse_matches: dict[int, int]) -> dict | None:
    prev_base = None
    for t in reversed(tracks[:index]):
        if t["track_id"] in reverse_matches:
            prev_base = reverse_matches[t["track_id"]]
            break
    next_base = None
    for t in tracks[index + 1:]:
        if t["track_id"] in reverse_matches:
            next_base = reverse_matches[t["track_id"]]
            break
    if prev_base is None and next_base is None:
        return None
    return {"after_base_track_id": prev_base, "before_base_track_id": next_base}


def _analyze_locators(plan: MergePlan, inputs: ThreeWayInput) -> None:
    base = list(inputs.base_snapshot.locators)
    ours = list(inputs.ours_snapshot.locators)
    theirs = list(inputs.theirs_snapshot.locators)
    if not base and not ours and not theirs:
        return
    base_remaining = _remove_exact_locator_matches(plan, base, ours, theirs)
    ours_remaining = [l for i, l in enumerate(ours) if i not in base_remaining["used_ours"]]
    theirs_remaining = [l for i, l in enumerate(theirs) if i not in base_remaining["used_theirs"]]
    base_remaining_locs = [l for i, l in enumerate(base) if i not in base_remaining["used_base"]]

    all_names = sorted({l.get("name") for l in base_remaining_locs + ours_remaining + theirs_remaining})
    for name in all_names:
        b = [l for l in base_remaining_locs if l.get("name") == name]
        o = [l for l in ours_remaining if l.get("name") == name]
        t = [l for l in theirs_remaining if l.get("name") == name]
        if len(b) > 1 or len(o) > 1 or len(t) > 1:
            plan.conflicts.append(Conflict(
                id=f"conflict-locator-{_safe_id(name)}-duplicate-name",
                field="locator.identity",
                base_value=b,
                ours_value=o,
                theirs_value=t,
                reason="Duplicate locator names prevent reliable movement identity",
                risk="medium",
                available_resolutions=["manual_locator_mapping"],
            ))
            continue
        _classify_unique_locator_name(plan, name, b, o, t)


def _remove_exact_locator_matches(plan: MergePlan, base: list[dict], ours: list[dict], theirs: list[dict]) -> dict[str, set[int]]:
    used_base: set[int] = set()
    used_ours: set[int] = set()
    used_theirs: set[int] = set()
    for bi, bl in enumerate(base):
        for oi, ol in enumerate(ours):
            if oi in used_ours or not _locator_equal(bl, ol):
                continue
            for ti, tl in enumerate(theirs):
                if ti in used_theirs or not _locator_equal(bl, tl):
                    continue
                used_base.add(bi)
                used_ours.add(oi)
                used_theirs.add(ti)
                plan.locator_changes.append(LocatorChange(
                    id=f"locator-{_safe_id(bl.get('name'))}-{_safe_id(bl.get('time'))}-unchanged",
                    kind="unchanged",
                    name=bl.get("name"),
                    base_time=bl.get("time"),
                    ours_time=ol.get("time"),
                    theirs_time=tl.get("time"),
                    auto_resolved=True,
                ))
                break
            if bi in used_base:
                break
    return {"used_base": used_base, "used_ours": used_ours, "used_theirs": used_theirs}


def _classify_unique_locator_name(plan: MergePlan, name: str, b: list[dict], o: list[dict], t: list[dict]) -> None:
    bv = b[0].get("time") if b else None
    ov = o[0].get("time") if o else None
    tv = t[0].get("time") if t else None
    if b and o and t:
        if _values_equal(ov, tv) and not _values_equal(ov, bv):
            plan.locator_changes.append(LocatorChange(id=f"locator-{_safe_id(name)}-moved-both", kind="moved", name=name, base_time=bv, ours_time=ov, theirs_time=tv, auto_resolved=True))
        elif _values_equal(ov, bv) and not _values_equal(tv, bv):
            plan.locator_changes.append(LocatorChange(id=f"locator-{_safe_id(name)}-moved-theirs", kind="moved", name=name, branch="theirs", base_time=bv, ours_time=ov, theirs_time=tv, auto_resolved=True))
        elif _values_equal(tv, bv) and not _values_equal(ov, bv):
            plan.locator_changes.append(LocatorChange(id=f"locator-{_safe_id(name)}-moved-ours", kind="moved", name=name, branch="ours", base_time=bv, ours_time=ov, theirs_time=tv, auto_resolved=True))
        else:
            plan.conflicts.append(Conflict(id=f"conflict-locator-{_safe_id(name)}-moved-differently", field="locator.movement", base_value=bv, ours_value=ov, theirs_value=tv, reason="Both sides moved the same locator differently", risk="medium", available_resolutions=["accept_ours", "accept_theirs", "retain_base"]))
    elif b and not o and t:
        if _values_equal(tv, bv):
            plan.locator_changes.append(LocatorChange(id=f"locator-{_safe_id(name)}-removed-ours", kind="removed", name=name, branch="ours", base_time=bv, theirs_time=tv, auto_resolved=False))
        else:
            plan.conflicts.append(Conflict(id=f"conflict-locator-{_safe_id(name)}-remove-vs-move", field="locator.remove_vs_move", base_value=bv, ours_value=None, theirs_value=tv, reason="One side removed a locator while the other moved it", risk="medium", available_resolutions=["accept_delete", "accept_move", "retain_base"]))
    elif b and o and not t:
        if _values_equal(ov, bv):
            plan.locator_changes.append(LocatorChange(id=f"locator-{_safe_id(name)}-removed-theirs", kind="removed", name=name, branch="theirs", base_time=bv, ours_time=ov, auto_resolved=False))
        else:
            plan.conflicts.append(Conflict(id=f"conflict-locator-{_safe_id(name)}-remove-vs-move", field="locator.remove_vs_move", base_value=bv, ours_value=ov, theirs_value=None, reason="One side removed a locator while the other moved it", risk="medium", available_resolutions=["accept_delete", "accept_move", "retain_base"]))
    elif b and not o and not t:
        plan.locator_changes.append(LocatorChange(id=f"locator-{_safe_id(name)}-removed-both", kind="removed", name=name, branch="both", base_time=bv, auto_resolved=True))
    elif not b:
        if o and t and _values_equal(ov, tv):
            plan.locator_changes.append(LocatorChange(id=f"locator-{_safe_id(name)}-added-both", kind="added", name=name, base_time=None, ours_time=ov, theirs_time=tv, auto_resolved=True))
        elif o and t:
            plan.conflicts.append(Conflict(id=f"conflict-locator-{_safe_id(name)}-added-different-times", field="locator.addition", base_value=None, ours_value=ov, theirs_value=tv, reason="Both sides added the same locator name at different times", risk="medium", available_resolutions=["accept_ours", "accept_theirs", "keep_both_with_rename"]))
        elif o:
            plan.locator_changes.append(LocatorChange(id=f"locator-{_safe_id(name)}-added-ours", kind="added", name=name, branch="ours", ours_time=ov, auto_resolved=True))
        elif t:
            plan.locator_changes.append(LocatorChange(id=f"locator-{_safe_id(name)}-added-theirs", kind="added", name=name, branch="theirs", theirs_time=tv, auto_resolved=True))


def _locator_equal(a: dict, b: dict) -> bool:
    return a.get("name") == b.get("name") and _values_equal(a.get("time"), b.get("time"))


def _track_ref(track: dict | None) -> dict | None:
    if track is None:
        return None
    return {"track_id": track.get("track_id"), "name": track.get("name"), "track_type": track.get("track_type")}


def _safe_id(value: object) -> str:
    return str(value).lower().replace(" ", "-").replace("/", "-")
