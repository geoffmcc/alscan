# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_FILE_NAME = ".alscanrc"


@dataclass
class CheckConfig:
    high_device_count: int = 8
    extreme_tempo_low: float = 40.0
    extreme_tempo_high: float = 200.0
    unfrozen_heavy_clips: int = 20
    unfrozen_heavy_devices: int = 3
    no_locators_min_tracks: int = 5

    @classmethod
    def defaults(cls) -> CheckConfig:
        return cls()

    @classmethod
    def from_file(cls, path: str | Path) -> CheckConfig:
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        raw = path.read_text(encoding="utf-8")
        return cls.from_toml(raw)

    @classmethod
    def from_toml(cls, text: str) -> CheckConfig:
        import tomllib
        data = tomllib.loads(text)
        thresholds = data.get("thresholds", {})
        config = cls()
        for key, value in thresholds.items():
            if hasattr(config, key):
                setattr(config, key, _coerce(value, getattr(config, key)))
        return config

    @classmethod
    def discover(cls, project_dir: str | Path) -> CheckConfig | None:
        current = Path(project_dir).resolve()
        for parent in [current, *current.parents]:
            candidate = parent / CONFIG_FILE_NAME
            if candidate.is_file():
                return cls.from_file(candidate)
        return None


def _coerce(value: Any, default: Any) -> Any:
    if default is None:
        return value
    if isinstance(default, int) and isinstance(value, (int, float)):
        return int(value)
    if isinstance(default, float) and isinstance(value, (int, float)):
        return float(value)
    if isinstance(default, bool) and isinstance(value, bool):
        return value
    if type(value) is type(default):
        return value
    return default
