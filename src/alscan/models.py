# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


TrackType = Literal["audio", "midi", "group", "return", "master"]
PluginType = Literal["vst2", "vst3", "au", "builtin"]
Severity = Literal["error", "warning", "info", "suggestion"]


@dataclass
class SampleRef:
    name: str
    path: str
    relative_path: str = ""
    relative_path_type: int = 0
    original_file_size: int = 0
    original_crc: int = 0
    live_pack_name: str = ""

    def resolved_path(self, project_dir: Path | None = None) -> Path | None:
        p = Path(self.path)
        if p.exists():
            return p.resolve()
        if project_dir and self.relative_path:
            rp = project_dir / self.relative_path
            if rp.exists():
                return rp.resolve()
        return None

    def exists(self, project_dir: Path | None = None) -> bool:
        return self.resolved_path(project_dir) is not None


@dataclass
class PluginRef:
    name: str
    plugin_type: PluginType
    path: str = ""
    unique_id: str = ""
    manufacturer: str = ""
    is_builtin: bool = False

    def exists(self) -> bool:
        if self.is_builtin:
            return True
        if self.path and Path(self.path).exists():
            return True
        return False


@dataclass
class Clip:
    name: str
    clip_type: Literal["audio", "midi"]
    color_index: int = 0
    start_time: float = 0.0
    duration: float = 0.0
    is_warped: bool = False
    warp_mode: int = 0
    loop_on: bool = False
    sample_ref: SampleRef | None = None
    notes: list[dict] = field(default_factory=list)


@dataclass
class Device:
    name: str
    device_type: str
    plugin_ref: PluginRef | None = None
    is_frozen: bool = False


@dataclass
class Track:
    name: str
    track_id: int
    track_type: TrackType
    color_index: int = 0
    is_frozen: bool = False
    group_id: int = -1
    volume: float = 1.0
    devices: list[Device] = field(default_factory=list)
    clips: list[Clip] = field(default_factory=list)


@dataclass
class Project:
    path: Path
    file_path: Path | None = None
    creator: str = ""
    major_version: str = ""
    minor_version: str = ""
    tempo: float = 120.0
    time_signature: tuple[int, int] = (4, 4)
    tracks: list[Track] = field(default_factory=list)
    locators: list[dict] = field(default_factory=list)


@dataclass
class Finding:
    severity: Severity
    check_name: str
    title: str
    message: str
    location: str = ""
    suggestion: str = ""
    file_path: str = ""

    def dict(self) -> dict:
        return {
            "severity": self.severity,
            "check_name": self.check_name,
            "title": self.title,
            "message": self.message,
            "location": self.location,
            "suggestion": self.suggestion,
            "file_path": self.file_path,
        }


@dataclass
class ScanResult:
    project: Project
    findings: list[Finding] = field(default_factory=list)
    scan_time_ms: float = 0.0

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def info(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "info"]

    @property
    def suggestions(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "suggestion"]
