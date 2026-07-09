# SPDX-License-Identifier: GPL-3.0-only
"""Recursive batch scan page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QTableWidget, QTableWidgetItem,
    QProgressBar, QHeaderView, QAbstractItemView, QMessageBox,
)
from PySide6.QtCore import Qt, QThreadPool, Slot

from alscan.gui.workers import BatchScanWorker, BatchScanTaskInput
from alscan.models import ScanResult


class BatchPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: BatchScanWorker | None = None
        self._results: list[tuple[Path, ScanResult | None, str | None]] = []
        self._pool = QThreadPool.globalInstance()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QLabel("Batch Scan Folder")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        input_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Root folder containing Ableton projects...")
        input_layout.addWidget(self.path_input, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        input_layout.addWidget(browse_btn)

        self.scan_btn = QPushButton("Scan All")
        self.scan_btn.setObjectName("primaryButton")
        self.scan_btn.clicked.connect(self._start_scan)
        input_layout.addWidget(self.scan_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel_scan)
        self.cancel_btn.setVisible(False)
        input_layout.addWidget(self.cancel_btn)

        layout.addLayout(input_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subheading")
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Project", "Status", "Errors", "Warnings", "Info"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table, 1)

    def set_path(self, path: str) -> None:
        self.path_input.setText(path)
        self._start_scan()

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Root Folder")
        if path:
            self.path_input.setText(path)

    def _start_scan(self) -> None:
        path = self.path_input.text().strip()
        if not path:
            return
        self._results = []
        self.table.setRowCount(0)
        self.status_label.setText("Scanning...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.scan_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)

        self._worker = BatchScanWorker(BatchScanTaskInput(root=path))
        self._worker.signals.finished.connect(self._on_scan_finished)
        self._worker.signals.error.connect(self._on_scan_error)
        self._pool.start(self._worker)

    def _cancel_scan(self) -> None:
        if self._worker:
            self._worker.cancel()
            self._worker = None
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.status_label.setText("Scan cancelled")

    @Slot(object)
    def _on_scan_finished(self, result: object) -> None:
        self._worker = None
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)

        if isinstance(result, list):
            self._results = result
            self._populate_table()

    @Slot(str, str)
    def _on_scan_error(self, message: str, details: str) -> None:
        self._worker = None
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.status_label.setText(f"Error: {message}")

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self._results))
        success = 0
        failed = 0
        for i, (proj_dir, result, error) in enumerate(self._results):
            self.table.setItem(i, 0, QTableWidgetItem(proj_dir.name))
            if error:
                self.table.setItem(i, 1, QTableWidgetItem(f"Failed: {error}"))
                failed += 1
            elif result:
                self.table.setItem(i, 1, QTableWidgetItem("OK"))
                self.table.setItem(i, 2, QTableWidgetItem(str(len(result.errors))))
                self.table.setItem(i, 3, QTableWidgetItem(str(len(result.warnings))))
                self.table.setItem(i, 4, QTableWidgetItem(str(len(result.info))))
                success += 1

        self.status_label.setText(
            f"Complete: {success} succeeded, {failed} failed "
            f"({len(self._results)} total)"
        )

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        if row < len(self._results):
            proj_dir, result, error = self._results[row]
            if result:
                from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit
                dlg = QDialog(self)
                dlg.setWindowTitle(proj_dir.name)
                dlg.setMinimumSize(600, 400)
                layout = QVBoxLayout(dlg)
                text = QTextEdit()
                text.setReadOnly(True)
                from alscan.report.terminal import print_terminal_report
                report_text = print_terminal_report(result, verbose=True)
                text.setPlainText(report_text)
                layout.addWidget(text)
                dlg.exec()
