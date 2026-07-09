# SPDX-License-Identifier: GPL-3.0-only
"""Rich structured analysis layer over DiffResult.

Consumes a raw DiffResult from the two-way diff engine and produces
structured ChangeItem objects, summary statistics, and human-readable
explanations.  Does not modify the underlying diff engine or its output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from alscan.versioner import DiffResult, TrackChange, DeviceDiff

ChangeType = Literal["added", "removed", "modified", "moved", "renamed"]
Category = Literal["track", "clip", "device", "locator", "tempo", "time_signature", "metadata"]

CATEGORY_LABELS: dict[str, str] = {
    "track": "Tracks",
    "clip": "Clips",
    "device": "Devices",
    "locator": "Locators",
    "tempo": "Tempo",
    "time_signature": "Time Signature",
    "metadata": "Metadata",
}


@dataclass
class ChangeItem:
    change_type: ChangeType
    category: Category
    object_type: str
    object_name: str
    property_name: str
    value_a: str
    value_b: str
    explanation: str
    parent_object: str = ""

    def __hash__(self):
        return hash((
            self.change_type, self.category, self.object_type,
            self.object_name, self.property_name,
            self.value_a, self.value_b, self.parent_object,
        ))


@dataclass
class CategorySummary:
    category: Category
    label: str
    added: int = 0
    removed: int = 0
    modified: int = 0
    moved: int = 0
    renamed: int = 0

    @property
    def total(self) -> int:
        return self.added + self.removed + self.modified + self.moved + self.renamed


@dataclass
class CompareAnalysis:
    project_a: str
    project_b: str
    path_a: str
    path_b: str
    items: list[ChangeItem] = field(default_factory=list)
    categories: list[CategorySummary] = field(default_factory=list)
    total_changes: int = 0
    has_changes: bool = False

    @property
    def is_small(self) -> bool:
        """Few enough changes that all groups should auto-expand."""
        return 0 < self.total_changes <= 10


def _explain_property_change(category: str, prop: str, val_a: str, val_b: str) -> str:
    """Translate a raw property change into a natural language description."""
    if prop == "Name":
        return f'Renamed from "{val_a}" to "{val_b}"'
    elif prop == "Clip count":
        try:
            a, b = int(val_a), int(val_b)
            diff = b - a
            if diff > 0:
                return f"{diff} clip{'s' if diff != 1 else ''} added"
            elif diff < 0:
                return f"{-diff} clip{'s' if diff != -1 else ''} removed"
        except (ValueError, TypeError):
            pass
    elif prop == "Device count":
        try:
            a, b = int(val_a), int(val_b)
            diff = b - a
            if diff > 0:
                return f"{diff} device{'s' if diff != 1 else ''} added"
            elif diff < 0:
                return f"{-diff} device{'s' if diff != 1 else ''} removed"
        except (ValueError, TypeError):
            pass
    elif prop == "Tempo":
        try:
            a, b = float(val_a), float(val_b)
            diff = b - a
            if diff > 0:
                return f"Tempo increased by {diff:g} BPM"
            else:
                return f"Tempo decreased by {-diff:g} BPM"
        except (ValueError, TypeError):
            pass
    elif prop == "Volume":
        try:
            a, b = float(val_a), float(val_b)
            diff = b - a
            if diff > 0:
                return f"Volume increased from {a} to {b}"
            else:
                return f"Volume decreased from {a} to {b}"
        except (ValueError, TypeError):
            pass
    elif prop == "Frozen":
        return "Track frozen" if val_b == "True" else "Track unfrozen"
    elif prop == "Type":
        return f"Type changed from {val_a} to {val_b}"
    elif prop == "Color":
        return f"Color index changed from {val_a} to {val_b}"
    elif prop == "Group":
        return f"Group changed from {val_a} to {val_b}"
    elif prop == "Time Signature":
        return f"Time signature changed from {val_a} to {val_b}"
    return f"Changed from {val_a} to {val_b}"


_PROPERTY_PARSERS = {
    "name": "Name",
    "clips": "Clip count",
    "devices": "Device count",
    "volume": "Volume",
    "frozen": "Frozen",
    "type": "Type",
    "color": "Color",
    "group_id": "Group",
}


def _parse_detail(detail: str) -> tuple[str, str, str] | None:
    """Parse a detail string like 'name: "Drums" -> "Percussion"' into
    (property_label, value_a, value_b)."""
    if ": " not in detail:
        return None
    raw_key, raw_values = detail.split(": ", 1)
    if " -> " not in raw_values:
        return None
    val_a, val_b = raw_values.split(" -> ", 1)
    key = raw_key.strip()
    val_a = val_a.strip().strip('"')
    val_b = val_b.strip().strip('"')
    label = _PROPERTY_PARSERS.get(key, key.replace("_", " ").title())
    return label, val_a, val_b


def _extract_changes(diff: DiffResult, path_a: str, path_b: str) -> list[ChangeItem]:
    items: list[ChangeItem] = []

    if diff.tempo_changed:
        items.append(ChangeItem(
            change_type="modified",
            category="tempo",
            object_type="Tempo",
            object_name="Tempo",
            property_name="Tempo",
            value_a=f"{diff.tempo_before}",
            value_b=f"{diff.tempo_after}",
            explanation=_explain_property_change(
                "tempo", "Tempo",
                f"{diff.tempo_before}", f"{diff.tempo_after}",
            ),
        ))

    if diff.time_sig_changed:
        ts_a = f"{diff.ts_before[0]}/{diff.ts_before[1]}"
        ts_b = f"{diff.ts_after[0]}/{diff.ts_after[1]}"
        items.append(ChangeItem(
            change_type="modified",
            category="time_signature",
            object_type="Time Signature",
            object_name="Time Signature",
            property_name="Time Signature",
            value_a=ts_a,
            value_b=ts_b,
            explanation=_explain_property_change(
                "time_sig", "Time Signature", ts_a, ts_b,
            ),
        ))

    for loc in diff.added_locators:
        name = loc.get("name", "")
        items.append(ChangeItem(
            change_type="added",
            category="locator",
            object_type="Locator",
            object_name=name,
            property_name="",
            value_a="",
            value_b=f"at {loc.get('time', 0):.1f}",
            explanation="Added in Source B",
        ))

    for loc in diff.removed_locators:
        name = loc.get("name", "")
        items.append(ChangeItem(
            change_type="removed",
            category="locator",
            object_type="Locator",
            object_name=name,
            property_name="",
            value_a=f"at {loc.get('time', 0):.1f}",
            value_b="",
            explanation="Present only in Source A",
        ))

    for tc in diff.track_changes:
        if tc.kind == "added":
            items.append(ChangeItem(
                change_type="added",
                category="track",
                object_type="Track",
                object_name=tc.name,
                property_name="",
                value_a="",
                value_b=f"ID {tc.track_id}",
                explanation="Added in Source B",
            ))
        elif tc.kind == "removed":
            items.append(ChangeItem(
                change_type="removed",
                category="track",
                object_type="Track",
                object_name=tc.name,
                property_name="",
                value_a=f"ID {tc.track_id}",
                value_b="",
                explanation="Present only in Source A",
            ))
        elif tc.kind == "modified":
            for detail in tc.details:
                parsed = _parse_detail(detail)
                if parsed is None:
                    items.append(ChangeItem(
                        change_type="modified",
                        category="track",
                        object_type="Track",
                        object_name=tc.name,
                        property_name="",
                        value_a="",
                        value_b="",
                        explanation=detail,
                    ))
                    continue
                prop_label, val_a, val_b = parsed
                category: Category = "track"
                change_type: ChangeType = "modified"
                if prop_label == "Name":
                    change_type = "renamed"
                elif prop_label == "Clip count":
                    category = "clip"
                items.append(ChangeItem(
                    change_type=change_type,
                    category=category,
                    object_type="Track",
                    object_name=tc.name,
                    property_name=prop_label,
                    value_a=val_a,
                    value_b=val_b,
                    explanation=_explain_property_change(
                        category, prop_label, val_a, val_b,
                    ),
                ))

    for dc in diff.device_changes:
        for dev in dc.added:
            dev_name = dev.get("name", "")
            items.append(ChangeItem(
                change_type="added",
                category="device",
                object_type="Device",
                object_name=dev_name,
                property_name="",
                value_a="",
                value_b=dev.get("plugin_type", dev.get("device_type", "")),
                explanation="Added in Source B",
                parent_object=dc.track_name,
            ))
        for dev in dc.removed:
            dev_name = dev.get("name", "")
            items.append(ChangeItem(
                change_type="removed",
                category="device",
                object_type="Device",
                object_name=dev_name,
                property_name="",
                value_a=dev.get("plugin_type", dev.get("device_type", "")),
                value_b="",
                explanation="Present only in Source A",
                parent_object=dc.track_name,
            ))
        if dc.order_changed:
            items.append(ChangeItem(
                change_type="moved",
                category="device",
                object_type="Device",
                object_name=f"Devices on {dc.track_name}",
                property_name="Order",
                value_a="",
                value_b="",
                explanation=f"Device order changed on track {dc.track_name}",
                parent_object=dc.track_name,
            ))

    return items


def _build_summaries(items: list[ChangeItem]) -> list[CategorySummary]:
    order = [
        ("track", CATEGORY_LABELS["track"]),
        ("clip", CATEGORY_LABELS["clip"]),
        ("device", CATEGORY_LABELS["device"]),
        ("locator", CATEGORY_LABELS["locator"]),
        ("tempo", CATEGORY_LABELS["tempo"]),
        ("time_signature", CATEGORY_LABELS["time_signature"]),
        ("metadata", CATEGORY_LABELS["metadata"]),
    ]
    summary_map: dict[str, CategorySummary] = {}
    for cat, label in order:
        summary_map[cat] = CategorySummary(category=cat, label=label)

    for item in items:
        cat = item.category
        if cat not in summary_map:
            summary_map[cat] = CategorySummary(category=cat, label=cat.title())
        cs = summary_map[cat]
        if item.change_type == "added":
            cs.added += 1
        elif item.change_type == "removed":
            cs.removed += 1
        elif item.change_type == "modified":
            cs.modified += 1
        elif item.change_type == "moved":
            cs.moved += 1
        elif item.change_type == "renamed":
            cs.renamed += 1

    return [s for s in summary_map.values() if s.total > 0]


def _generate_summary_text(items: list[ChangeItem], summaries: list[CategorySummary]) -> list[str]:
    """Generate human-readable summary lines."""
    lines: list[str] = []
    for cs in summaries:
        parts: list[str] = []
        if cs.modified > 0:
            parts.append(f"{cs.modified} {cs.label.lower()}{'s' if cs.modified != 1 else ''} changed")
        if cs.added > 0:
            parts.append(f"{cs.added} {cs.label.lower()}{'s' if cs.added != 1 else ''} added")
        if cs.removed > 0:
            parts.append(f"{cs.removed} {cs.label.lower()}{'s' if cs.removed != 1 else ''} removed")
        if cs.moved > 0:
            parts.append(f"{cs.moved} {cs.label.lower()}{'s' if cs.moved != 1 else ''} moved")
        if cs.renamed > 0:
            parts.append(f"{cs.renamed} {cs.label.lower()}{'s' if cs.renamed != 1 else ''} renamed")
        if parts:
            lines.append(", ".join(parts))

    if not lines:
        lines.append("No differences found in structural metadata")
    return lines


def _collect_categories(items: list[ChangeItem]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item.category not in seen:
            seen.add(item.category)
            result.append(item.category)
    result.sort()
    return result


def analyse(diff: DiffResult, path_a: str, path_b: str) -> CompareAnalysis:
    items = _extract_changes(diff, path_a, path_b)
    summaries = _build_summaries(items)
    return CompareAnalysis(
        project_a=diff.project_a,
        project_b=diff.project_b,
        path_a=path_a,
        path_b=path_b,
        items=items,
        categories=summaries,
        total_changes=len(items),
        has_changes=diff.has_changes,
    )
