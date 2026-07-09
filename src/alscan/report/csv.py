# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from alscan.models import ScanResult

CSV_FIELD_NAMES = [
    "project",
    "project_path",
    "severity",
    "check_name",
    "title",
    "message",
    "location",
    "suggestion",
    "file_path",
]


def _formula_safe(value: str) -> str:
    if not value:
        return value
    if value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def generate_csv_report(result: ScanResult, *, include_header: bool = True) -> str:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELD_NAMES, extrasaction="ignore",
                            quoting=csv.QUOTE_ALL, lineterminator="\n")
    if include_header:
        writer.writeheader()

    project_name = result.project.file_path.stem if result.project.file_path else "unknown"
    project_path = str(result.project.path) if result.project.path else ""

    if not result.findings:
        writer.writerow({
            "project": project_name,
            "project_path": project_path,
            "severity": "",
            "check_name": "",
            "title": "",
            "message": "",
            "location": "",
            "suggestion": "",
            "file_path": "",
        })
    else:
        for finding in result.findings:
            row = {
                "project": project_name,
                "project_path": project_path,
                "severity": finding.severity,
                "check_name": finding.check_name,
                "title": _formula_safe(finding.title),
                "message": _formula_safe(finding.message),
                "location": finding.location,
                "suggestion": _formula_safe(finding.suggestion),
                "file_path": finding.file_path,
            }
            writer.writerow(row)

    return buf.getvalue()


def generate_csv_batch(
    results: Sequence[tuple[str, ScanResult | None, str | None]],
) -> str:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELD_NAMES, extrasaction="ignore",
                            quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writeheader()
    for proj_dir, result, error in results:
        project_name = proj_dir.name if hasattr(proj_dir, "name") else str(proj_dir)
        project_path = str(proj_dir)
        if error is not None:
            writer.writerow({
                "project": project_name,
                "project_path": project_path,
                "severity": "error",
                "check_name": "scan_error",
                "title": "Scan Failed",
                "message": _formula_safe(error),
                "location": "",
                "suggestion": "Check that the project directory is accessible and contains a valid .als file",
                "file_path": "",
            })
        elif result is None:
            writer.writerow({
                "project": project_name,
                "project_path": project_path,
                "severity": "",
                "check_name": "",
                "title": "",
                "message": "",
                "location": "",
                "suggestion": "",
                "file_path": "",
            })
        elif not result.findings:
            writer.writerow({
                "project": project_name,
                "project_path": project_path,
                "severity": "",
                "check_name": "",
                "title": "",
                "message": "",
                "location": "",
                "suggestion": "",
                "file_path": "",
            })
        else:
            for finding in result.findings:
                writer.writerow({
                    "project": project_name,
                    "project_path": project_path,
                    "severity": finding.severity,
                    "check_name": finding.check_name,
                    "title": _formula_safe(finding.title),
                    "message": _formula_safe(finding.message),
                    "location": finding.location,
                    "suggestion": _formula_safe(finding.suggestion),
                    "file_path": finding.file_path,
                })
    return buf.getvalue()
