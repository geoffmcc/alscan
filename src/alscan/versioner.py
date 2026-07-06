from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from alscan.models import Project
from alscan.parser import parse_als


SNAPSHOTS_DIR = ".alscan/snapshots"
SNAPSHOT_FORMAT_VERSION = "1"

_REQUIRED_SNAPSHOT_FIELDS = {
    "format_version": str,
    "project_name": str,
    "timestamp": (int, float),
    "structural_fingerprint": str,
    "creator": str,
    "major_version": str,
    "minor_version": str,
    "tempo": (int, float),
    "time_signature": list,
    "tracks": list,
    "locators": list,
}


def _type_name(tp):
    if isinstance(tp, tuple):
        return "(" + ", ".join(t.__name__ for t in tp) + ")"
    return tp.__name__


@dataclass
class Snapshot:
    format_version: str
    structural_fingerprint: str
    project_name: str
    timestamp: float
    creator: str
    major_version: str
    minor_version: str
    tempo: float
    time_signature: list[int]
    tracks: list[dict]
    locators: list[dict]

    @property
    def track_count(self) -> int:
        return len(self.tracks)

    @property
    def device_count(self) -> int:
        return sum(t["device_count"] for t in self.tracks)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> Snapshot:
        d = json.loads(data)
        missing = _REQUIRED_SNAPSHOT_FIELDS.keys() - d.keys()
        if missing:
            raise ValueError(f"Snapshot missing required fields: {', '.join(sorted(missing))}")
        extra = d.keys() - _REQUIRED_SNAPSHOT_FIELDS.keys()
        if extra:
            raise ValueError(f"Snapshot has unknown fields: {', '.join(sorted(extra))}")
        for field, expected_type in _REQUIRED_SNAPSHOT_FIELDS.items():
            val = d[field]
            if not isinstance(val, expected_type):
                expected_name = _type_name(expected_type)
                raise TypeError(
                    f"Snapshot field '{field}' expected {expected_name}, got {type(val).__name__}"
                )
        if d["format_version"] != SNAPSHOT_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported snapshot format version '{d['format_version']}' "
                f"(expected '{SNAPSHOT_FORMAT_VERSION}')"
            )
        return cls(**d)


def _structural_fingerprint(proj: Project) -> str:
    h = hashlib.sha256()
    for t in sorted(proj.tracks, key=lambda x: x.track_id):
        h.update(f"{t.track_id}:{t.name}:{t.track_type}:{t.is_frozen}:{t.color_index}:{t.group_id}\n".encode())
        for d in t.devices:
            h.update(f"  dev:{d.name}:{d.device_type}:{d.is_frozen}\n".encode())
            if d.plugin_ref:
                h.update(f"  plugin:{d.plugin_ref.name}:{d.plugin_ref.plugin_type}\n".encode())
        for c in t.clips:
            h.update(f"  clip:{c.name}:{c.clip_type}\n".encode())
            if c.sample_ref:
                h.update(f"  sample:{c.sample_ref.name}:{c.sample_ref.relative_path}\n".encode())
    h.update(f"tempo:{proj.tempo}\n".encode())
    h.update(f"time_sig:{proj.time_signature[0]}/{proj.time_signature[1]}\n".encode())
    return h.hexdigest()[:16]


def _track_dict(track) -> dict:
    return {
        "track_id": track.track_id,
        "name": track.name,
        "track_type": track.track_type,
        "is_frozen": track.is_frozen,
        "color_index": track.color_index,
        "group_id": track.group_id,
        "volume": track.volume,
        "device_count": len(track.devices),
        "clip_count": len(track.clips),
        "devices": [
            {
                "name": d.name,
                "device_type": d.device_type,
                "is_frozen": d.is_frozen,
                "plugin_name": d.plugin_ref.name if d.plugin_ref else None,
                "plugin_type": d.plugin_ref.plugin_type if d.plugin_ref else None,
            }
            for d in track.devices
        ],
        "samples": sorted(
            {c.sample_ref.name for c in track.clips if c.sample_ref}
        ),
    }


def build_snapshot(proj: Project) -> Snapshot:
    return Snapshot(
        format_version=SNAPSHOT_FORMAT_VERSION,
        structural_fingerprint=_structural_fingerprint(proj),
        project_name=proj.file_path.stem if proj.file_path else "unknown",
        timestamp=time.time(),
        creator=proj.creator,
        major_version=proj.major_version,
        minor_version=proj.minor_version,
        tempo=proj.tempo,
        time_signature=list(proj.time_signature),
        tracks=[_track_dict(t) for t in proj.tracks],
        locators=proj.locators,
    )


def save_snapshot(proj: Project, project_dir: Path) -> Path:
    snap = build_snapshot(proj)
    snap_dir = _safe_snapshots_dir(project_dir)
    snap_dir.mkdir(parents=True, exist_ok=True)
    suffix = uuid.uuid4().hex[:12]
    stem = f"{snap.project_name}-{int(snap.timestamp)}-{suffix}"
    path = snap_dir / f"{stem}.json"
    tmp = snap_dir / f".{stem}.tmp.{uuid.uuid4().hex[:8]}"
    tmp.write_text(snap.to_json(), encoding="utf-8")
    try:
        os.fsync(tmp.open("rb").fileno())
    except OSError:
        pass
    tmp.replace(path)
    return path


