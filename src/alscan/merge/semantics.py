from __future__ import annotations

from typing import Any


def three_way_scalar(
    base: Any, ours: Any, theirs: Any
) -> tuple[Any, bool]:
    """Three-way merge for a scalar field.

    Returns (resolved_value, was_conflict).
    """
    if ours == theirs:
        return ours, False
    if ours == base:
        return theirs, False
    if theirs == base:
        return ours, False
    return base, True


def three_way_device_list(
    base: list[dict], ours: list[dict], theirs: list[dict]
) -> tuple[list[dict], bool]:
    """Ordered device-list three-way comparison.

    No per-device identity matching in v0.4. Treats the ordered list as
    a single structural field.
    """
    if ours == theirs:
        return ours, False
    if ours == base:
        return theirs, False
    if theirs == base:
        return ours, False
    return base, True


def merge_sample_name_union(
    base: list[str], ours: list[str], theirs: list[str]
) -> tuple[list[str], list[str]]:
    """Retention-biased sample name union.

    Returns (sorted_unique_names, warnings).

    Retains any name present in either branch. This is conservative:
    alscan cannot determine whether a missing name represents deletion,
    relocation, replacement, or incomplete parsing.
    """
    merged = sorted(set(ours) | set(theirs))
    warnings = []
    base_set = set(base)
    ours_set = set(ours)
    theirs_set = set(theirs)
    retained_from_one = (ours_set ^ theirs_set) - (base_set - ours_set - theirs_set)
    if retained_from_one:
        warnings.append(
            "Sample-name metadata uses a retention-biased union. "
            "A name present in either branch is retained because alscan "
            "cannot determine whether its absence represents deletion, "
            "relocation, replacement, or incomplete parsing. "
            "Equal names do not prove equal source files."
        )
    return merged, warnings


def track_exact_identity(
    base_track: dict, ours_track: dict, theirs_track: dict
) -> tuple[bool, str, list[str]]:
    """Check whether a track is an exact three-way identity match.

    Returns (is_exact, confidence_level, warnings).
    Confidence: "exact" | "ambiguous"
    """
    base_id = base_track.get("track_id")
    ours_id = ours_track.get("track_id") if ours_track else None
    theirs_id = theirs_track.get("track_id") if theirs_track else None
    base_type = base_track.get("track_type")
    ours_type = ours_track.get("track_type") if ours_track else None
    theirs_type = theirs_track.get("track_type") if theirs_track else None

    warnings: list[str] = []

    if ours_track is None and theirs_track is None:
        return False, "unmatched", ["track absent from both branches"]

    if ours_track is None:
        return False, "unmatched", ["track absent from ours"]

    if theirs_track is None:
        return False, "unmatched", ["track absent from theirs"]

    if ours_id == base_id and theirs_id == base_id:
        if ours_type == base_type and theirs_type == base_type:
            return True, "exact", []
        else:
            warnings.append(
                f"Same track ID ({base_id}) but track type differs: "
                f"base={base_type}, ours={ours_type}, theirs={theirs_type}"
            )
            return False, "ambiguous", warnings

    return False, "unmatched", [
        f"track_id differs: base={base_id}, ours={ours_id}, theirs={theirs_id}"
    ]


def three_way_track_field(
    base_track: dict, ours_track: dict, theirs_track: dict, field: str
) -> tuple[Any, bool]:
    """Three-way merge for a single track field.

    Returns (resolved_value, was_conflict).
    """
    base_val = base_track.get(field)
    ours_val = ours_track.get(field) if ours_track else None
    theirs_val = theirs_track.get(field) if theirs_track else None
    return three_way_scalar(base_val, ours_val, theirs_val)
