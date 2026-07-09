# SPDX-License-Identifier: GPL-3.0-only
"""Synthetic fixture factory for three-way merge analysis testing.

Builds Snapshot objects directly (bypassing .als XML parsing) so that
tests can focus on the analysis logic rather than file generation.
All fixtures are temporary and in-memory.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Any

from alscan.versioner import Snapshot


# ---------------------------------------------------------------------------
# Track builder
# ---------------------------------------------------------------------------

_track_counter: int = 0


def _next_id() -> int:
    global _track_counter
    _track_counter += 1
    return _track_counter


def reset_ids() -> None:
    global _track_counter
    _track_counter = 0


def track(
    name: str = "",
    track_id: int | None = None,
    track_type: str = "audio",
    is_frozen: bool = False,
    color_index: int = 0,
    group_id: int = -1,
    volume: float = 1.0,
    clips: int = 0,
    devices: list[dict] | None = None,
    samples: list[str] | None = None,
) -> dict:
    """Build a track dict matching alscan's Snapshot.tracks schema."""
    if track_id is None:
        track_id = _next_id()
    if devices is None:
        devices = []
    if samples is None:
        samples = []
    return {
        "track_id": track_id,
        "name": name,
        "track_type": track_type,
        "is_frozen": is_frozen,
        "color_index": color_index,
        "group_id": group_id,
        "volume": volume,
        "device_count": len(devices),
        "clip_count": clips,
        "devices": list(devices),
        "samples": list(samples),
    }


def device(
    name: str = "",
    device_type: str = "audio_effect",
    is_frozen: bool = False,
    plugin_name: str | None = None,
    plugin_type: str | None = None,
) -> dict:
    """Build a device dict."""
    return {
        "name": name,
        "device_type": device_type,
        "is_frozen": is_frozen,
        "plugin_name": plugin_name,
        "plugin_type": plugin_type,
    }


def locator(name: str, time: float = 0.0) -> dict:
    return {"name": name, "time": time}


# ---------------------------------------------------------------------------
# Snapshot builder
# ---------------------------------------------------------------------------

_snap_counter: int = 0


def _next_stamp() -> float:
    global _snap_counter
    _snap_counter += 1
    return 1_700_000_000.0 + _snap_counter


def snapshot(
    name: str = "",
    tempo: float = 120.0,
    time_signature: tuple[int, int] = (4, 4),
    tracks: list[dict] | None = None,
    locators: list[dict] | None = None,
    creator: str = "alscan-test",
    major_version: str = "12",
    minor_version: str = "1",
    fingerprint: str | None = None,
) -> Snapshot:
    """Build a Snapshot from track dicts and scalar metadata."""
    if tracks is None:
        tracks = []
    if locators is None:
        locators = []
    if name == "":
        name = f"test-project-{uuid.uuid4().hex[:8]}"
    if fingerprint is None:
        import hashlib
        h = hashlib.sha256()
        for t in sorted(tracks, key=lambda x: x["track_id"]):
            h.update(f"{t['track_id']}:{t['name']}:{t['track_type']}\n".encode())
        h.update(f"tempo:{tempo}\n".encode())
        fingerprint = h.hexdigest()[:16]

    return Snapshot(
        format_version="1",
        structural_fingerprint=fingerprint,
        project_name=name,
        timestamp=_next_stamp(),
        creator=creator,
        major_version=major_version,
        minor_version=minor_version,
        tempo=tempo,
        time_signature=list(time_signature),
        tracks=[copy.deepcopy(t) for t in tracks],
        locators=[copy.deepcopy(l) for l in locators],
    )


# ---------------------------------------------------------------------------
# Mutation helpers
# ---------------------------------------------------------------------------


def mutate(snap: Snapshot, **overrides: Any) -> Snapshot:
    """Return a copy of `snap` with the given fields replaced."""
    d = dict(
        format_version=snap.format_version,
        structural_fingerprint=snap.structural_fingerprint,
        project_name=snap.project_name,
        timestamp=snap.timestamp + 1.0,
        creator=snap.creator,
        major_version=snap.major_version,
        minor_version=snap.minor_version,
        tempo=snap.tempo,
        time_signature=list(snap.time_signature),
        tracks=[copy.deepcopy(t) for t in snap.tracks],
        locators=[copy.deepcopy(l) for l in snap.locators],
    )
    d.update(overrides)
    return Snapshot(**d)


def with_tempo(snap: Snapshot, tempo: float) -> Snapshot:
    return mutate(snap, tempo=tempo)


def with_time_signature(snap: Snapshot, num: int, den: int) -> Snapshot:
    return mutate(snap, time_signature=[num, den])


def with_tracks(snap: Snapshot, tracks: list[dict]) -> Snapshot:
    return mutate(snap, tracks=[copy.deepcopy(t) for t in tracks])


def with_locators(snap: Snapshot, locators: list[dict]) -> Snapshot:
    return mutate(snap, locators=[copy.deepcopy(l) for l in locators])


def with_track_field(snap: Snapshot, track_id: int, **kwargs: Any) -> Snapshot:
    """Modify a single track's fields in a copy of the snapshot."""
    new_tracks = []
    for t in snap.tracks:
        if t["track_id"] == track_id:
            nt = dict(t)
            if "clips" in kwargs:
                nt["clip_count"] = kwargs.pop("clips")
            if "devices" in kwargs:
                devs = kwargs.pop("devices")
                nt["devices"] = [copy.deepcopy(d) for d in devs]
                nt["device_count"] = len(devs)
            nt.update(kwargs)
            new_tracks.append(nt)
        else:
            new_tracks.append(copy.deepcopy(t))
    return with_tracks(snap, new_tracks)


