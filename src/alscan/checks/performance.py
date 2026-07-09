# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from alscan.checks import Finding, register
from alscan.config import CheckConfig
from alscan.models import Project

HEAVY_DEVICES = {
    "Diva", "Serum", "Omnisphere", "Kontakt", "Pigments",
    "Massive", "Massive X", "Hive", "Repro", "The Legend",
    "Valhalla", "Dune", "Phase Plant", "Iris", "Ana",
    "SynthMaster", "Avenger", "Spire", "Sylenth1", "TyrellN6",
    "FabFilter Pro-R", "FabFilter Pro-L", "FabFilter Pro-MB",
    "Ozone", "Neutron", "Gullfoss", "Soothe", "Pro-Q 3",
    "Reverb", "Convolution Reverb Pro",
}

LATENCY_HEAVY = {"Ozone", "Neutron", "Gullfoss", "Soothe", "Pro-L", "L2", "L3"}


@register("frozen_tracks", severity="warning", description="Tracks that are frozen")
def check_frozen_tracks(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        if track.is_frozen:
            findings.append(Finding(
                severity="warning",
                check_name="frozen_tracks",
                title="Frozen Track",
                message=f'Track "{track.name}" is frozen',
                location=f"Track: {track.name}",
                suggestion="Unfreeze before making changes to its devices or clips",
            ))
    return findings


@register("high_device_count", severity="info", description="Tracks with unusually many devices")
def check_high_device_count(project: Project, config: CheckConfig | None = None) -> list[Finding]:
    limit = config.high_device_count if config else CheckConfig.defaults().high_device_count
    findings = []
    for track in project.tracks:
        if len(track.devices) > limit:
            findings.append(Finding(
                severity="info",
                check_name="high_device_count",
                title="High Device Count",
                message=f'Track "{track.name}" has {len(track.devices)} devices',
                location=f"Track: {track.name}",
                suggestion="Group devices into an Instrument Rack or freeze to save CPU",
            ))
    return findings


@register("cpu_heavy_plugins", severity="info", description="Known CPU-intensive plugins in the project")
def check_cpu_heavy_plugins(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        for device in track.devices:
            if device.plugin_ref and device.plugin_ref.name in HEAVY_DEVICES:
                findings.append(Finding(
                    severity="info",
                    check_name="cpu_heavy_plugins",
                    title="CPU-Heavy Plugin",
                    message=f'"{device.plugin_ref.name}" on track "{track.name}" is CPU-intensive',
                    location=f"Track: {track.name} > Device: {device.name}",
                    suggestion="Freeze this track or bounce to audio to reduce CPU usage",
                ))
    return findings


@register("high_latency_plugins", severity="info", description="Plugins known for introducing high latency")
def check_high_latency_plugins(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        for device in track.devices:
            if device.plugin_ref and device.plugin_ref.name in LATENCY_HEAVY:
                findings.append(Finding(
                    severity="info",
                    check_name="high_latency_plugins",
                    title="High-Latency Plugin",
                    message=f'"{device.plugin_ref.name}" on track "{track.name}" may introduce latency',
                    location=f"Track: {track.name} > Device: {device.name}",
                    suggestion="Disable or bypass this plugin during recording, re-enable for mixing",
                ))
    return findings


@register("unfrozen_heavy_tracks", severity="info", description="Tracks with many clips and devices that could be frozen")
def check_unfrozen_heavy_tracks(project: Project, config: CheckConfig | None = None) -> list[Finding]:
    cfg = config if config else CheckConfig.defaults()
    clip_limit = cfg.unfrozen_heavy_clips
    device_limit = cfg.unfrozen_heavy_devices
    findings = []
    for track in project.tracks:
        if track.is_frozen:
            continue
        clip_count = len(track.clips)
        device_count = len(track.devices)
        if clip_count > clip_limit and device_count > device_limit:
            findings.append(Finding(
                severity="info",
                check_name="unfrozen_heavy_tracks",
                title="Unfrozen Track with High Clip/Device Count",
                message=f'Track "{track.name}" has {clip_count} clips and {device_count} devices',
                location=f"Track: {track.name}",
                suggestion="Consider freezing this track to save CPU",
            ))
    return findings
