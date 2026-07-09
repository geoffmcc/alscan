# SPDX-License-Identifier: GPL-3.0-only
"""Three-way structural analysis page."""

from __future__ import annotations

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
from alscan.gui.widgets.drop_area import DropArea
from alscan.merge.plan import MergePlan
from alscan.services import save_merge_plan, save_merge_report, ReportError


class ThreeWayPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: ThreeWayWorker | None = None
        self._plan: MergePlan | None = None
        self._pool = QThreadPool.globalInstance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QLabel("Three-Way Structural Analysis")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        exp_badge = QLabel("EXPERIMENTAL")
        exp_badge.setStyleSheet(
            "background-color: #f38ba8; color: #1e1e2e; "
            "font-weight: bold; padding: 4px 8px; border-radius: 4px;"
        )
        exp_badge.setFixedWidth(120)
        layout.addWidget(exp_badge)

        info_label = QLabel(
            "This is an experimental three-way structural analysis that compares "
            "Base, Ours, and Theirs versions of an Ableton Live project. "
            "<b>It does not modify any source files, does not create a merged "
            ".als file, and does not apply conflict resolutions.</b> "
            "Results are analytical only."
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("subheading")
        layout.addWidget(info_label)

        input_group = QGroupBox("Inputs")
        input_group_layout = QVBoxLayout(input_group)

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
        input_group_layout.addLayout(make_input_row("Base:", self.base_input))

        self.ours_input = QLineEdit()
        self.ours_input.setPlaceholderText("Ours version (.als or .json)...")
        input_group_layout.addLayout(make_input_row("Ours:", self.ours_input))

        self.theirs_input = QLineEdit()
        self.theirs_input.setPlaceholderText("Theirs version (.als or .json)...")
        input_group_layout.addLayout(make_input_row("Theirs:", self.theirs_input))

        opt_layout = QHBoxLayout()
        self.allow_unrelated = QCheckBox("Allow unrelated projects")
        self.allow_unrelated.setToolTip(
            "Analyze projects that do not share common ancestry. "
            "Results will be marked with low confidence."
        )
        opt_layout.addWidget(self.allow_unrelated)

        self.analyze_btn = QPushButton("Analyze Versions")
        self.analyze_btn.setObjectName("primaryButton")
        self.analyze_btn.clicked.connect(self._start_analysis)
        opt_layout.addWidget(self.analyze_btn)

        input_group_layout.addLayout(opt_layout)
        layout.addWidget(input_group)

        drop_area = DropArea("Drop three files here (or use individual pickers)")
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

    def _on_dropped(self, path: str) -> None:
        if not self.base_input.text().strip():
            self.base_input.setText(path)
        elif not self.ours_input.text().strip():
            self.ours_input.setText(path)
        elif not self.theirs_input.text().strip():
            self.theirs_input.setText(path)

    def _start_analysis(self) -> None:
        base = self.base_input.text().strip()
        ours = self.ours_input.text().strip()
        theirs = self.theirs_input.text().strip()
        if not base or not ours or not theirs:
            return

        self._plan = None
        self.result_tree.setVisible(False)
        self.save_json_btn.setVisible(False)
        self.save_html_btn.setVisible(False)
        self.status_label.setText("Analyzing...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.analyze_btn.setEnabled(False)

        self._worker = ThreeWayWorker(ThreeWayTaskInput(
            base=base,
            ours=ours,
            theirs=theirs,
            allow_unrelated=self.allow_unrelated.isChecked(),
        ))
        self._worker.signals.finished.connect(self._on_analysis_finished)
        self._worker.signals.error.connect(self._on_analysis_error)
        self._pool.start(self._worker)

    @Slot(object)
    def _on_analysis_finished(self, result: object) -> None:
        self._worker = None
        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)

        if isinstance(result, MergePlan):
            self._plan = result
            self._populate_results(result)
            self.result_tree.setVisible(True)
            self.save_json_btn.setVisible(True)
            self.save_html_btn.setVisible(True)

    @Slot(str, str)
    def _on_analysis_error(self, message: str, details: str) -> None:
        self._worker = None
        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.status_label.setText("")
        from alscan.gui.dialogs.error_dialog import ErrorDialog
        dlg = ErrorDialog(message, details, self)
        dlg.exec()

    def _populate_results(self, plan: MergePlan) -> None:
        self.result_tree.clear()
        self.result_tree.setColumnCount(2)

        root = QTreeWidgetItem(["Three-Way Analysis Results", ""])
        self.result_tree.addTopLevelItem(root)

        root.addChild(QTreeWidgetItem(["Confidence", plan.lineage_confidence]))
        root.addChild(QTreeWidgetItem(["Conflicts", str(plan.conflict_count)]))
        root.addChild(QTreeWidgetItem(["Auto-Resolved", str(len(plan.auto_resolved))]))
        root.addChild(QTreeWidgetItem(["Warning Count", str(plan.warning_count)]))

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
                tc_item.addChild(QTreeWidgetItem([
                    f"[{tc.kind}] {tc.name}",
                    tc.branch
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
                pos = entry.get("position", "?")
                name = entry.get("name", "?")
                tid = entry.get("track_id", "?")
                order_item.addChild(QTreeWidgetItem([f"#{pos}: {name}", f"ID: {tid}"]))

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
        sources = []

        def _path(p: str) -> Path:
            return Path(p)

        if self.base_input.text():
            sources.append(_path(self.base_input.text()))
        if self.ours_input.text():
            sources.append(_path(self.ours_input.text()))
        if self.theirs_input.text():
            sources.append(_path(self.theirs_input.text()))

        try:
            save_merge_plan(self._plan, Path(path), sources)
            QMessageBox.information(self, "Saved", f"Merge plan saved to:\n{path}")
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
        sources = []

        def _path(p: str) -> Path:
            return Path(p)

        if self.base_input.text():
            sources.append(_path(self.base_input.text()))
        if self.ours_input.text():
            sources.append(_path(self.ours_input.text()))
        if self.theirs_input.text():
            sources.append(_path(self.theirs_input.text()))

        try:
            save_merge_report(self._plan, Path(path), sources)
            webbrowser.open(Path(path).as_uri())
            QMessageBox.information(
                self, "Saved",
                f"Conflict report saved and opened:\n{path}"
            )
        except ReportError as e:
            QMessageBox.warning(self, "Save Error", str(e))
