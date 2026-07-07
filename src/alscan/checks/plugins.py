from __future__ import annotations

from pathlib import Path

from alscan.checks import Finding, register
from alscan.models import Project
from alscan.plugindirs import known_plugin_dirs


@register("broken_plugins", severity="error", description="VST/AU plugins referenced but not found on disk")
def check_broken_plugins(project: Project) -> list[Finding]:
    findings = []
    seen_paths: set[str] = set()

    for track in project.tracks:
        for device in track.devices:
            if device.plugin_ref is None:
                continue
            ref = device.plugin_ref
            if ref.is_builtin:
                continue

            path_str = ref.path.strip()
            if not path_str:
                findings.append(Finding(
                    severity="warning",
                    check_name="broken_plugins",
                    title="Plugin with No Path",
                    message=f'Plugin "{ref.name}" has no file path in the project file',
                    location=f"Track: {track.name} > Device: {device.name}",
                    suggestion="The plugin may have been removed or the project migrated from another system",
                ))
                continue

            if path_str in seen_paths:
                continue
            seen_paths.add(path_str)

            plugin_path = Path(path_str)
            if plugin_path.exists():
                continue

            found = False
            for dir_path in known_plugin_dirs():
                candidate = dir_path / plugin_path.name
                if candidate.exists():
                    found = True
                    break

            if not found:
                findings.append(Finding(
                    severity="error",
                    check_name="broken_plugins",
                    title="Missing Plugin",
                    message=f'Plugin "{ref.name}" not found at: {path_str}',
                    location=f"Track: {track.name} > Device: {device.name}",
                    suggestion="Install the missing plugin or update its path",
                    file_path=path_str,
                ))

    return findings


@register("frozen_plugins", severity="warning", description="Frozen tracks with plugins that may not re-open")
def check_frozen_plugins(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        if not track.is_frozen:
            continue
        external = [d for d in track.devices if d.plugin_ref and not d.plugin_ref.is_builtin]
        if external:
            findings.append(Finding(
                severity="warning",
                check_name="frozen_plugins",
                title="Frozen Track with External Plugins",
                message=f'Track "{track.name}" has {len(external)} external plugin(s) while frozen',
                location=f"Track: {track.name}",
                suggestion="Unfreeze to verify plugins are available. Missing plugins may prevent unfreezing.",
            ))
    return findings
