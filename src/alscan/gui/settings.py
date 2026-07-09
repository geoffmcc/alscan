# SPDX-License-Identifier: GPL-3.0-only
"""Application settings management using QSettings."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QByteArray

from alscan.gui.theme import ThemeMode


class AppSettings:
    def __init__(self) -> None:
        self._settings = QSettings("ALScan", "ALScan")

    @property
    def theme(self) -> str:
        return self._settings.value("theme", "system")

    @theme.setter
    def theme(self, value: str) -> None:
        self._settings.setValue("theme", value)

    @property
    def default_output_dir(self) -> str:
        return self._settings.value("default_output_dir", "")

    @default_output_dir.setter
    def default_output_dir(self, value: str) -> None:
        self._settings.setValue("default_output_dir", value)

    @property
    def auto_open_reports(self) -> bool:
        return self._settings.value("auto_open_reports", "true") == "true"

    @auto_open_reports.setter
    def auto_open_reports(self, value: bool) -> None:
        self._settings.setValue("auto_open_reports", "true" if value else "false")

    @property
    def confirm_overwrite(self) -> bool:
        return self._settings.value("confirm_overwrite", "true") == "true"

    @confirm_overwrite.setter
    def confirm_overwrite(self, value: bool) -> None:
        self._settings.setValue("confirm_overwrite", "true" if value else "false")

    @property
    def max_recent(self) -> int:
        return int(self._settings.value("max_recent", "10"))

    @max_recent.setter
    def max_recent(self, value: int) -> None:
        self._settings.setValue("max_recent", str(value))

    @property
    def recent_paths(self) -> list[str]:
        raw = self._settings.value("recent_paths", [])
        if isinstance(raw, str):
            return [raw]
        if raw is None:
            return []
        return list(raw)

    @recent_paths.setter
    def recent_paths(self, paths: list[str]) -> None:
        self._settings.setValue("recent_paths", paths)

    @property
    def window_geometry(self) -> QByteArray | None:
        return self._settings.value("window_geometry", None)

    @window_geometry.setter
    def window_geometry(self, geo: QByteArray) -> None:
        self._settings.setValue("window_geometry", geo)

    @property
    def verbose_scan(self) -> bool:
        return self._settings.value("verbose_scan", "false") == "true"

    @verbose_scan.setter
    def verbose_scan(self, value: bool) -> None:
        self._settings.setValue("verbose_scan", "true" if value else "false")

    def add_recent_path(self, path: str) -> None:
        paths = self.recent_paths
        path_str = str(Path(path).resolve())
        if path_str in paths:
            paths.remove(path_str)
        paths.insert(0, path_str)
        max_r = self.max_recent
        if len(paths) > max_r:
            paths = paths[:max_r]
        self.recent_paths = paths

    def reset(self) -> None:
        self._settings.clear()
