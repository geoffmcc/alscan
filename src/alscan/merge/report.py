from __future__ import annotations

import json
import math
from dataclasses import asdict
from html import escape
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from alscan.merge.plan import MergePlan


def render_merge_report(plan: MergePlan | dict[str, Any]) -> str:
    """Render a consumer-facing HTML report from a MergePlan v2 document.

    This renderer is deliberately presentation-only. It consumes the plan model
    produced by merge analysis and does not recompute identity, ordering,
    locator, or merge semantics.
    """
    data = _plan_dict(plan)
    _validate_v2(data)

    title = "alscan merge conflict report"
    conflicts = _sorted_items(data.get("conflicts", []), "field", "id")
    auto_resolved = _sorted_items(data.get("auto_resolved", []), "field", "id")
    identity_matches = _sorted_identity_matches(data.get("identity_matches", []))
    track_changes = _sorted_items(data.get("track_changes", []), "kind", "branch", "id")
    locator_changes = _sorted_locator_changes(data.get("locator_changes", []))
    proposed_track_order = _sorted_items(data.get("proposed_track_order", []), "position", "track_id", "name")
    warnings = sorted(str(w) for w in data.get("warnings", []))

    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_h(title)}</title>",
        "<style>",
        _CSS,
        "</style>",
        "</head>",
        "<body>",
        "<main>",
        f"<h1>{_h(title)}</h1>",
        _summary(data),
        _sources(data),
        _warnings(warnings),
        _section("Conflicts requiring review", conflicts, _conflict_card, empty="No conflicts detected."),
        _section("Auto-resolved changes", auto_resolved, _auto_card, empty="No auto-resolved changes."),
        _section("Track changes", track_changes, _track_card, empty="No track changes."),
        _section("Locator changes", locator_changes, _locator_card, empty="No locator changes."),
        _section("Identity matches", identity_matches, _identity_card, empty="No identity matches."),
        _section("Proposed track order (analysis-only)", proposed_track_order, _generic_card, empty="No proposed track order."),
        _supported_scope(data),
        _privacy_footer(),
        "</main>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts) + "\n"


def _plan_dict(plan: MergePlan | dict[str, Any]) -> dict[str, Any]:
    if isinstance(plan, MergePlan):
        return asdict(plan)
    if isinstance(plan, dict):
        return plan
    raise TypeError("merge report requires a MergePlan or MergePlan dictionary")


def _validate_v2(data: dict[str, Any]) -> None:
    if data.get("document_type") != "alscan-merge-plan":
        raise ValueError("merge report requires an alscan-merge-plan document")
    if str(data.get("format_version")) != "2":
        raise ValueError("merge report requires MergePlan format_version 2")
    required = {
        "document_type": str,
        "format_version": str,
        "alscan_version": str,
        "created_at_utc": str,
        "input_mode": str,
        "sources": dict,
        "source_structural_fingerprints": dict,
        "supported_field_scope": list,
        "lineage_confidence": str,
        "conflict_count": int,
        "warning_count": int,
        "auto_resolved": list,
        "conflicts": list,
        "identity_matches": list,
        "track_changes": list,
        "locator_changes": list,
        "proposed_track_order": list,
        "file_differences_detected": bool,
        "warnings": list,
    }
    for key, expected in required.items():
        if key not in data:
            raise ValueError(f"merge report missing required field: {key}")
        if not isinstance(data[key], expected):
            raise ValueError(f"merge report field has incorrect type: {key}")
    if data["input_mode"] not in ("als", "snapshot"):
        raise ValueError("merge report input_mode must be 'als' or 'snapshot'")
    _validate_sources(data["sources"])
    _validate_string_list(data["supported_field_scope"], "supported_field_scope")
    _validate_string_list(data["warnings"], "warnings")
    _validate_records(data["conflicts"], "conflicts", {
        "id": str, "field": str, "reason": str, "risk": str,
        "available_resolutions": list, "auto_blocked": bool,
    })
    for index, item in enumerate(data["conflicts"]):
        _validate_string_list(item["available_resolutions"], f"conflicts[{index}].available_resolutions")
    _validate_records(data["auto_resolved"], "auto_resolved", {
        "id": str, "field": str, "resolution": str, "description": str,
    })
    _validate_records(data["identity_matches"], "identity_matches", {
        "track_id": int, "name": str, "base_track_id": int,
        "confidence": str, "classification": str, "evidence": list,
        "auto_resolved": bool, "warnings": list,
    })
    for index, item in enumerate(data["identity_matches"]):
        for optional_id in ("ours_track_id", "theirs_track_id"):
            if item.get(optional_id) is not None and not isinstance(item.get(optional_id), int):
                raise ValueError(f"identity_matches[{index}].{optional_id} has incorrect type")
        _validate_string_list(item["evidence"], f"identity_matches[{index}].evidence")
        _validate_string_list(item["warnings"], f"identity_matches[{index}].warnings")
    _validate_records(data["track_changes"], "track_changes", {
        "id": str, "kind": str, "branch": str, "name": str,
        "auto_resolved": bool, "details": dict,
    })
    for index, item in enumerate(data["track_changes"]):
        for optional_id in ("track_id", "base_track_id", "branch_track_id"):
            if item.get(optional_id) is not None and not isinstance(item.get(optional_id), int):
                raise ValueError(f"track_changes[{index}].{optional_id} has incorrect type")
        if item.get("proposed_position") is not None and not isinstance(item.get("proposed_position"), dict):
            raise ValueError(f"track_changes[{index}].proposed_position has incorrect type")
    _validate_records(data["locator_changes"], "locator_changes", {
        "id": str, "kind": str, "name": str, "branch": str,
        "auto_resolved": bool, "details": dict,
    })
    _validate_proposed_order(data["proposed_track_order"])
    _reject_non_finite(data)


