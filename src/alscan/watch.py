# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from alscan.models import ScanResult
from alscan.project import find_projects
from alscan.services import scan_project, ScanOptions

POLL_INTERVAL_S = 1.0
DEBOUNCE_S = 2.0
STABILITY_CHECKS = 3
STABILITY_INTERVAL_S = 0.5


@dataclass
class WatchState:
    path: Path
    projects: dict[str, ProjectWatch] = field(default_factory=dict)


@dataclass
class ProjectWatch:
    als_path: Path
    last_size: int = -1
    last_mtime: float = 0.0
    debounce_until: float = 0.0
    last_findings: set[str] = field(default_factory=set)
    last_scan_time: float = 0.0


EventCb = Callable[[str, ScanResult | None, list[str], list[str]], None]
"""Callback: (project_name, result, new_findings, resolved_findings)."""


def watch_directory(
    path: str | Path,
    event_cb: EventCb | None = None,
    cancelled_cb: Callable[[], bool] | None = None,
    options: ScanOptions | None = None,
) -> None:
    root = Path(path).resolve()
    state = WatchState(path=root)
    state.projects = _discover_projects(root)

    while True:
        if cancelled_cb and cancelled_cb():
            break

        for proj_name, pw in list(state.projects.items()):
            if cancelled_cb and cancelled_cb():
                return
            _check_project(proj_name, pw, options, event_cb)

        new_projects = _discover_projects(root)
        new_names = set(new_projects) - set(state.projects)
        for name in new_names:
            state.projects[name] = new_projects[name]
            if event_cb:
                event_cb(name, None, [], [])

        time.sleep(POLL_INTERVAL_S)


def _discover_projects(root: Path) -> dict[str, ProjectWatch]:
    projects: dict[str, ProjectWatch] = {}
    try:
        for proj_dir in find_projects(root):
            als_files = list(proj_dir.glob("*.als"))
            if len(als_files) != 1:
                continue
            als = als_files[0]
            name = proj_dir.name
            try:
                st = als.stat()
                projects[name] = ProjectWatch(
                    als_path=als,
                    last_size=st.st_size,
                    last_mtime=st.st_mtime,
                )
            except OSError:
                continue
    except (OSError, PermissionError):
        pass
    return projects


def _check_project(
    name: str,
    pw: ProjectWatch,
    options: ScanOptions | None,
    event_cb: EventCb | None,
) -> None:
    now = time.time()
    try:
        st = pw.als_path.stat()
    except OSError:
        return

    if st.st_mtime <= pw.last_mtime:
        return

    if now < pw.debounce_until:
        pw.debounce_until = now + DEBOUNCE_S
        return

    if not _file_stable(pw.als_path, st.st_size):
        return

    pw.last_mtime = st.st_mtime
    pw.last_size = st.st_size
    pw.debounce_until = now + DEBOUNCE_S
    pw.last_scan_time = now

    try:
        result = scan_project(str(pw.als_path.parent), options=options)
    except Exception:
        return

    current_keys = {_finding_key(f) for f in result.findings}
    new_keys = current_keys - pw.last_findings
    resolved_keys = pw.last_findings - current_keys

    new_findings = [k for k in new_keys]
    resolved_findings = [k for k in resolved_keys]
    pw.last_findings = current_keys

    if event_cb:
        event_cb(name, result, new_findings, resolved_findings)


def _file_stable(path: Path, initial_size: int) -> bool:
    for _ in range(STABILITY_CHECKS):
        time.sleep(STABILITY_INTERVAL_S)
        try:
            st = path.stat()
        except OSError:
            return False
        if st.st_size != initial_size:
            return False
        initial_size = st.st_size
    return True


def _finding_key(finding) -> str:
    return f"{finding.check_name}:{finding.title}:{finding.location}"