def add_track(snap: Snapshot, **kwargs: Any) -> Snapshot:
    """Add a new track to the snapshot with a guaranteed-unique ID."""
    new_id = kwargs.get("track_id", _next_id())
    existing_ids = {t["track_id"] for t in snap.tracks}
    while new_id in existing_ids:
        new_id = _next_id()
    kwargs["track_id"] = new_id
    nt = track(**kwargs)
    return with_tracks(snap, snap.tracks + [nt])


def remove_track(snap: Snapshot, track_id: int) -> Snapshot:
    return with_tracks(snap, [t for t in snap.tracks if t["track_id"] != track_id])


def swap_tracks(snap: Snapshot, id_a: int, id_b: int) -> Snapshot:
    """Swap the positions of two tracks."""
    new_tracks = list(snap.tracks)
    idx_a = next(i for i, t in enumerate(new_tracks) if t["track_id"] == id_a)
    idx_b = next(i for i, t in enumerate(new_tracks) if t["track_id"] == id_b)
    new_tracks[idx_a], new_tracks[idx_b] = new_tracks[idx_b], new_tracks[idx_a]
    return with_tracks(snap, new_tracks)


def move_track(snap: Snapshot, track_id: int, new_index: int) -> Snapshot:
    """Move a track to a new position."""
    new_tracks = list(snap.tracks)
    track_obj = next(t for t in new_tracks if t["track_id"] == track_id)
    new_tracks.remove(track_obj)
    new_tracks.insert(new_index, track_obj)
    return with_tracks(snap, new_tracks)


def add_locator(snap: Snapshot, name: str, time: float) -> Snapshot:
    return with_locators(snap, snap.locators + [locator(name, time)])


def remove_locator(snap: Snapshot, name: str, time: float | None = None) -> Snapshot:
    if time is not None:
        return with_locators(snap, [
            l for l in snap.locators
            if not (l["name"] == name and l.get("time") == time)
        ])
    return with_locators(snap, [l for l in snap.locators if l["name"] != name])


def move_locator(snap: Snapshot, name: str, new_time: float) -> Snapshot:
    return with_locators(snap, [
        locator(name, new_time) if l["name"] == name else l
        for l in snap.locators
    ])


# ---------------------------------------------------------------------------
# Fixture recipes
# ---------------------------------------------------------------------------


def two_track_project(prefix: str = "test") -> Snapshot:
    """Base fixture: 2 audio tracks, 120 BPM, 4/4."""
    reset_ids()
    return snapshot(
        name=f"{prefix}-project",
        tempo=120.0,
        tracks=[
            track(name="Kick", track_id=1, track_type="audio", clips=2, color_index=1),
            track(name="Snare", track_id=2, track_type="audio", clips=3, color_index=2),
        ],
    )


def three_track_project(prefix: str = "test") -> Snapshot:
    """Base fixture: 3 audio tracks."""
    reset_ids()
    return snapshot(
        name=f"{prefix}-project",
        tempo=120.0,
        tracks=[
            track(name="Kick", track_id=1, track_type="audio", clips=2, color_index=1),
            track(name="Snare", track_id=2, track_type="audio", clips=3, color_index=2),
            track(name="Hi-Hat", track_id=3, track_type="audio", clips=4, color_index=3),
        ],
    )


def device_heavy_project(prefix: str = "test") -> Snapshot:
    """Fixture with tracks that have devices."""
    reset_ids()
    return snapshot(
        name=f"{prefix}-project",
        tempo=120.0,
        tracks=[
            track(name="Drums", track_id=1, track_type="audio", clips=2, color_index=1, devices=[
                device(name="Compressor", device_type="audio_effect", plugin_type="AudioEffect"),
                device(name="EQ Eight", device_type="audio_effect", plugin_type="AudioEffect"),
            ]),
            track(name="Bass", track_id=2, track_type="midi", clips=1, devices=[
                device(name="Operator", device_type="instrument", plugin_type="Instrument"),
            ]),
        ],
    )


def locator_project(prefix: str = "test") -> Snapshot:
    """Fixture with locators."""
    reset_ids()
    return snapshot(
        name=f"{prefix}-project",
        tempo=120.0,
        tracks=[
            track(name="Audio", track_id=1, track_type="audio", clips=1),
        ],
        locators=[
            locator("Intro", 1.0),
            locator("Verse", 9.0),
            locator("Chorus", 17.0),
            locator("Outro", 65.0),
        ],
    )


def large_project(prefix: str = "big", n_tracks: int = 50) -> Snapshot:
    """Generate a project with many tracks."""
    reset_ids()
    tracks = []
    for i in range(1, n_tracks + 1):
        tracks.append(track(
            name=f"Track {i}",
            track_id=i,
            track_type="audio" if i % 3 != 0 else "midi",
            clips=i % 5,
            color_index=i % 8,
            group_id=(i % 4) if i % 3 == 0 else -1,
        ))
    return snapshot(name=f"{prefix}-project", tracks=tracks)
