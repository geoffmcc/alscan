# SPDX-License-Identifier: GPL-3.0-only
"""Structural comparison page for .als files and snapshots."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QProgressBar, QFrame,
)
from PySide6.QtCore import Qt, QThreadPool, Slot

from alscan.io_safety import validate_output_dest
from alscan.gui.compare_analysis import analyse, _build_summaries, _generate_summary_text
from alscan.gui.workers import CompareWorker, CompareTaskInput
from alscan.gui.widgets.drop_area import DropArea
from alscan.gui.widgets.compare_result_widget import CompareResultWidget
from alscan.versioner import DiffResult

_log = logging.getLogger(__name__)


class ComparePage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: CompareWorker | None = None
        self._pool = QThreadPool.globalInstance()
        self._last_path_a: str = ""
        self._last_path_b: str = ""
        self._compare_completed: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        heading = QLabel("Compare Versions")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        self.info_label = QLabel(
            "Compare two .als files, an .als file with a snapshot, or two snapshots. "
            "This compares structural metadata only: tempo, time signature, locators, "
            "tracks, devices, and more."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setObjectName("subheading")
        layout.addWidget(self.info_label)

        self.input_area = QFrame()
        self.input_area.setObjectName("compareInputArea")
        self._build_input_area()
        layout.addWidget(self.input_area)

        self.drop_area = DropArea("Drop two .als or snapshot files here (or use browse)")
        self.drop_area.path_dropped.connect(self._on_dropped)
        layout.addWidget(self.drop_area)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subheading")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.result_widget = CompareResultWidget()
        self.result_widget.setVisible(False)
        self.result_widget.swap_requested.connect(self._on_swap_sources)
        self.result_widget.copy_summary_requested.connect(self._on_summary_copied)
        self.result_widget.export_report_requested.connect(self._on_export_report)
        layout.addWidget(self.result_widget, 1)

    def _build_input_area(self) -> None:
        input_layout = QVBoxLayout(self.input_area)

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

        btn_layout = QHBoxLayout()
        self.compare_btn = QPushButton("Compare")
        self.compare_btn.setObjectName("primaryButton")
        self.compare_btn.clicked.connect(self._start_compare)
        btn_layout.addWidget(self.compare_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_compare)
        btn_layout.addWidget(self.cancel_btn)

        self.change_sources_btn = QPushButton("Change Sources")
        self.change_sources_btn.setVisible(False)
        self.change_sources_btn.clicked.connect(self._expand_input_area)
        btn_layout.addWidget(self.change_sources_btn)

        btn_layout.addStretch()
        input_layout.addLayout(btn_layout)

    def set_sources(self, path_a: str, path_b: str) -> None:
        self.path_a_input.setText(path_a)
        self.path_b_input.setText(path_b)

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

        self._last_path_a = path_a
        self._last_path_b = path_b

        self.result_widget.setVisible(False)
        self.status_label.setText("Comparing...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.compare_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)

        self._worker = CompareWorker(CompareTaskInput(path_a=path_a, path_b=path_b))
        self._worker.signals.finished.connect(self._on_compare_finished)
        self._worker.signals.error.connect(self._on_compare_error)
        self._pool.start(self._worker)

    def _cancel_compare(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            try:
                self._worker.signals.finished.disconnect(self._on_compare_finished)
            except (TypeError, RuntimeError):
                pass
            try:
                self._worker.signals.error.disconnect(self._on_compare_error)
            except (TypeError, RuntimeError):
                pass
            self._worker = None
        self.progress_bar.setVisible(False)
        self.compare_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.status_label.setText("Comparison cancelled.")

    @Slot(object)
    def _on_compare_finished(self, result: object) -> None:
        self._worker = None
        self.progress_bar.setVisible(False)
        self.compare_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)

        if isinstance(result, DiffResult):
            self._compare_completed = True
            self.status_label.setText("Comparison complete.")
            self.result_widget.setVisible(True)
            self.result_widget.set_result(
                result,
                self._last_path_a,
                self._last_path_b,
            )
            self._compact_input_area()

    @Slot(str, str)
    def _on_compare_error(self, message: str, details: str) -> None:
        self._worker = None
        self.progress_bar.setVisible(False)
        self.compare_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.status_label.setText("")
        from alscan.gui.dialogs.error_dialog import ErrorDialog
        dlg = ErrorDialog(message, details, self)
        dlg.exec()

    def _compact_input_area(self) -> None:
        self.info_label.setVisible(False)
        self.drop_area.setMinimumHeight(20)
        self.drop_area.setMaximumHeight(40)
        self.drop_area.label.setText("Drop new files to compare different versions")
        self.drop_area.label.setObjectName("")
        self.input_area.setMaximumHeight(40)
        self.compare_btn.setText("Recompare")
        self.change_sources_btn.setVisible(True)

    def _expand_input_area(self) -> None:
        self.info_label.setVisible(True)
        self.drop_area.setMinimumHeight(80)
        self.drop_area.setMaximumHeight(16777215)
        self.drop_area.label.setText("Drop two .als or snapshot files here (or use browse)")
        self.drop_area.label.setObjectName("subheading")
        self.input_area.setMaximumHeight(16777215)
        self.compare_btn.setText("Compare")
        self.change_sources_btn.setVisible(False)

    def _on_swap_sources(self) -> None:
        if not self._last_path_a or not self._last_path_b:
            return
        diff = self.result_widget.raw_diff()
        if diff is None:
            return
        self._last_path_a, self._last_path_b = self._last_path_b, self._last_path_a
        self.path_a_input.setText(self._last_path_a)
        self.path_b_input.setText(self._last_path_b)
        self.result_widget.set_swapped_result(
            diff, self._last_path_a, self._last_path_b
        )
        self.status_label.setText("Sources swapped.")

    def _on_summary_copied(self) -> None:
        self.status_label.setText("Summary copied to clipboard.")

    def _on_export_report(self) -> None:
        diff = self.result_widget.raw_diff()
        if diff is None:
            self.status_label.setText("No comparison result to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Comparison Report",
            "comparison_report.txt", "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return

        dest = Path(path)
        sources = []
        if self._last_path_a:
            sources.append(Path(self._last_path_a))
        if self._last_path_b:
            sources.append(Path(self._last_path_b))

        try:
            validate_output_dest(dest, sources, reject_ableton_exts=True)
        except ValueError as e:
            self.status_label.setText(f"Export failed: {e}")
            return

        try:
            analysis = analyse(diff, self._last_path_a, self._last_path_b)
            lines: list[str] = []
            lines.append("ALScan Comparison Report")
            lines.append(f"Source A: {self._last_path_a}")
            lines.append(f"Source B: {self._last_path_b}")
            lines.append("=" * 60)
            lines.append("")
            summaries = _build_summaries(analysis.items)
            lines.extend(_generate_summary_text(analysis.items, summaries))
            lines.append("")
            for item in analysis.items:
                line = f"[{item.change_type.upper()}] {item.object_type}: {item.object_name}"
                if item.property_name:
                    line += f" \u2014 {item.property_name}: {item.value_a} \u2192 {item.value_b}"
                if item.explanation:
                    line += f" \u2014 {item.explanation}"
                lines.append(line)

            dest.write_text("\n".join(lines), encoding="utf-8")
            self.status_label.setText(f"Report exported to {dest.name}")
        except Exception as e:
            _log.exception("Export report failed")
            self.status_label.setText(f"Export failed: {e}")
