# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from collections import defaultdict

from alscan.checks import Finding, register
from alscan.models import Project

OVERLAP_TOLERANCE = 1e-6

SILENT_VELOCITY = 0
NEAR_SILENT_VELOCITY = 10
MAX_VELOCITY = 127


@register("empty_midi_clips", severity="info",
          description="MIDI clips that contain no MIDI note data")
def check_empty_midi_clips(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        for clip in track.clips:
            if clip.clip_type != "midi":
                continue
            if clip.duration <= 0:
                continue
            if len(clip.notes) == 0:
                findings.append(Finding(
                    severity="info",
                    check_name="empty_midi_clips",
                    title="Empty MIDI Clip",
                    message=(
                        f'Clip "{clip.name or "(unnamed)"}" on track '
                        f'"{track.name}" has no MIDI notes'
                    ),
                    location=f'Track: {track.name} > Clip: {clip.name or "(unnamed)"}',
                    suggestion=(
                        "Delete the clip if it is unused, or add notes. "
                        "Empty clips may be left over from accidental deletion."
                    ),
                ))
    return findings


@register("overlapping_notes", severity="warning",
          description="MIDI notes of the same pitch that overlap in time within a clip")
def check_overlapping_notes(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        for clip in track.clips:
            if clip.clip_type != "midi":
                continue
            if len(clip.notes) < 2:
                continue
            notes = sorted(clip.notes, key=lambda n: (n["time"], n["pitch"]))
            overlap_pitches: set[int] = set()
            total_overlaps = 0
            by_pitch: dict[int, list[dict]] = defaultdict(list)
            for n in notes:
                by_pitch[n["pitch"]].append(n)
            for pitch, pitch_notes in by_pitch.items():
                for i in range(len(pitch_notes) - 1):
                    a = pitch_notes[i]
                    b = pitch_notes[i + 1]
                    if b["time"] < a["time"] + a["duration"] - OVERLAP_TOLERANCE:
                        overlap_pitches.add(pitch)
                        total_overlaps += 1
            if overlap_pitches:
                pitches_str = ", ".join(str(p) for p in sorted(overlap_pitches)[:10])
                if len(overlap_pitches) > 10:
                    pitches_str += f" and {len(overlap_pitches) - 10} more"
                findings.append(Finding(
                    severity="warning",
                    check_name="overlapping_notes",
                    title="Overlapping MIDI Notes",
                    message=(
                        f'Clip "{clip.name or "(unnamed)"}" on track '
                        f'"{track.name}" has {total_overlaps} overlapping '
                        f'note(s) on pitch(es): {pitches_str}'
                    ),
                    location=f'Track: {track.name} > Clip: {clip.name or "(unnamed)"}',
                    suggestion=(
                        "Overlapping notes of the same pitch can cause stuck notes "
                        "in some plugins. Shorten or delete the earlier note."
                    ),
                ))
    return findings


@register("extreme_velocity", severity="info",
          description="MIDI notes with velocity at or near zero or maximum")
def check_extreme_velocity(project: Project) -> list[Finding]:
    findings = []
    for track in project.tracks:
        for clip in track.clips:
            if clip.clip_type != "midi":
                continue
            if not clip.notes:
                continue
            silent_count = 0
            near_silent_count = 0
            max_count = 0
            for note in clip.notes:
                v = note.get("velocity", 100)
                if v <= SILENT_VELOCITY:
                    silent_count += 1
                elif v < NEAR_SILENT_VELOCITY:
                    near_silent_count += 1
                if v >= MAX_VELOCITY:
                    max_count += 1

            parts = []
            if silent_count:
                parts.append(f"{silent_count} note(s) with velocity 0 (silent)")
            if near_silent_count:
                parts.append(f"{near_silent_count} note(s) with velocity 1-{NEAR_SILENT_VELOCITY - 1} (nearly silent)")
            if max_count:
                parts.append(f"{max_count} note(s) at velocity {MAX_VELOCITY} (maximum)")

            if not parts:
                continue

            clip_name = clip.name or "(unnamed)"
            findings.append(Finding(
                severity="info",
                check_name="extreme_velocity",
                title="Extreme MIDI Velocity",
                message=(
                    f'Clip "{clip_name}" on track "{track.name}" '
                    f'has {", ".join(parts)}'
                ),
                location=f'Track: {track.name} > Clip: {clip_name}',
                suggestion=(
                    "Velocity 0 notes are silent — they may be intended for key switching "
                    "or accidental. Maximum velocity notes may clip on velocity-sensitive "
                    "instruments. Review the clip in the piano roll."
                ),
            ))
    return findings
