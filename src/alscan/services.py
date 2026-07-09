# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import json
import time
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from alscan.checks import Check, list_checks as _list_checks
from alscan.config import CheckConfig
from alscan.io_safety import (
    atomic_write as _atomic_write_report,
    validate_output_dest,
)
from alscan.merge.analysis import build_merge_plan
from alscan.merge.inputs import validate_three_way
from alscan.merge.plan import MergePlan
from alscan.merge.report import render_merge_report
from alscan.models import ScanResult
from alscan.parser import parse_als
from alscan.project import find_als_file, find_projects
from alscan.report.html import generate_html_report
from alscan.report.json import generate_json_report
from alscan.versioner import (
    Snapshot,
    SNAPSHOT_FORMAT_VERSION,
    build_snapshot,
    diff_snapshots,
    find_snapshots,
    load_snapshot,
    save_snapshot,
    DiffResult,
)


ProgressCb = Callable[[int, int, str], None]
"""Callback signature for progress updates: (completed, total, current_label)."""

CancelledCb = Callable[[], bool]
"""Callback that returns True if the operation should be cancelled."""


def _invoke_check(check: Check, project, config: CheckConfig | None):
    try:
        sig = inspect.signature(check.func)
        if "config" in sig.parameters:
            return check.func(project, config=config)
    except (ValueError, TypeError):
        pass
    return check.func(project)


class ScanError(Exception):
    pass


class SnapshotError(Exception):
    pass


class CompareError(Exception):
    pass


class MergePlanError(Exception):
    pass


class ReportError(Exception):
    pass


@dataclass
class ScanOptions:
    format: Literal["terminal", "json", "html", "csv"] = "terminal"
    verbose: bool = False
    pretty: bool = True
    check_config: CheckConfig | None = None


@dataclass
class SnapshotInfo:
    path: Path
    timestamp: float
    project_name: str
    tempo: float
    track_count: int
    device_count: int

    @classmethod
    def from_snapshot(cls, path: Path, snap: Snapshot) -> SnapshotInfo:
        return cls(
            path=path,
            timestamp=snap.timestamp,
            project_name=snap.project_name,
            tempo=snap.tempo,
            track_count=snap.track_count,
            device_count=snap.device_count,
        )


def scan_project(
    path: str | Path,
    options: ScanOptions | None = None,
    progress_cb: ProgressCb | None = None,
    cancelled_cb: CancelledCb | None = None,
) -> ScanResult:
    path = Path(path)
    als_file = find_als_file(path)
    if als_file is None:
        resolved = Path(path).resolve()
        if resolved.is_dir():
            als_files = list(resolved.glob("*.als"))
            if len(als_files) > 1:
                raise ScanError(
                    f"Multiple .als files found at: {resolved}\n"
                    f"  Specify one: <project_folder>/<filename>.als"
                )
        raise ScanError(f"Could not find a .als file at: {path}")

    if cancelled_cb and cancelled_cb():
        raise ScanError("Scan cancelled")

    if progress_cb:
        progress_cb(0, 1, als_file.name)

    start = time.time()
    try:
        project = parse_als(als_file)
    except Exception as e:
        raise ScanError(f"Error parsing {als_file}: {e}") from e

    if cancelled_cb and cancelled_cb():
        raise ScanError("Scan cancelled")

    from alscan.checks import list_checks
    findings = []
    checks = list_checks()
    config = options.check_config if options else None
    for i, check in enumerate(checks):
        if cancelled_cb and cancelled_cb():
            raise ScanError("Scan cancelled")
        try:
            result = _invoke_check(check, project, config)
            findings.extend(result)
        except Exception as e:
            findings.append(Finding(
                severity="warning",
                check_name=check.name,
                title=f"Check \"{check.name}\" failed to run",
                message=f"The check did not complete. Technical detail: {e}",
                location="internal",
                suggestion="Re-run the scan. If the problem persists, report this issue.",
            ))

    elapsed = (time.time() - start) * 1000
    return ScanResult(project=project, findings=findings, scan_time_ms=round(elapsed, 1))


def scan_projects_recursive(
    root: str | Path,
    options: ScanOptions | None = None,
    progress_cb: ProgressCb | None = None,
    cancelled_cb: CancelledCb | None = None,
) -> list[tuple[Path, ScanResult | None, str | None]]:
    root = Path(root).resolve()
    projects = find_projects(root)
    results: list[tuple[Path, ScanResult | None, str | None]] = []

    total = len(projects)
    for i, proj_dir in enumerate(projects):
        if cancelled_cb and cancelled_cb():
            raise ScanError("Recursive scan cancelled")
        if progress_cb:
            progress_cb(i, total, proj_dir.name)
        try:
            r = scan_project(proj_dir, options, None, cancelled_cb)
            results.append((proj_dir, r, None))
        except ScanError as e:
            results.append((proj_dir, None, str(e)))
        except Exception as e:
            results.append((proj_dir, None, str(e)))

    if progress_cb:
        progress_cb(total, total, "Complete")
    return results


