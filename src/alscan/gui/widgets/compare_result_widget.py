# SPDX-License-Identifier: GPL-3.0-only
"""Compare result widget with Summary, Detailed, and Raw view modes."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QButtonGroup,
    QCheckBox, QFrame, QStackedWidget, QApplication,
    QHeaderView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from alscan.gui.compare_analysis import (
    ChangeItem, CompareAnalysis, CategorySummary, _generate_summary_text,
    _explain_property_change, _collect_categories, _build_summaries,
    CATEGORY_LABELS, analyse,
)
from alscan.gui.widgets.compare_badge import BadgeWidget
from alscan.versioner import DiffResult


_DETAIL_COLUMNS = [
    "Change", "Object", "Property", "Source A", "Source B", "Explanation",
]


def _elide(text: str, width: int = 40) -> str:
    if len(text) <= width:
        return text
    return text[:width - 1] + "\u2026"


def _predominant_change(items: list[ChangeItem]) -> str:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.change_type] = counts.get(item.change_type, 0) + 1
    return max(counts, key=counts.get) if counts else "modified"


class CompareResultWidget(QWidget):
    swap_requested = Signal()
    copy_summary_requested = Signal()
    export_report_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._analysis: CompareAnalysis | None = None
        self._raw_diff: DiffResult | None = None
        self._swapped = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._build_source_header(layout)
        self._build_toolbar(layout)
        self._build_stack(layout)
        self._build_actions(layout)

    def raw_diff(self) -> DiffResult | None:
        """Public accessor for the stored DiffResult."""
        return self._raw_diff

    def analysis(self) -> CompareAnalysis | None:
        """Public accessor for the stored CompareAnalysis."""
        return self._analysis

    def set_result(self, diff: DiffResult, path_a: str, path_b: str) -> None:
        self._raw_diff = diff
        self._analysis = analyse(diff, path_a, path_b)
        self._swapped = False
        self._update_source_display(path_a, path_b)
        self._update_filters()
        self._select_default_mode()
        self._update_mode()
        self._update_summary()
        self._update_detailed()
        self._update_raw()
        self.export_btn.setVisible(self._analysis.has_changes)

    def set_swapped_result(self, diff: DiffResult, path_a: str, path_b: str) -> None:
        """Update display with swapped source paths without re-parsing."""
        self._swapped = True
        self._analysis = analyse(diff, path_a, path_b)
        self._update_source_display(path_a, path_b)

    def _select_default_mode(self) -> None:
        if "detailed" in self._mode_buttons:
            self._mode_buttons["detailed"].setChecked(True)
        elif self._mode_buttons:
            next(iter(self._mode_buttons.values())).setChecked(True)

    def _build_source_header(self, parent_layout: QVBoxLayout) -> None:
        frame = QFrame()
        frame.setObjectName("compareSourceHeader")
        header_layout = QHBoxLayout(frame)
        header_layout.setContentsMargins(8, 6, 8, 6)

        font = QFont()
        font.setBold(True)

        self.source_a_label = QLabel("Source A")
        self.source_a_label.setFont(font)
        self.source_a_label.setObjectName("compareSourceA")
        self.source_a_path = QLabel("")
        self.source_a_path.setObjectName("subheading")
        self.source_a_path.setToolTip("")
        self.source_a_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.arrow_label = QLabel("\u2192")
        self.arrow_label.setFont(font)
        self.arrow_label.setStyleSheet("font-size: 16px;")

        self.source_b_label = QLabel("Source B")
        self.source_b_label.setFont(font)
        self.source_b_label.setObjectName("compareSourceB")
        self.source_b_path = QLabel("")
        self.source_b_path.setObjectName("subheading")
        self.source_b_path.setToolTip("")
        self.source_b_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.swap_btn = QPushButton("\u21C4 Swap Sources")
        self.swap_btn.setToolTip("Reverse the comparison direction (A \u2194 B)")
        self.swap_btn.clicked.connect(self._on_swap)

        self.direction_label = QLabel("")
        self.direction_label.setObjectName("subheading")

        header_layout.addWidget(self.source_a_label)
        header_layout.addWidget(self.source_a_path, 1)
        header_layout.addWidget(self.arrow_label)
        header_layout.addWidget(self.source_b_label)
        header_layout.addWidget(self.source_b_path, 1)
        header_layout.addWidget(self.swap_btn)
        header_layout.addWidget(self.direction_label)

        parent_layout.addWidget(frame)

    def _build_toolbar(self, parent_layout: QVBoxLayout) -> None:
        toolbar = QHBoxLayout()

        mode_label = QLabel("View:")
        toolbar.addWidget(mode_label)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self._mode_buttons: dict[str, QPushButton] = {}
        for mode_id, mode_label_text in [("summary", "Summary"), ("detailed", "Detailed"), ("raw", "Raw")]:
            btn = QPushButton(mode_label_text)
            btn.setCheckable(True)
            btn.setObjectName("compareModeBtn")
            btn.clicked.connect(lambda checked, m=mode_id: self._set_mode(m))
            self.mode_group.addButton(btn)
            self._mode_buttons[mode_id] = btn
            toolbar.addWidget(btn)

        toolbar.addSpacing(16)

        self.filter_label = QLabel("Filter:")
        toolbar.addWidget(self.filter_label)

        self.filter_widgets: dict[str, QCheckBox] = {}
        self.filter_container = QHBoxLayout()
        toolbar.addLayout(self.filter_container)

        toolbar.addStretch()

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar)
        toolbar_widget.setObjectName("compareToolbar")
        parent_layout.addWidget(toolbar_widget)

    def _build_stack(self, parent_layout: QVBoxLayout) -> None:
        self.stack = QStackedWidget()

        self._build_summary_view()
        self._build_detailed_view()
        self._build_raw_view()

        parent_layout.addWidget(self.stack, 1)

    def _build_summary_view(self) -> None:
        self.summary_container = QWidget()
        layout = QVBoxLayout(self.summary_container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("compareSummary")
        self.summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.summary_label)

        self.summary_tree = QTreeWidget()
        self.summary_tree.setHeaderLabels(["Change", "Details"])
        self.summary_tree.setAlternatingRowColors(True)
        self.summary_tree.setIndentation(20)
        self.summary_tree.setAnimated(True)
        header = self.summary_tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.summary_tree, 1)

        self.stack.addWidget(self.summary_container)

    def _build_detailed_view(self) -> None:
        self.detailed_tree = QTreeWidget()
        self.detailed_tree.setHeaderLabels(_DETAIL_COLUMNS)
        self.detailed_tree.setAlternatingRowColors(True)
        self.detailed_tree.setIndentation(20)
        self.detailed_tree.setAnimated(True)
        self.detailed_tree.setRootIsDecorated(True)
        header = self.detailed_tree.header()
        header.setStretchLastSection(True)
        for i in range(len(_DETAIL_COLUMNS) - 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.stack.addWidget(self.detailed_tree)

    def _build_raw_view(self) -> None:
        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setFont(QFont("Consolas, Courier New, monospace", 10))
        self.raw_text.setObjectName("compareRawText")
        self.stack.addWidget(self.raw_text)

    def _build_actions(self, parent_layout: QVBoxLayout) -> None:
        action_layout = QHBoxLayout()

        self.copy_summary_btn = QPushButton("\u2398 Copy Summary")
        self.copy_summary_btn.setToolTip("Copy the comparison summary to clipboard")
        self.copy_summary_btn.clicked.connect(self._on_copy_summary)
        action_layout.addWidget(self.copy_summary_btn)

        action_layout.addStretch()

        self.export_btn = QPushButton("\u2B07 Export Report")
        self.export_btn.setToolTip("Export comparison report to file")
        self.export_btn.clicked.connect(self._on_export_report)
        action_layout.addWidget(self.export_btn)

        parent_layout.addLayout(action_layout)

    def _update_source_display(self, path_a: str, path_b: str) -> None:
        file_a = Path(path_a).name if path_a else ""
        file_b = Path(path_b).name if path_b else ""

        if self._swapped:
            self.source_a_label.setText(file_b)
            self.source_a_path.setText(path_b)
            self.source_a_path.setToolTip(path_b)
            self.source_b_label.setText(file_a)
            self.source_b_path.setText(path_a)
            self.source_b_path.setToolTip(path_a)
        else:
            self.source_a_label.setText(file_a)
            self.source_a_path.setText(path_a)
            self.source_a_path.setToolTip(path_a)
            self.source_b_label.setText(file_b)
            self.source_b_path.setText(path_b)
            self.source_b_path.setToolTip(path_b)

        self.direction_label.setText("(changes show A \u2192 B)")

    def _update_filters(self) -> None:
        for cb in self.filter_widgets.values():
            cb.deleteLater()
        self.filter_widgets.clear()

        if self._analysis is None:
            return

        categories = _collect_categories(self._analysis.items)
        for cat in categories:
            cb = QCheckBox(CATEGORY_LABELS.get(cat, cat.title()))
            cb.setChecked(True)
            # The 'checked' parameter is unused but QCheckBox.toggled provides it.
            # All checkboxes call _update_mode() which re-evaluates all active filters.
            cb.toggled.connect(lambda _checked: self._update_mode())
            self.filter_widgets[cat] = cb
            self.filter_container.addWidget(cb)

    def _active_filters(self) -> set[str]:
        return {cat for cat, cb in self.filter_widgets.items() if cb.isChecked()}

    def _filtered_items(self) -> list[ChangeItem]:
        if self._analysis is None:
            return []
        active = self._active_filters()
        if not active:
            return []
        return [item for item in self._analysis.items if item.category in active]

    def _update_mode(self) -> None:
        if self._analysis is None:
            return

        checked = self.mode_group.checkedButton()
        if checked is None:
            return

        text = checked.text().lower()
        if text == "summary":
            self.stack.setCurrentWidget(self.summary_container)
            self._update_summary()
        elif text == "raw":
            self.stack.setCurrentWidget(self.raw_text)
            self._update_raw()
        else:
            self.stack.setCurrentWidget(self.detailed_tree)
            self._update_detailed()

    def _set_mode(self, mode: str) -> None:
        if mode in self._mode_buttons:
            self._mode_buttons[mode].setChecked(True)
        self._update_mode()

    def _update_summary(self) -> None:
        if self._analysis is None:
            return

        items = self._filtered_items()

        lines: list[str] = []

        if not self._analysis.has_changes:
            lines.append("No differences found in structural metadata.")
            self.summary_label.setText("\n".join(lines))
            self.summary_tree.clear()
            return

        if not items:
            if not self._active_filters():
                lines.append("Enable one or more category filters to see changes.")
            else:
                lines.append("No changes match the selected filters.")
            self.summary_label.setText("\n".join(lines))
            self.summary_tree.clear()
            return

        summaries = _build_summaries(items)
        summary_lines = _generate_summary_text(items, summaries)
        lines.extend(summary_lines)

        lines.append("")
        lines.append("Source A \u2192 Source B")

        self.summary_label.setText("\n".join(lines))

        self.summary_tree.clear()

        grouped: dict[str, list[ChangeItem]] = {}
        for item in items:
            key = item.category
            grouped.setdefault(key, []).append(item)

        for cat in sorted(grouped):
            group_items = grouped[cat]
            cat_label = CATEGORY_LABELS.get(cat, cat.title())
            group_root = QTreeWidgetItem([cat_label, f"{len(group_items)} change(s)"])

            sub_groups: dict[str, list[ChangeItem]] = {}
            for item in group_items:
                obj_key = item.object_name
                if item.parent_object:
                    obj_key = item.parent_object + " / " + obj_key
                sub_groups.setdefault(obj_key, []).append(item)

            for obj_key, obj_items in sub_groups.items():
                if len(obj_items) == 1:
                    item = obj_items[0]
                    expl = item.explanation if item.explanation else f"{item.value_a} \u2192 {item.value_b}"
                    elided = _elide(expl, 60)
                    child = QTreeWidgetItem([item.object_type, elided])
                    child.setToolTip(1, expl)
                    badge = BadgeWidget(item.change_type)
                    self.summary_tree.setItemWidget(child, 0, badge)
                    group_root.addChild(child)
                else:
                    obj_item = QTreeWidgetItem([obj_key, f"{len(obj_items)} change(s)"])
                    for item in obj_items:
                        expl = item.explanation if item.explanation else f"{item.value_a} \u2192 {item.value_b}"
                        prop_text = f"{item.property_name}: {expl}" if item.property_name else expl
                        elided = _elide(prop_text, 60)
                        leaf = QTreeWidgetItem(["", elided])
                        leaf.setToolTip(1, prop_text)
                        badge = BadgeWidget(item.change_type)
                        self.summary_tree.setItemWidget(leaf, 0, badge)
                        obj_item.addChild(leaf)
                    group_root.addChild(obj_item)

            self.summary_tree.addTopLevelItem(group_root)

        if self._analysis.is_small:
            self.summary_tree.expandAll()

        header = self.summary_tree.header()
        header.setStretchLastSection(True)

    def _update_detailed(self) -> None:
        self.detailed_tree.clear()

        if self._analysis is None:
            return

        items = self._filtered_items()

        if not items:
            return

        grouped: dict[str, list[ChangeItem]] = {}
        for item in items:
            key = item.object_name
            grouped.setdefault(key, []).append(item)

        for obj_name in sorted(grouped):
            obj_items = grouped[obj_name]
            if len(obj_items) == 1:
                item = obj_items[0]
                elided_name = _elide(item.object_name, 30)
                row = QTreeWidgetItem([
                    "", _elide(item.object_type, 15),
                    item.property_name, item.value_a, item.value_b,
                    item.explanation,
                ])
                row.setToolTip(1, f"{item.object_type}: {item.object_name}")
                row.setToolTip(2, item.property_name)
                row.setToolTip(3, item.value_a)
                row.setToolTip(4, item.value_b)
                row.setToolTip(5, item.explanation)
                badge = BadgeWidget(item.change_type)
                self.detailed_tree.setItemWidget(row, 0, badge)
                self.detailed_tree.addTopLevelItem(row)
            else:
                first = obj_items[0]
                parent_badge_type = _predominant_change(obj_items)
                parent = QTreeWidgetItem([
                    "", _elide(first.object_type, 15), obj_name, "", "", "",
                ])
                parent.setToolTip(2, obj_name)
                badge = BadgeWidget(parent_badge_type)
                self.detailed_tree.setItemWidget(parent, 0, badge)
                for item in obj_items:
                    child = QTreeWidgetItem([
                        "", "", item.property_name,
                        item.value_a, item.value_b,
                        item.explanation,
                    ])
                    child.setToolTip(2, item.property_name)
                    child.setToolTip(3, item.value_a)
                    child.setToolTip(4, item.value_b)
                    child.setToolTip(5, item.explanation)
                    child_badge = BadgeWidget(item.change_type)
                    self.detailed_tree.setItemWidget(child, 0, child_badge)
                    parent.addChild(child)
                self.detailed_tree.addTopLevelItem(parent)

        if self._analysis.is_small:
            self.detailed_tree.expandAll()

        header = self.detailed_tree.header()
        header.setStretchLastSection(True)

    def _update_raw(self) -> None:
        if self._raw_diff is None:
            self.raw_text.setPlainText("")
            return

        lines: list[str] = []
        r = self._raw_diff
        lines.append(f"Raw Diff: {r.project_a} vs {r.project_b}")
        lines.append("=" * 60)
        lines.append("")

        if not r.has_changes:
            lines.append("No differences found.")
            self.raw_text.setPlainText("\n".join(lines))
            return

        if r.tempo_changed:
            lines.append(f"Tempo: {r.tempo_before} BPM -> {r.tempo_after} BPM")

        if r.time_sig_changed:
            lines.append(f"Time Sig: {r.ts_before[0]}/{r.ts_before[1]} -> {r.ts_after[0]}/{r.ts_after[1]}")

        if r.locators_changed:
            lines.append("")
            lines.append("Locator changes:")
            for loc in r.added_locators:
                lines.append(f'  + "{loc["name"]}" at {loc.get("time", 0):.1f}')
            for loc in r.removed_locators:
                lines.append(f'  - "{loc["name"]}" at {loc.get("time", 0):.1f}')

        if r.track_changes:
            lines.append("")
            lines.append("Track changes:")
            for tc in r.track_changes:
                sym = {"added": "+", "removed": "-", "modified": "~", "unchanged": " "}[tc.kind]
                lines.append(f"  {sym} [{tc.track_id}] {tc.name}")
                for d in tc.details:
                    lines.append(f"      {d}")

        if r.device_changes:
            lines.append("")
            lines.append("Device changes:")
            for dc in r.device_changes:
                lines.append(f"  ~ [{dc.track_id}] {dc.track_name}")
                for dev in dc.added:
                    name = dev.get("name", "")
                    label = name
                    ptype = dev.get("plugin_type", "")
                    dtype = dev.get("device_type", "")
                    if ptype:
                        label = f"{name} ({ptype})"
                    elif dtype and dtype != name:
                        label = f"{name} ({dtype})"
                    lines.append(f'    + "{label}"')
                for dev in dc.removed:
                    name = dev.get("name", "")
                    label = name
                    ptype = dev.get("plugin_type", "")
                    dtype = dev.get("device_type", "")
                    if ptype:
                        label = f"{name} ({ptype})"
                    elif dtype and dtype != name:
                        label = f"{name} ({dtype})"
                    lines.append(f'    - "{label}"')
                if dc.order_changed:
                    lines.append("    ~ device order changed")

        self.raw_text.setPlainText("\n".join(lines))

    def _on_swap(self) -> None:
        self._swapped = not self._swapped
        if self._analysis is not None:
            self._update_source_display(
                self._analysis.path_a, self._analysis.path_b
            )
        self.swap_requested.emit()

    def _on_copy_summary(self) -> None:
        if self._analysis is None:
            return
        items = self._filtered_items()
        if not items:
            summary_lines = ["No differences found in structural metadata."]
        else:
            summaries = _build_summaries(items)
            summary_lines = _generate_summary_text(items, summaries)
            summary_lines.append("")
            summary_lines.append("Details:")
            for item in items:
                line = f"  [{item.change_type.upper()}] {item.object_type}: {item.object_name}"
                if item.property_name:
                    line += f" \u2014 {item.property_name}: {item.value_a} \u2192 {item.value_b}"
                if item.explanation:
                    line += f" \u2014 {item.explanation}"
                summary_lines.append(line)

        text = "\n".join(summary_lines)
        QApplication.clipboard().setText(text)
        self.copy_summary_requested.emit()

    def _on_export_report(self) -> None:
        self.export_report_requested.emit()