def load_snapshot(path: Path) -> Snapshot:
    raw = path.read_text(encoding="utf-8")
    return Snapshot.from_json(raw)


def find_snapshots(project_dir: Path) -> list[Path]:
    snap_dir = _safe_snapshots_dir(project_dir)
    if not snap_dir.is_dir():
        return []
    snaps = []
    for p in snap_dir.glob("*.json"):
        try:
            raw = p.read_text(encoding="utf-8")
            d = json.loads(raw)
            ts = d.get("timestamp", 0.0)
            snaps.append((ts, p))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
    snaps.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in snaps]


def _safe_snapshots_dir(project_dir: Path) -> Path:
    resolved = project_dir.resolve()
    snap_dir = resolved / SNAPSHOTS_DIR
    parts = snap_dir.relative_to(resolved).parts
    for i in range(1, len(parts) + 1):
        check = resolved / Path(*parts[:i])
        if check.is_symlink() or check.is_junction():
            raise PermissionError(
                f"Path component is a symlink or junction; refusing to follow: {check}"
            )
    if snap_dir.exists():
        parent = snap_dir.resolve()
        try:
            parent.relative_to(resolved)
        except ValueError:
            raise PermissionError(
                f".alscan/snapshots resolves outside the project directory: {parent}"
            )
    return snap_dir


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

ChangeKind = Literal["added", "removed", "modified", "unchanged"]


@dataclass
class TrackChange:
    kind: ChangeKind
    track_id: int
    name: str
    details: list[str] = None

    def __post_init__(self):
        if self.details is None:
            self.details = []


@dataclass
class DiffResult:
    project_a: str
    project_b: str
    tempo_changed: bool = False
    tempo_before: float = 0.0
    tempo_after: float = 0.0
    time_sig_changed: bool = False
    ts_before: list[int] = None
    ts_after: list[int] = None
    locators_changed: bool = False
    locators_before: list[dict] = None
    locators_after: list[dict] = None
    added_locators: list[dict] = None
    removed_locators: list[dict] = None
    track_changes: list[TrackChange] = None

    def __post_init__(self):
        if self.track_changes is None:
            self.track_changes = []
        if self.ts_before is None:
            self.ts_before = [4, 4]
        if self.ts_after is None:
            self.ts_after = [4, 4]
        if self.locators_before is None:
            self.locators_before = []
        if self.locators_after is None:
            self.locators_after = []
        if self.added_locators is None:
            self.added_locators = []
        if self.removed_locators is None:
            self.removed_locators = []

    @property
    def has_changes(self) -> bool:
        return self.tempo_changed or self.time_sig_changed or self.locators_changed or bool(self.track_changes)


def diff_snapshots(a: Snapshot, b: Snapshot) -> DiffResult:
    result = DiffResult(
        project_a=a.project_name,
        project_b=b.project_name,
    )

    if a.tempo != b.tempo:
        result.tempo_changed = True
        result.tempo_before = a.tempo
        result.tempo_after = b.tempo

    if a.time_signature != b.time_signature:
        result.time_sig_changed = True
        result.ts_before = a.time_signature
        result.ts_after = b.time_signature

    if a.locators != b.locators:
        result.locators_changed = True
        result.locators_before = a.locators
        result.locators_after = b.locators
        a_set = {(loc["name"], loc.get("time", 0.0)) for loc in a.locators}
        b_set = {(loc["name"], loc.get("time", 0.0)) for loc in b.locators}
        result.added_locators = [dict(name=n, time=t) for n, t in b_set - a_set]
        result.removed_locators = [dict(name=n, time=t) for n, t in a_set - b_set]

    a_tracks = {t["track_id"]: t for t in a.tracks}
    b_tracks = {t["track_id"]: t for t in b.tracks}

    all_ids = set(a_tracks) | set(b_tracks)
    for tid in sorted(all_ids):
        if tid in a_tracks and tid not in b_tracks:
            result.track_changes.append(TrackChange(
                kind="removed", track_id=tid, name=a_tracks[tid]["name"],
            ))
        elif tid not in a_tracks and tid in b_tracks:
            result.track_changes.append(TrackChange(
                kind="added", track_id=tid, name=b_tracks[tid]["name"],
            ))
        else:
            ta, tb = a_tracks[tid], b_tracks[tid]
            details = []
            if ta["name"] != tb["name"]:
                details.append(f'name: "{ta["name"]}" -> "{tb["name"]}"')
            if ta["track_type"] != tb["track_type"]:
                details.append(f'type: {ta["track_type"]} -> {tb["track_type"]}')
            if ta["is_frozen"] != tb["is_frozen"]:
                details.append(f'frozen: {ta["is_frozen"]} -> {tb["is_frozen"]}')
            if ta["device_count"] != tb["device_count"]:
                details.append(f'devices: {ta["device_count"]} -> {tb["device_count"]}')
            if ta["clip_count"] != tb["clip_count"]:
                details.append(f'clips: {ta["clip_count"]} -> {tb["clip_count"]}')
            if details:
                result.track_changes.append(TrackChange(
                    kind="modified", track_id=tid, name=tb["name"], details=details,
                ))

    return result
