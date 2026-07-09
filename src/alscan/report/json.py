# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import json
from dataclasses import asdict

from alscan.models import ScanResult


def generate_json_report(result: ScanResult, pretty: bool = True) -> str:
    data = {
        "project": {
            "name": result.project.file_path.name if result.project.file_path else "unknown",
            "creator": result.project.creator,
            "tempo": result.project.tempo,
            "time_signature": f"{result.project.time_signature[0]}/{result.project.time_signature[1]}",
            "tracks": len(result.project.tracks),
            "track_counts": {
                "audio": sum(1 for t in result.project.tracks if t.track_type == "audio"),
                "midi": sum(1 for t in result.project.tracks if t.track_type == "midi"),
                "group": sum(1 for t in result.project.tracks if t.track_type == "group"),
                "return": sum(1 for t in result.project.tracks if t.track_type == "return"),
                "master": sum(1 for t in result.project.tracks if t.track_type == "master"),
            },
        },
        "scan_time_ms": result.scan_time_ms,
        "summary": {
            "errors": len(result.errors),
            "warnings": len(result.warnings),
            "info": len(result.info),
            "suggestions": len(result.suggestions),
            "total": len(result.findings),
        },
        "findings": [asdict(f) for f in result.findings],
    }
    indent = 2 if pretty else None
    return json.dumps(data, indent=indent, ensure_ascii=False)