def _sorted_items(items: Any, *keys: str) -> list[dict[str, Any]]:
    rows = [item for item in items if isinstance(item, dict)]
    return sorted(rows, key=lambda item: tuple(str(item.get(key, "")) for key in keys))


def _sorted_identity_matches(items: Any) -> list[dict[str, Any]]:
    rows = [item for item in items if isinstance(item, dict)]
    order = {"exact": 0, "plausible": 1, "ambiguous": 2, "unmatched": 3}
    return sorted(rows, key=lambda item: (order.get(str(item.get("classification", "")), 99), str(item.get("track_id", ""))))


def _sorted_locator_changes(items: Any) -> list[dict[str, Any]]:
    rows = [item for item in items if isinstance(item, dict)]
    order = {"added": 0, "moved": 1, "removed": 2, "ambiguous": 3}
    return sorted(rows, key=lambda item: (order.get(str(item.get("kind", "")), 99), str(item.get("name", "")), str(item.get("id", ""))))


def _h(value: Any) -> str:
    if value is None:
        return ""
    return escape(str(value), quote=True)


def _json(value: Any) -> str:
    safe = _redact_private(value)
    return _h(json.dumps(safe, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False))


def _privacy_footer() -> str:
    return (
        '<footer class="privacy-footer">'
        "<h2>Privacy warning</h2>"
        "<p>This report contains structural project metadata. Track names, locator names, "
        "source labels, hashes, plugin/device names, and sample names may reveal unreleased "
        "work, collaborators, clients, or local workflow details. Review before sharing.</p>"
        "<p>This report is read-only. It does not modify source files, create merged metadata, "
        "write .als files, or apply conflict resolutions.</p>"
        "</footer>"
    )


def _summary(data: dict[str, Any]) -> str:
    cards = [
        ("Conflicts", data.get("conflict_count", 0)),
        ("Warnings", data.get("warning_count", 0)),
        ("Auto-resolved", len(data.get("auto_resolved", []))),
        ("Track changes", len(data.get("track_changes", []))),
        ("Locator changes", len(data.get("locator_changes", []))),
        ("Lineage", data.get("lineage_confidence", "")),
    ]
    body = "".join(
        f'<div class="stat"><span>{_h(label)}</span><strong>{_h(value)}</strong></div>'
        for label, value in cards
    )
    return (
        '<section class="summary">'
        "<h2>Summary</h2>"
        f'<div class="stats">{body}</div>'
        f'<p><strong>Input mode:</strong> {_h(data.get("input_mode", ""))}</p>'
        f'<p><strong>Created:</strong> {_h(data.get("created_at_utc", ""))}</p>'
        "</section>"
    )


def _sources(data: dict[str, Any]) -> str:
    sources = data.get("sources", {})
    rows = []
    for name in ("base", "ours", "theirs"):
        src = sources.get(name, {}) if isinstance(sources, dict) else {}
        rows.append(
            "<tr>"
            f"<th>{_h(name)}</th>"
            f"<td>{_h(_basename_label(src.get('label', '')))}</td>"
            f"<td><code>{_h(src.get('sha256', ''))}</code></td>"
            f"<td>{_h(src.get('size', ''))}</td>"
            "</tr>"
        )
    return (
        '<section class="sources">'
        "<h2>Sources</h2>"
        "<table><thead><tr><th>Role</th><th>Label</th><th>SHA-256</th><th>Size</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "</section>"
    )


