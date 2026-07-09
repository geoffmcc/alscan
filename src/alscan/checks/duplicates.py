# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from collections import defaultdict

from alscan.checks import Finding, register
from alscan.models import Project


@register("duplicate_samples", severity="info", description="Same sample used across multiple tracks")
def check_duplicate_samples(project: Project) -> list[Finding]:
    findings = []
    sample_map: dict[str, list[str]] = defaultdict(list)

    for track in project.tracks:
        for clip in track.clips:
            if clip.sample_ref is None:
                continue
            key = f"{clip.sample_ref.name}:{clip.sample_ref.original_file_size}"
            sample_map[key].append(track.name)

    for key, tracks in sample_map.items():
        if len(tracks) > 1:
            name = key.split(":")[0]
            unique = list(dict.fromkeys(tracks))
            findings.append(Finding(
                severity="info",
                check_name="duplicate_samples",
                title="Duplicate Sample",
                message=f'Sample "{name}" is used in {len(unique)} tracks',
                location=", ".join(f'"{t}"' for t in unique[:5]),
                suggestion="Use a shared audio track or grouping to reduce redundancy",
            ))
    return findings
