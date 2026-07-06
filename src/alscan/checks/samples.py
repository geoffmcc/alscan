from __future__ import annotations

from alscan.checks import Finding, register
from alscan.models import Project


@register("missing_samples", severity="error", description="Audio files referenced but not found on disk")
def check_missing_samples(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        for clip in track.clips:
            if clip.sample_ref is None:
                continue
            ref = clip.sample_ref
            if not ref.exists(project.path):
                findings.append(Finding(
                    severity="error",
                    check_name="missing_samples",
                    title="Missing Sample",
                    message=f'Sample "{ref.name}" not found at: {ref.path}',
                    location=f"Track: {track.name} > Clip: {clip.name or '(unnamed)'}",
                    suggestion="Re-link the sample in Ableton or use Collect All and Save",
                    file_path=str(ref.path),
                ))
            elif ref.relative_path_type != 3:
                findings.append(Finding(
                    severity="warning",
                    check_name="external_samples",
                    title="External Sample (Not Collected)",
                    message=f'Sample "{ref.name}" lives outside the project folder',
                    location=f"Track: {track.name} > Clip: {clip.name or '(unnamed)'}",
                    suggestion="Use File > Collect All and Save to embed it in the project",
                    file_path=str(ref.path),
                ))
    return findings


@register("missing_pack_samples", severity="info", description="Live Pack samples that may not be installed")
def check_missing_pack_samples(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        for clip in track.clips:
            if clip.sample_ref is None:
                continue
            ref = clip.sample_ref
            if ref.relative_path_type == 2 and not ref.exists(project.path):
                findings.append(Finding(
                    severity="info",
                    check_name="missing_pack_samples",
                    title="Missing Pack Sample",
                    message=f'Sample "{ref.name}" from pack "{ref.live_pack_name}" not found',
                    location=f"Track: {track.name} > Clip: {clip.name or '(unnamed)'}",
                    suggestion=f'Install the Ableton Pack "{ref.live_pack_name}" or re-link the sample',
                    file_path=str(ref.path),
                ))
    return findings
