# SPDX-License-Identifier: GPL-3.0-only
"""Single project scan page."""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QComboBox, QCheckBox, QProgressBar,
    QFrame, QMessageBox, QSplitter, QGroupBox,
)
from PySide6.QtCore import Qt, QThreadPool, Slot

from alscan.gui.widgets.result_table import ResultTableWidget
from alscan.gui.widgets.drop_area import DropArea
from alscan.gui.workers import ScanWorker, ScanTaskInput
from alscan.gui.settings import AppSettings
from alscan.services import (
    render_health_report,
    save_report,
    ReportError,
)
from alscan.models import ScanResult


class ScanPage(QWidget):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._result: ScanResult | None = None
        self._worker: ScanWorker | None = None
        self._pool = QThreadPool.globalInstance()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QLabel("Project Health Scan")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        input_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Path to .als file or project folder...")
        input_layout.addWidget(self.path_input, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        input_layout.addWidget(browse_btn)

        self.scan_btn = QPushButton("Scan")
        self.scan_btn.setObjectName("primaryButton")
        self.scan_btn.clicked.connect(self._start_scan)
        input_layout.addWidget(self.scan_btn)

        layout.addLayout(input_layout)

        drop_area = DropArea("Drop .als file or project folder to scan")
        drop_area.path_dropped.connect(self.path_input.setText)
        layout.addWidget(drop_area)

        options_group = QGroupBox("Options")
        options_layout = QHBoxLayout(options_group)
        self.verbose_check = QCheckBox("Verbose")
        options_layout.addWidget(self.verbose_check)
        options_layout.addWidget(QLabel("Output format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["terminal", "json", "html", "csv"])
        options_layout.addWidget(self.format_combo)
        options_layout.addStretch()
        layout.addWidget(options_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subheading")
        layout.addWidget(self.status_label)

        self.result_table = ResultTableWidget()
        self.result_table.setVisible(False)
        layout.addWidget(self.result_table, 1)

        export_layout = QHBoxLayout()
        self.export_json_btn = QPushButton("Export JSON")
        self.export_json_btn.clicked.connect(self._export_json)
        self.export_json_btn.setVisible(False)
        export_layout.addWidget(self.export_json_btn)

        self.export_html_btn = QPushButton("Export HTML & Open")
        self.export_html_btn.clicked.connect(self._export_html)
        self.export_html_btn.setVisible(False)
        export_layout.addWidget(self.export_html_btn)

        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.clicked.connect(self._export_csv)
        self.export_csv_btn.setVisible(False)
        export_layout.addWidget(self.export_csv_btn)

        self.rescan_btn = QPushButton("Rescan")
        self.rescan_btn.clicked.connect(self._start_scan)
        self.rescan_btn.setVisible(False)
        export_layout.addWidget(self.rescan_btn)

        open_folder_btn = QPushButton("Open Source Folder")
        open_folder_btn.clicked.connect(self._open_folder)
        open_folder_btn.setVisible(True)
        export_layout.addWidget(open_folder_btn)

        export_layout.addStretch()
        layout.addLayout(export_layout)

    def set_path(self, path: str) -> None:
        self.path_input.setText(path)
        self._start_scan()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Ableton Project",
            "", "Ableton Live Set (*.als);;All Files (*)"
        )
        if path:
            self.path_input.setText(path)

    def _start_scan(self) -> None:
        path = self.path_input.text().strip()
        if not path:
            return

        self._result = None
        self.result_table.setVisible(False)
        self.export_json_btn.setVisible(False)
        self.export_html_btn.setVisible(False)
        self.export_csv_btn.setVisible(False)
        self.rescan_btn.setVisible(False)
        self.status_label.setText("Scanning...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.scan_btn.setEnabled(False)

        self._worker = ScanWorker(ScanTaskInput(
            path=path,
            verbose=self.verbose_check.isChecked(),
        ))
        self._worker.signals.finished.connect(self._on_scan_finished)
        self._worker.signals.error.connect(self._on_scan_error)
        self._pool.start(self._worker)

    @Slot(object)
    def _on_scan_finished(self, result: object) -> None:
        self._worker = None
        self._result = result
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.result_table.setVisible(True)
        self.rescan_btn.setVisible(True)

        if isinstance(result, ScanResult):
            if result.findings:
                self.status_label.setText(
                    f"Found {len(result.errors)} errors, "
                    f"{len(result.warnings)} warnings, "
                    f"{len(result.info)} info items"
                )
                self.result_table.set_findings(result.findings)
            else:
                self.status_label.setText("No issues found - project looks healthy!")
            self.export_json_btn.setVisible(True)
            self.export_html_btn.setVisible(True)
            self.export_csv_btn.setVisible(True)

    @Slot(str, str)
    def _on_scan_error(self, message: str, details: str) -> None:
        self._worker = None
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.status_label.setText("")
        from alscan.gui.dialogs.error_dialog import ErrorDialog
        dlg = ErrorDialog(message, details, self)
        dlg.exec()

    def _export_json(self) -> None:
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save JSON Report",
            str(Path(self._result.project.path).parent / "alscan-report.json"),
            "JSON (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            content = render_health_report(self._result, "json")
            save_report(content, Path(path))
            QMessageBox.information(self, "Saved", f"JSON report saved to:\n{path}")
        except ReportError as e:
            QMessageBox.warning(self, "Save Error", str(e))

    def _export_html(self) -> None:
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save HTML Report",
            str(Path(self._result.project.path).parent / "alscan-report.html"),
            "HTML (*.html);;All Files (*)"
        )
        if not path:
            return
        try:
            content = render_health_report(self._result, "html")
            save_report(content, Path(path))
            webbrowser.open(Path(path).as_uri())
            QMessageBox.information(self, "Saved", f"HTML report saved and opened:\n{path}")
        except ReportError as e:
            QMessageBox.warning(self, "Save Error", str(e))

    def _export_csv(self) -> None:
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV Report",
            str(Path(self._result.project.path).parent / "alscan-report.csv"),
            "CSV (*.csv);;All Files (*)"
        )
        if not path:
            return
        try:
            content = render_health_report(self._result, "csv")
            save_report(content, Path(path))
            QMessageBox.information(self, "Saved", f"CSV report saved to:\n{path}")
        except ReportError as e:
            QMessageBox.warning(self, "Save Error", str(e))

    def _open_folder(self) -> None:
        path = self.path_input.text().strip()
        if path:
            from alscan.gui.platform_utils import open_folder
            folder = Path(path).resolve()
            if folder.is_file():
                folder = folder.parent
            open_folder(folder)
