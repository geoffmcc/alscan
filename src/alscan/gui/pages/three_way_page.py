# SPDX-License-Identifier: GPL-3.0-only
"""Three-way structural analysis page."""

from __future__ import annotations

import os
import subprocess
import webbrowser
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QFrame, QMessageBox, QCheckBox,
    QGroupBox, QHeaderView,
)
from PySide6.QtCore import Qt, QThreadPool, Slot

from alscan.gui.workers import ThreeWayWorker, ThreeWayTaskInput
from alscan.gui.widgets.drop_area import ThreeWayDropArea
from alscan.merge.plan import MergePlan
from alscan.services import save_merge_plan, save_merge_report, ReportError


class ThreeWayPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: ThreeWayWorker | None = None
        self._plan: MergePlan | None = None
        self._pool = QThreadPool.globalInstance()
        self._analysis_complete = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QLabel("Three-Way Analysis")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        self.info_label = QLabel(
            "Compare Base (common ancestor), Ours (one descendant), and Theirs "
            "(the other descendant) versions of an Ableton Live project. "
            "<b>This is structural analysis only. It does not modify any source "
            "files, does not create a merged .als file, and does not apply "
            "conflict resolutions.</b> Results are analytical only."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setObjectName("subheading")
        layout.addWidget(self.info_label)

        self.input_area = QFrame()
        self._build_input_area()
        layout.addWidget(self.input_area)

        self.drop_area = ThreeWayDropArea()
        self.drop_area.paths_dropped.connect(self._on_paths_dropped)
        layout.addWidget(self.drop_area)

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

        export_layout = QHBoxLayout()
        self.save_json_btn = QPushButton("Save JSON Merge Plan")
        self.save_json_btn.clicked.connect(self._save_json)
        self.save_json_btn.setVisible(False)
        export_layout.addWidget(self.save_json_btn)

        self.save_html_btn = QPushButton("Save HTML Conflict Report")
        self.save_html_btn.clicked.connect(self._save_html)
        self.save_html_btn.setVisible(False)
        export_layout.addWidget(self.save_html_btn)

        export_layout.addStretch()
        layout.addLayout(export_layout)

    def _build_input_area(self) -> None:
        input_layout = QVBoxLayout(self.input_area)

        role_widget = QWidget()
        role_layout = QHBoxLayout(role_widget)
        role_layout.setContentsMargins(0, 0, 0, 0)
        role_desc = QLabel(
            "<b>Base</b> = common ancestor &nbsp;&nbsp; "
            "<b>Ours</b> = one descendant &nbsp;&nbsp; "
            "<b>Theirs</b> = the other descendant"
        )
        role_desc.setObjectName("subheading")
        role_layout.addWidget(role_desc)
        role_layout.addStretch()
        input_layout.addWidget(role_widget)

        def make_input_row(label_text: str, target: QLineEdit) -> QHBoxLayout:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setMinimumWidth(70)
            row.addWidget(lbl)
            row.addWidget(target, 1)
            btn = QPushButton("Browse...")
            btn.clicked.connect(lambda: self._browse_file(target))
            row.addWidget(btn)
            return row

        self.base_input = QLineEdit()
        self.base_input.setPlaceholderText("Base version (.als or .json)...")
        input_layout.addLayout(make_input_row("Base:", self.base_input))

        self.ours_input = QLineEdit()
        self.ours_input.setPlaceholderText("Ours version (.als or .json)...")
        input_layout.addLayout(make_input_row("Ours:", self.ours_input))

        self.theirs_input = QLineEdit()
        self.theirs_input.setPlaceholderText("Theirs version (.als or .json)...")
        input_layout.addLayout(make_input_row("Theirs:", self.theirs_input))

        opt_layout = QHBoxLayout()
        self.allow_unrelated = QCheckBox("Allow unrelated projects")
        self.allow_unrelated.setToolTip(
            "Analyze projects that do not share common ancestry. "
            "Results will be marked with low confidence."
        )
        opt_layout.addWidget(self.allow_unrelated)

        self.allow_plausible = QCheckBox("Allow plausible identity matching")
        self.allow_plausible.setToolTip(
            "Allow track identity matches based on structural evidence "
            "when track IDs differ. Disabled by default."
        )
        opt_layout.addWidget(self.allow_plausible)

        opt_layout.addStretch()

        self.analyze_btn = QPushButton("Analyze Versions")
        self.analyze_btn.setObjectName("primaryButton")
        self.analyze_btn.clicked.connect(self._start_analysis)
        opt_layout.addWidget(self.analyze_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_analysis)
        opt_layout.addWidget(self.cancel_btn)

        self.change_sources_btn = QPushButton("Change Sources")
        self.change_sources_btn.setVisible(False)
        self.change_sources_btn.clicked.connect(self._expand_input_area)
        opt_layout.addWidget(self.change_sources_btn)

        input_layout.addLayout(opt_layout)

    def set_sources(self, base: str, ours: str, theirs: str) -> None:
        self.base_input.setText(base)
        self.ours_input.setText(ours)
        self.theirs_input.setText(theirs)

    def _browse_file(self, target: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select File",
            "", "Ableton Live Set (*.als);;Snapshot JSON (*.json);;All Files (*)"
        )
        if path:
            target.setText(path)

    def _on_paths_dropped(self, base: str, ours: str, theirs: str) -> None:
        self.set_sources(base, ours, theirs)

    def _validate_inputs(self) -> str | None:
        """Return an error string if inputs are invalid, None if valid."""
        paths = [
            self.base_input.text().strip(),
            self.ours_input.text().strip(),
            self.theirs_input.text().strip(),
        ]
        labels = ["Base", "Ours", "Theirs"]

        for label, p in zip(labels, paths):
            if not p:
                return f"{label} path is empty."

        resolved = []
        for p in paths:
            rp = Path(p).resolve()
            resolved.append(rp)
            if not rp.exists():
                return f"File not found: {p}"

        if resolved[0] == resolved[1] or resolved[0] == resolved[2] or resolved[1] == resolved[2]:
            return "Duplicate input: Base, Ours, and Theirs must be three independent files."

        extensions = {p.suffix.lower() for p in resolved}
        if len(extensions) > 1:
            return "Mixed input types detected. All three inputs must be of the same type (.als or .json)."

        if not extensions.issubset({".als", ".json"}):
            return "Unsupported file type. Use .als or .json snapshot files."

        return None

    def _start_analysis(self) -> None:
        error = self._validate_inputs()
        if error:
            self.status_label.setText(error)
            return

        base = self.base_input.text().strip()
        ours = self.ours_input.text().strip()
        theirs = self.theirs_input.text().strip()

        self._plan = None
        self._analysis_complete = False
        self.result_tree.setVisible(False)
        self.save_json_btn.setVisible(False)
        self.save_html_btn.setVisible(False)
        self.status_label.setText("Analyzing...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.analyze_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.change_sources_btn.setVisible(False)

        self._worker = ThreeWayWorker(ThreeWayTaskInput(
            base=base,
            ours=ours,
            theirs=theirs,
            allow_unrelated=self.allow_unrelated.isChecked(),
            allow_plausible=self.allow_plausible.isChecked(),
        ))
        self._worker.signals.finished.connect(self._on_analysis_finished)
        self._worker.signals.error.connect(self._on_analysis_error)
        self._pool.start(self._worker)

    def _cancel_analysis(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                try:
                    self._worker.signals.finished.disconnect(self._on_analysis_finished)
                except (TypeError, RuntimeError, SystemError):
                    pass
                try:
                    self._worker.signals.error.disconnect(self._on_analysis_error)
                except (TypeError, RuntimeError, SystemError):
                    pass
            self._worker = None
        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.status_label.setText("Analysis cancelled.")

    @Slot(object)
    def _on_analysis_finished(self, result: object) -> None:
        self._worker = None
        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)

        if isinstance(result, MergePlan):
            self._plan = result
            self._analysis_complete = True
            self._populate_results(result)
            self.result_tree.setVisible(True)
            self.save_json_btn.setVisible(True)
            self.save_html_btn.setVisible(True)
            self._compact_input_area()

    @Slot(str, str)
    def _on_analysis_error(self, message: str, details: str) -> None:
        self._worker = None
        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.status_label.setText("")
        from alscan.gui.dialogs.error_dialog import ErrorDialog
        dlg = ErrorDialog(message, details, self)
        dlg.exec()

    def _compact_input_area(self) -> None:
        self.info_label.setVisible(False)
        self.drop_area.setMinimumHeight(20)
        self.drop_area.setMaximumHeight(40)
        self.drop_area.label.setText("Drop three files to compare different versions")
        self.input_area.setMaximumHeight(50)
        self.analyze_btn.setText("Reanalyze")
        self.change_sources_btn.setVisible(True)

    def _expand_input_area(self) -> None:
        self.info_label.setVisible(True)
        self.drop_area.setMinimumHeight(100)
        self.drop_area.setMaximumHeight(16777215)
        self.drop_area.label.setText("Drop three files here\nor use individual file pickers below")
        self.input_area.setMaximumHeight(16777215)
        self.analyze_btn.setText("Analyze Versions")
        self.change_sources_btn.setVisible(False)

    def _populate_results(self, plan: MergePlan) -> None:
        self.result_tree.clear()
        self.result_tree.setColumnCount(2)

        root = QTreeWidgetItem(["Three-Way Analysis Results", ""])
        self.result_tree.addTopLevelItem(root)

        lineage = QTreeWidgetItem(["Lineage Confidence", plan.lineage_confidence])
        root.addChild(lineage)
        root.addChild(QTreeWidgetItem(["Conflicts", str(plan.conflict_count)]))
        root.addChild(QTreeWidgetItem(["Auto-Resolved", str(len(plan.auto_resolved))]))
        root.addChild(QTreeWidgetItem(["Warnings", str(plan.warning_count)]))

        if plan.sources:
            src_item = QTreeWidgetItem(["Sources", ""])
            root.addChild(src_item)
            for role in ("base", "ours", "theirs"):
                info = plan.sources.get(role, {})
                label = info.get("label", "unknown")
                sha = info.get("sha256", "")[:12]
                src_item.addChild(QTreeWidgetItem([f"{role}: {label}", f"SHA256: {sha}..."]))

        if plan.warnings:
            warn_item = QTreeWidgetItem(["Warnings", ""])
            root.addChild(warn_item)
            for w in plan.warnings:
                warn_item.addChild(QTreeWidgetItem(["", str(w)]))

        if plan.conflicts:
            conf_item = QTreeWidgetItem(["Conflicts", str(plan.conflict_count)])
            root.addChild(conf_item)
            for c in plan.conflicts:
                child = QTreeWidgetItem([f"{c.field}: {c.id}", c.reason])
                conf_item.addChild(child)
                child.addChild(QTreeWidgetItem(["Base", str(c.base_value)]))
                child.addChild(QTreeWidgetItem(["Ours", str(c.ours_value)]))
                child.addChild(QTreeWidgetItem(["Theirs", str(c.theirs_value)]))

        if plan.auto_resolved:
            auto_item = QTreeWidgetItem(["Auto-Resolved", str(len(plan.auto_resolved))])
            root.addChild(auto_item)
            for a in plan.auto_resolved:
                child = QTreeWidgetItem([f"{a.field}: {a.id}", a.resolution])
                auto_item.addChild(child)
                child.addChild(QTreeWidgetItem(["Base", str(a.base_value)]))
                child.addChild(QTreeWidgetItem(["Resolved", str(a.resolved_value)]))

        if plan.identity_matches:
            id_item = QTreeWidgetItem(["Identity Matches", str(len(plan.identity_matches))])
            root.addChild(id_item)
            for m in plan.identity_matches:
                id_item.addChild(QTreeWidgetItem([
                    f"Track {m.base_track_id}: {m.name}",
                    f"confidence={m.confidence}"
                ]))

        if plan.track_changes:
            tc_item = QTreeWidgetItem(["Track Changes", str(len(plan.track_changes))])
            root.addChild(tc_item)
            for tc in plan.track_changes:
                branch_info = tc.branch
                if tc.auto_resolved:
                    branch_info += " (auto)"
                tc_item.addChild(QTreeWidgetItem([
                    f"[{tc.kind}] {tc.name or f'ID {tc.branch_track_id}'}",
                    branch_info,
                ]))

        if plan.locator_changes:
            loc_item = QTreeWidgetItem(["Locator Changes", str(len(plan.locator_changes))])
            root.addChild(loc_item)
            for lc in plan.locator_changes:
                loc_item.addChild(QTreeWidgetItem([f"[{lc.kind}] {lc.name}", lc.branch]))

        if plan.proposed_track_order:
            order_item = QTreeWidgetItem([
                "Proposed Track Order",
                str(len(plan.proposed_track_order))
            ])
            root.addChild(order_item)
            for entry in plan.proposed_track_order:
                track = entry.get("track", {})
                pos = entry.get("position", {})
                name = track.get("name", "?")
                tid = track.get("track_id", "?")
                after = pos.get("after_base_track_id")
                before = pos.get("before_base_track_id")
                pos_text = f"after={after}, before={before}" if after is not None or before is not None else "?"
                order_item.addChild(QTreeWidgetItem([f"{name} (ID:{tid})", pos_text]))

        self.result_tree.expandAll()
        self.status_label.setText(
            f"Analysis complete: {plan.conflict_count} conflict(s), "
            f"{len(plan.auto_resolved)} auto-resolved change(s)"
        )

    def _save_json(self) -> None:
        if not self._plan:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Merge Plan JSON",
            "merge-plan.json",
            "JSON (*.json);;All Files (*)"
        )
        if not path:
            return
        sources = self._source_paths()
        try:
            save_merge_plan(self._plan, Path(path), sources)
            self.status_label.setText(f"Merge plan saved: {Path(path).name}")
            self._ask_open_folder(Path(path))
        except ReportError as e:
            QMessageBox.warning(self, "Save Error", str(e))

    def _save_html(self) -> None:
        if not self._plan:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save HTML Conflict Report",
            "merge-report.html",
            "HTML (*.html);;All Files (*)"
        )
        if not path:
            return
        sources = self._source_paths()
        try:
            save_merge_report(self._plan, Path(path), sources)
            self.status_label.setText(f"Report saved: {Path(path).name}")
            webbrowser.open(Path(path).as_uri())
            self._ask_open_folder(Path(path))
        except ReportError as e:
            QMessageBox.warning(self, "Save Error", str(e))

    def _source_paths(self) -> list[Path]:
        sources = []
        for inp in (self.base_input, self.ours_input, self.theirs_input):
            if inp.text().strip():
                sources.append(Path(inp.text().strip()))
        return sources

    def _ask_open_folder(self, dest: Path) -> None:
        btn = QMessageBox.question(
            self, "Export Complete",
            f"File saved to:\n{dest}\n\nOpen containing folder?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if btn == QMessageBox.StandardButton.Yes:
            from alscan.gui.platform_utils import open_folder
            open_folder(dest.parent)
