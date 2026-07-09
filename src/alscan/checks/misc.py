# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from alscan.checks import Finding, register
from alscan.models import Project


@register("warped_clips", severity="info", description="Audio clips with warping enabled")
def check_warped_clips(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        for clip in track.clips:
            if clip.clip_type == "audio" and clip.is_warped:
                findings.append(Finding(
                    severity="info",
                    check_name="warped_clips",
                    title="Warped Audio Clip",
                    message=f'Clip "{clip.name or "(unnamed)"}" on track "{track.name}" has warping enabled',
                    location=f"Track: {track.name} > Clip: {clip.name or '(unnamed)'}",
                    suggestion="Disable warping if the clip doesn't need tempo stretching for better audio quality",
                ))
    return findings


@register("master_chain_plugins", severity="info", description="Master track has plugin devices")
def check_master_chain_plugins(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        if track.track_type != "master":
            continue
        if track.devices:
            names = ", ".join(d.name for d in track.devices)
            findings.append(Finding(
                severity="info",
                check_name="master_chain_plugins",
                title="Master Chain Plugins",
                message=f'Master chain has {len(track.devices)} device(s): {names}',
                location="Master track",
                suggestion="Master chain plugins affect the entire mix and can add significant CPU load",
            ))
    return findings


@register("extreme_tempo", severity="info", description="Project tempo outside 40-200 BPM range")
def check_extreme_tempo(project: Project) -> list[Finding]:
    findings = []
    if project.tempo < 40:
        findings.append(Finding(
            severity="info",
            check_name="extreme_tempo",
            title="Very Low Tempo",
            message=f'Project tempo is {project.tempo} BPM — unusually low',
            location="Project settings",
            suggestion="Verify the tempo is intentional. Extremely low tempos can affect plugin behavior and timing",
        ))
    elif project.tempo > 200:
        findings.append(Finding(
            severity="info",
            check_name="extreme_tempo",
            title="Very High Tempo",
            message=f'Project tempo is {project.tempo} BPM — unusually high',
            location="Project settings",
            suggestion="Verify the tempo is intentional. Extremely high tempos may cause performance issues",
        ))
    return findings


@register("no_locators", severity="info", description="Project has no locators/markers")
def check_no_locators(project: Project) -> list[Finding]:
    findings = []
    if len(project.locators) == 0 and len(project.tracks) > 5:
        findings.append(Finding(
            severity="info",
            check_name="no_locators",
            title="No Locators",
            message="Project has no locators/markers",
            location="Project settings",
            suggestion="Add locators to mark song sections (verse, chorus, bridge) for easier navigation",
        ))
    return findings
