from __future__ import annotations

from alscan.checks import Finding, register
from alscan.models import Project


@register("empty_tracks", severity="info", description="Tracks with no clips")
def check_empty_tracks(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        if track.track_type in ("master", "return"):
            continue
        if len(track.clips) == 0:
            findings.append(Finding(
                severity="info",
                check_name="empty_tracks",
                title="Empty Track",
                message=f'Track "{track.name}" has no clips',
                location=f"Track: {track.name}",
                suggestion="Remove unused tracks or mute if you plan to use them later",
            ))
    return findings


@register("unused_returns", severity="warning", description="Return tracks that may not be used")
def check_unused_returns(project: Project) -> list[Finding]:
    return_tracks = [t for t in project.tracks if t.track_type == "return"]
    if not return_tracks:
        return []

    findings = []
    used: set[str] = set()
    for track in project.tracks:
        if track.track_type in ("master", "return"):
            continue
        for ret in return_tracks:
            if len(ret.clips) > 0:
                used.add(ret.name)

    for ret in return_tracks:
        if ret.name not in used:
            findings.append(Finding(
                severity="warning",
                check_name="unused_returns",
                title="Unused Return Track",
                message=f'Return track "{ret.name}" does not appear to have content routed to it',
                location=f"Track: {ret.name}",
                suggestion="Remove the return if unused, or route sends to it",
            ))
    return findings


@register("empty_groups", severity="info", description="Group tracks with no children")
def check_empty_groups(project: Project) -> list[Finding]:
    findings = []
    groups = [t for t in project.tracks if t.track_type == "group"]
    for group in groups:
        children = [t for t in project.tracks if t.group_id == group.track_id]
        if not children:
            findings.append(Finding(
                severity="info",
                check_name="empty_groups",
                title="Empty Group Track",
                message=f'Group track "{group.name}" has no child tracks',
                location=f"Track: {group.name}",
                suggestion="Remove the empty group or add tracks to it",
            ))
    return findings


@register("unnamed_tracks", severity="info", description="Tracks with no user-assigned name")
def check_unnamed_tracks(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        if not track.name:
            findings.append(Finding(
                severity="info",
                check_name="unnamed_tracks",
                title="Unnamed Track",
                message=f"Track #{track.track_id} has no name",
                location=f"Track #{track.track_id}",
                suggestion="Give the track a descriptive name for better organization",
            ))
    return findings


@register("duplicate_track_names", severity="info", description="Tracks sharing the same name")
def check_duplicate_track_names(project: Project) -> list[Finding]:
    findings = []
    seen: dict[str, list[str]] = {}
    for track in project.tracks:
        if track.name:
            if track.name not in seen:
                seen[track.name] = []
            seen[track.name].append(track.track_type)
    for name, types in seen.items():
        if len(types) > 1:
            track_list = ", ".join(f"({t})" for t in types)
            findings.append(Finding(
                severity="info",
                check_name="duplicate_track_names",
                title="Duplicate Track Name",
                message=f'Multiple tracks named "{name}": {track_list}',
                location=f"Track: {name}",
                suggestion="Rename tracks to be uniquely identifiable",
            ))
    return findings