def _warnings(warnings: list[str]) -> str:
    if not warnings:
        return '<section><h2>Warnings</h2><p class="empty">No warnings.</p></section>'
    items = "".join(f"<li>{_h(w)}</li>" for w in warnings)
    return f'<section><h2>Warnings</h2><ul class="warnings">{items}</ul></section>'


def _section(title: str, items: list[dict[str, Any]], renderer, empty: str) -> str:
    if not items:
        return f'<section><h2>{_h(title)}</h2><p class="empty">{_h(empty)}</p></section>'
    body = "".join(renderer(item) for item in items)
    return f'<section><h2>{_h(title)}</h2><div class="cards">{body}</div></section>'


def _conflict_card(item: dict[str, Any]) -> str:
    title = f"{item.get('field', '')} - {item.get('id', '')}"
    values = {
        "base": item.get("base_value"),
        "ours": item.get("ours_value"),
        "theirs": item.get("theirs_value"),
    }
    return _card(
        title,
        [
            ("Risk", item.get("risk", "")),
            ("Reason", item.get("reason", "")),
            ("Auto blocked", item.get("auto_blocked", "")),
            ("Resolution options only", item.get("available_resolutions", [])),
        ],
        values,
        class_name="conflict",
    )


def _auto_card(item: dict[str, Any]) -> str:
    title = f"{item.get('field', '')} - {item.get('id', '')}"
    return _card(
        title,
        [
            ("Resolution", item.get("resolution", "")),
            ("Description", item.get("description", "")),
        ],
        {"base": item.get("base_value"), "resolved": item.get("resolved_value")},
    )


def _track_card(item: dict[str, Any]) -> str:
    title = f"{item.get('kind', '')} - {item.get('name', '') or item.get('id', '')}"
    return _card(
        title,
        [
            ("Branch", item.get("branch", "")),
            ("Track ID", item.get("track_id", "")),
            ("Base track ID", item.get("base_track_id", "")),
            ("Branch track ID", item.get("branch_track_id", "")),
            ("Auto resolved", item.get("auto_resolved", "")),
        ],
        {"proposed_position": item.get("proposed_position"), "details": item.get("details", {})},
    )


def _locator_card(item: dict[str, Any]) -> str:
    title = f"{item.get('kind', '')} - {item.get('name', '')}"
    return _card(
        title,
        [
            ("Branch", item.get("branch", "")),
            ("Auto resolved", item.get("auto_resolved", "")),
        ],
        {
            "base_time": item.get("base_time"),
            "ours_time": item.get("ours_time"),
            "theirs_time": item.get("theirs_time"),
            "details": item.get("details", {}),
        },
    )


def _identity_card(item: dict[str, Any]) -> str:
    title = f"{item.get('classification', '')} - {item.get('name', '') or item.get('track_id', '')}"
    status = "blocked" if item.get("classification") == "ambiguous" else "review required" if item.get("classification") == "plausible" else "exact"
    return _card(
        title,
        [
            ("Status", status),
            ("Confidence", item.get("confidence", "")),
            ("Base track ID", item.get("base_track_id", "")),
            ("Ours track ID", item.get("ours_track_id", "")),
            ("Theirs track ID", item.get("theirs_track_id", "")),
            ("Auto resolved", item.get("auto_resolved", "")),
            ("Evidence", item.get("evidence", [])),
            ("Warnings", item.get("warnings", [])),
        ],
        {},
    )


def _generic_card(item: dict[str, Any]) -> str:
    return _card(item.get("id") or item.get("name") or "item", [], item)


def _card(title: Any, fields: list[tuple[str, Any]], details: Any, class_name: str = "") -> str:
    rows = "".join(
        f'<div class="field"><span>{_h(label)}</span><strong>{_h(value)}</strong></div>'
        for label, value in fields
    )
    detail_block = f"<pre>{_json(details)}</pre>" if details not in ({}, [], None) else ""
    klass = f" card {class_name}" if class_name else "card"
    return f'<article class="{klass}"><h3>{_h(title)}</h3>{rows}{detail_block}</article>'