def get_checks() -> list[Check]:
    return sorted(_list_checks(), key=lambda x: x.name)


def get_check(name: str) -> Check | None:
    from alscan.checks import get_check as _get
    return _get(name)


def create_snapshot(path: str | Path) -> Path:
    path_obj = Path(path)
    als_file = find_als_file(path_obj)
    if als_file is None:
        raise SnapshotError(f"Could not find a .als file at: {path}")
    try:
        proj = parse_als(als_file)
    except Exception as e:
        raise SnapshotError(f"Error parsing {als_file}: {e}") from e
    try:
        dest = save_snapshot(proj, als_file.parent)
    except Exception as e:
        raise SnapshotError(f"Error saving snapshot: {e}") from e
    return dest


def list_snapshots(path: str | Path) -> list[SnapshotInfo]:
    path_obj = Path(path)
    als_file = find_als_file(path_obj)
    if als_file is None:
        raise SnapshotError(f"Could not find a .als file at: {path}")
    snaps = find_snapshots(als_file.parent)
    result: list[SnapshotInfo] = []
    for snap_path in snaps:
        try:
            snap = load_snapshot(snap_path)
            result.append(SnapshotInfo.from_snapshot(snap_path, snap))
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
    return result


def _load_any_source(path: str | Path) -> Snapshot:
    p = Path(path).resolve()
    if p.is_dir():
        raise CompareError(
            "Expected an .als project file or alscan snapshot .json file, "
            f"but received a directory: {p}"
        )
    if p.suffix == ".json":
        try:
            snap = load_snapshot(p)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            raise CompareError(f"Error reading snapshot {p}: {e}") from e
        if snap.format_version != SNAPSHOT_FORMAT_VERSION:
            raise CompareError(
                f"Unsupported snapshot format version '{snap.format_version}' "
                f"(expected '{SNAPSHOT_FORMAT_VERSION}')"
            )
        return snap
    try:
        return build_snapshot(parse_als(p))
    except Exception as e:
        raise CompareError(f"Error parsing {p}: {e}") from e


def compare_sources(
    path_a: str | Path,
    path_b: str | Path,
) -> DiffResult:
    snap_a = _load_any_source(path_a)
    snap_b = _load_any_source(path_b)
    return diff_snapshots(snap_a, snap_b)


def create_merge_plan(
    base_path: str | Path,
    ours_path: str | Path,
    theirs_path: str | Path,
    allow_unrelated: bool = False,
    allow_plausible: bool = False,
) -> MergePlan:
    try:
        inputs = validate_three_way(
            str(base_path), str(ours_path), str(theirs_path),
            allow_unrelated=allow_unrelated,
            allow_plausible=allow_plausible,
        )
    except (FileNotFoundError, ValueError) as e:
        raise MergePlanError(str(e)) from e

    return build_merge_plan(inputs)


def render_health_report(result: ScanResult, fmt: str, pretty: bool = True) -> str:
    if fmt == "json":
        return generate_json_report(result, pretty=pretty)
    elif fmt == "html":
        return generate_html_report(result)
    elif fmt == "csv":
        from alscan.report.csv import generate_csv_report
        return generate_csv_report(result)
    else:
        from alscan.report.terminal import print_terminal_report
        return print_terminal_report(result)


def save_report(
    content: str,
    dest: Path,
    source_paths: list[Path] | None = None,
) -> Path:
    sources = source_paths or []
    try:
        validate_output_dest(dest, sources)
    except (ValueError, FileExistsError) as e:
        raise ReportError(str(e)) from e
    try:
        _atomic_write_report(dest, content)
    except OSError as e:
        raise ReportError(f"Could not write to {dest}: {e}") from e
    return dest


def save_merge_plan(plan: MergePlan, dest: Path, sources: list[Path]) -> Path:
    json_str = plan.to_json()
    try:
        validate_output_dest(dest, sources)
    except (ValueError, FileExistsError) as e:
        raise ReportError(str(e)) from e
    try:
        _atomic_write_report(dest, json_str)
    except OSError as e:
        raise ReportError(f"Could not write merge plan to {dest}: {e}") from e
    return dest


def save_merge_report(plan: MergePlan, dest: Path, sources: list[Path]) -> Path:
    html = render_merge_report(plan)
    try:
        validate_output_dest(dest, sources)
    except (ValueError, FileExistsError) as e:
        raise ReportError(str(e)) from e
    try:
        _atomic_write_report(dest, html)
    except OSError as e:
        raise ReportError(f"Could not write merge report to {dest}: {e}") from e
    return dest
