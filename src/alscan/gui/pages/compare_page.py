# SPDX-License-Identifier: GPL-3.0-only
"""Structural comparison page for .als files and snapshots."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QFrame, QMessageBox,
)
from PySide6.QtCore import Qt, QThreadPool, Slot

from alscan.gui.workers import CompareWorker, CompareTaskInput
from alscan.gui.widgets.drop_area import DropArea
from alscan.versioner import DiffResult


class ComparePage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: CompareWorker | None = None
        self._pool = QThreadPool.globalInstance()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QLabel("Compare Versions")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        info_label = QLabel(
            "Compare two .als files, an .als file with a snapshot, or two snapshots. "
            "This compares structural metadata only: tempo, time signature, locators, "
            "tracks, devices, and more."
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("subheading")
        layout.addWidget(info_label)

        input_frame = QFrame()
        input_layout = QVBoxLayout(input_frame)

        self.a_layout = QHBoxLayout()
        label_a = QLabel("Source A:")
        label_a.setMinimumWidth(70)
        self.a_layout.addWidget(label_a)
        self.path_a_input = QLineEdit()
        self.path_a_input.setPlaceholderText(".als file or snapshot .json...")
        self.a_layout.addWidget(self.path_a_input, 1)

        browse_a_btn = QPushButton("Browse...")
        browse_a_btn.clicked.connect(lambda: self._browse(self.path_a_input))
        self.a_layout.addWidget(browse_a_btn)
        input_layout.addLayout(self.a_layout)

        self.b_layout = QHBoxLayout()
        label_b = QLabel("Source B:")
        label_b.setMinimumWidth(70)
        self.b_layout.addWidget(label_b)
        self.path_b_input = QLineEdit()
        self.path_b_input.setPlaceholderText(".als file, snapshot .json, or --snapshot index...")
        self.b_layout.addWidget(self.path_b_input, 1)

        browse_b_btn = QPushButton("Browse...")
        browse_b_btn.clicked.connect(lambda: self._browse(self.path_b_input))
        self.b_layout.addWidget(browse_b_btn)
        input_layout.addLayout(self.b_layout)

        self.compare_btn = QPushButton("Compare")
        self.compare_btn.setObjectName("primaryButton")
        self.compare_btn.clicked.connect(self._start_compare)
        input_layout.addWidget(self.compare_btn)

        layout.addWidget(input_frame)

        drop_area = DropArea("Drop two .als or snapshot files here (or use browse)")
        drop_area.path_dropped.connect(self._on_dropped)
        layout.addWidget(drop_area)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subheading")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["Category", "Details"])
        self.result_tree.setAlternatingRowColors(True)
        self.result_tree.setVisible(False)
        layout.addWidget(self.result_tree, 1)

    def set_sources(self, path_a: str, path_b: str) -> None:
        self.path_a_input.setText(path_a)
        self.path_b_input.setText(path_b)
        self._start_compare()

    def _browse(self, target: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select File",
            "", "Ableton Live Set (*.als);;Snapshot JSON (*.json);;All Files (*)"
        )
        if path:
            target.setText(path)

    def _on_dropped(self, path: str) -> None:
        if not self.path_a_input.text().strip():
            self.path_a_input.setText(path)
        elif not self.path_b_input.text().strip():
            self.path_b_input.setText(path)

    def _start_compare(self) -> None:
        path_a = self.path_a_input.text().strip()
        path_b = self.path_b_input.text().strip()
        if not path_a or not path_b:
            return

        self.result_tree.setVisible(False)
        self.status_label.setText("Comparing...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.compare_btn.setEnabled(False)

        self._worker = CompareWorker(CompareTaskInput(path_a=path_a, path_b=path_b))
        self._worker.signals.finished.connect(self._on_compare_finished)
        self._worker.signals.error.connect(self._on_compare_error)
        self._pool.start(self._worker)

    @Slot(object)
    def _on_compare_finished(self, result: object) -> None:
        self._worker = None
        self.progress_bar.setVisible(False)
        self.compare_btn.setEnabled(True)

        if isinstance(result, DiffResult):
            self.result_tree.setVisible(True)
            self.result_tree.clear()

            title_item = QTreeWidgetItem([f"{result.project_a} vs {result.project_b}", ""])
            self.result_tree.addTopLevelItem(title_item)

            if not result.has_changes:
                item = QTreeWidgetItem(["", "No differences found in structural metadata."])
                title_item.addChild(item)
                self.status_label.setText("No differences found.")
                return

            if result.tempo_changed:
                item = QTreeWidgetItem([
                    "Tempo",
                    f"{result.tempo_before} BPM -> {result.tempo_after} BPM"
                ])
                title_item.addChild(item)

            if result.time_sig_changed:
                item = QTreeWidgetItem([
                    "Time Signature",
                    f"{result.ts_before[0]}/{result.ts_before[1]} -> "
                    f"{result.ts_after[0]}/{result.ts_after[1]}"
                ])
                title_item.addChild(item)

            if result.locators_changed:
                loc_item = QTreeWidgetItem(["Locators", ""])
                title_item.addChild(loc_item)
                for loc in result.added_locators:
                    loc_item.addChild(QTreeWidgetItem([
                        "Added",
                        f'"{loc["name"]}" at {loc.get("time", 0):.1f}'
                    ]))
                for loc in result.removed_locators:
                    loc_item.addChild(QTreeWidgetItem([
                        "Removed",
                        f'"{loc["name"]}" at {loc.get("time", 0):.1f}'
                    ]))

            if result.track_changes:
                track_item = QTreeWidgetItem([
                    "Track Changes",
                    f"{len(result.track_changes)} change(s)"
                ])
                title_item.addChild(track_item)
                sym_map = {"added": "+", "removed": "-", "modified": "~", "unchanged": " "}
                for tc in result.track_changes:
                    sym = sym_map.get(tc.kind, "?")
                    child = QTreeWidgetItem([
                        f"{sym} [{tc.track_id}] {tc.name}",
                        tc.kind,
                    ])
                    track_item.addChild(child)
                    for d in tc.details:
                        child.addChild(QTreeWidgetItem(["", d]))

            if result.device_changes:
                dev_item = QTreeWidgetItem([
                    "Device Changes",
                    f"{len(result.device_changes)} track(s) affected"
                ])
                title_item.addChild(dev_item)
                for dc in result.device_changes:
                    track_child = QTreeWidgetItem([
                        f"[{dc.track_id}] {dc.track_name}",
                        "",
                    ])
                    dev_item.addChild(track_child)
                    for dev in dc.added:
                        label = dev.get("name", "")
                        ptype = dev.get("plugin_type", "")
                        dtype = dev.get("device_type", "")
                        if ptype:
                            label = f"{label} ({ptype})"
                        elif dtype and dtype != label:
                            label = f"{label} ({dtype})"
                        track_child.addChild(QTreeWidgetItem([f"+ \"{label}\"", "added"]))
                    for dev in dc.removed:
                        label = dev.get("name", "")
                        ptype = dev.get("plugin_type", "")
                        dtype = dev.get("device_type", "")
                        if ptype:
                            label = f"{label} ({ptype})"
                        elif dtype and dtype != label:
                            label = f"{label} ({dtype})"
                        track_child.addChild(QTreeWidgetItem([f"- \"{label}\"", "removed"]))
                    if dc.order_changed:
                        track_child.addChild(
                            QTreeWidgetItem(["~ device order changed", ""])
                        )

            self.result_tree.expandAll()
            self.status_label.setText("Comparison complete.")

    @Slot(str, str)
    def _on_compare_error(self, message: str, details: str) -> None:
        self._worker = None
        self.progress_bar.setVisible(False)
        self.compare_btn.setEnabled(True)
        self.status_label.setText("")
        from alscan.gui.dialogs.error_dialog import ErrorDialog
        dlg = ErrorDialog(message, details, self)
        dlg.exec()