def _supported_scope(data: dict[str, Any]) -> str:
    scope = sorted(str(item) for item in data.get("supported_field_scope", []))
    items = "".join(f"<li>{_h(item)}</li>" for item in scope)
    return f'<section><h2>Supported field scope</h2><ul class="scope">{items}</ul></section>'


def _validate_sources(sources: dict[str, Any]) -> None:
    for role in ("base", "ours", "theirs"):
        if role not in sources or not isinstance(sources[role], dict):
            raise ValueError(f"merge report sources missing role: {role}")
        src = sources[role]
        for key, expected in {"label": str, "sha256": str, "size": int}.items():
            if key not in src:
                raise ValueError(f"merge report source missing field: {role}.{key}")
            if not isinstance(src[key], expected):
                raise ValueError(f"merge report source field has incorrect type: {role}.{key}")


def _validate_string_list(values: Any, name: str) -> None:
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise ValueError(f"merge report field must be a list of strings: {name}")


def _validate_records(items: Any, name: str, required: dict[str, type]) -> None:
    if not isinstance(items, list):
        raise ValueError(f"merge report field must be a list: {name}")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"merge report record must be an object: {name}[{index}]")
        for key, expected in required.items():
            if key not in item:
                raise ValueError(f"merge report record missing field: {name}[{index}].{key}")
            if not isinstance(item[key], expected):
                raise ValueError(f"merge report record field has incorrect type: {name}[{index}].{key}")


def _validate_proposed_order(items: Any) -> None:
    if not isinstance(items, list):
        raise ValueError("merge report proposed_track_order must be a list")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"merge report proposed_track_order[{index}] must be an object")
        if not isinstance(item.get("branch"), str):
            raise ValueError(f"merge report proposed_track_order[{index}].branch has incorrect type")
        if not isinstance(item.get("track"), dict):
            raise ValueError(f"merge report proposed_track_order[{index}].track has incorrect type")
        if not isinstance(item.get("position"), dict):
            raise ValueError(f"merge report proposed_track_order[{index}].position has incorrect type")


def _reject_non_finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("merge report contains non-finite numeric value")
    if isinstance(value, dict):
        for item in value.values():
            _reject_non_finite(item)
    elif isinstance(value, list):
        for item in value:
            _reject_non_finite(item)


def _redact_private(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            key_s = str(key)
            if key_s.lower() in {"plugin_state", "pluginstate", "raw_plugin_state", "state_blob"}:
                redacted[key] = "[redacted plugin state]"
            else:
                redacted[key] = _redact_private(item)
        return redacted
    if isinstance(value, list):
        return [_redact_private(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_private(item) for item in value)
    return value


def _basename_label(value: Any) -> str:
    text = str(value)
    if not text:
        return ""
    if text.startswith(_WINDOWS_PREFIXES) or "\\" in text:
        return PureWindowsPath(text).name or "[redacted path]"
    if text.startswith("/"):
        return PurePosixPath(text).name or "[redacted path]"
    return text


_WINDOWS_PREFIXES = tuple(f"{letter}:" for letter in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")


_CSS = """
:root { color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
body { margin: 0; background: #10131a; color: #e8edf7; }
main { max-width: 1120px; margin: 0 auto; padding: 32px 20px 56px; }
h1 { margin: 0 0 18px; font-size: 2.1rem; letter-spacing: -0.03em; }
h2 { margin: 0 0 14px; font-size: 1.25rem; }
h3 { margin: 0 0 12px; font-size: 1rem; }
section { margin-top: 20px; padding: 18px; border: 1px solid #2c3445; border-radius: 14px; background: #171c26; }
.privacy-footer { border-color: #9f6b1d; background: #251d11; }
.summary { background: linear-gradient(135deg, #172033, #1b2638); }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.stat, .card, .field { border: 1px solid #2c3445; border-radius: 10px; background: #111720; }
.stat { padding: 14px; }
.stat span, .field span { display: block; color: #9aa8bd; font-size: 0.82rem; }
.stat strong { display: block; margin-top: 6px; font-size: 1.3rem; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
.card { padding: 14px; }
.conflict { border-color: #c75252; }
.field { margin: 8px 0; padding: 8px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px; border-bottom: 1px solid #2c3445; text-align: left; vertical-align: top; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
code { overflow-wrap: anywhere; }
pre { overflow: auto; padding: 12px; border-radius: 10px; background: #0b0f16; color: #d7e2f2; }
.empty { color: #9aa8bd; }
a { color: inherit; }
""".strip()
