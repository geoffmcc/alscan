# SPDX-License-Identifier: GPL-3.0-only
"""Snapshot creation and history page."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QTableWidget, QTableWidgetItem,
    QProgressBar, QHeaderView, QAbstractItemView, QMessageBox,
    QGroupBox,
)
from PySide6.QtCore import Qt, QThreadPool, Slot

from alscan.gui.workers import SnapshotWorker, SnapshotTaskInput, ListSnapshotsWorker
from alscan.gui.settings import AppSettings
from alscan.gui.widgets.drop_area import DropArea
from alscan.services import SnapshotInfo


class SnapshotsPage(QWidget):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._snap_worker: SnapshotWorker | None = None
        self._pool = QThreadPool.globalInstance()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QLabel("Snapshots")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        info_label = QLabel(
            "Snapshots capture structural metadata only: tempo, time signature, "
            "track list with device details, clip counts, volume, colour, group "
            "assignment, plugin references, and a structural fingerprint. "
            "No audio content is stored."
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("subheading")
        layout.addWidget(info_label)

        snap_group = QGroupBox("Create Snapshot")
        snap_layout = QHBoxLayout(snap_group)
        self.snap_path_input = QLineEdit()
        self.snap_path_input.setPlaceholderText("Path to .als file or project folder...")
        snap_layout.addWidget(self.snap_path_input, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_snapshot)
        snap_layout.addWidget(browse_btn)

        self.snap_btn = QPushButton("Create Snapshot")
        self.snap_btn.setObjectName("primaryButton")
        self.snap_btn.clicked.connect(self._create_snapshot)
        snap_layout.addWidget(self.snap_btn)
        layout.addWidget(snap_group)

        drop_area = DropArea("Drop .als file to create snapshot")
        drop_area.path_dropped.connect(self.snap_path_input.setText)
        layout.addWidget(drop_area)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subheading")
        layout.addWidget(self.status_label)

        history_group = QGroupBox("Snapshot History")
        history_layout = QVBoxLayout(history_group)
        hist_input_layout = QHBoxLayout()
        self.hist_path_input = QLineEdit()
        self.hist_path_input.setPlaceholderText("Project folder to browse snapshots...")
        hist_input_layout.addWidget(self.hist_path_input, 1)

        hist_browse_btn = QPushButton("Browse...")
        hist_browse_btn.clicked.connect(self._browse_history)
        hist_input_layout.addWidget(hist_browse_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_history)
        hist_input_layout.addWidget(self.refresh_btn)

        open_folder_btn = QPushButton("Open Snapshots Folder")
        open_folder_btn.clicked.connect(self._open_snaps_folder)
        hist_input_layout.addWidget(open_folder_btn)

        history_layout.addLayout(hist_input_layout)
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels([
            "#", "Date/Time", "Tempo", "Tracks", "Devices"
        ])
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.history_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.verticalHeader().setVisible(False)
        history_layout.addWidget(self.history_table, 1)
        layout.addWidget(history_group, 1)

    def _browse_snapshot(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Ableton Project",
            "", "Ableton Live Set (*.als);;All Files (*)"
        )
        if path:
            self.snap_path_input.setText(path)

    def _create_snapshot(self) -> None:
        path = self.snap_path_input.text().strip()
        if not path:
            return

        self.status_label.setText("Creating snapshot...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.snap_btn.setEnabled(False)

        self._snap_worker = SnapshotWorker(SnapshotTaskInput(path=path))
        self._snap_worker.signals.finished.connect(self._on_snapshot_created)
        self._snap_worker.signals.error.connect(self._on_snapshot_error)
        self._pool.start(self._snap_worker)

    @Slot(object)
    def _on_snapshot_created(self, dest: object) -> None:
        self._snap_worker = None
        self.progress_bar.setVisible(False)
        self.snap_btn.setEnabled(True)
        if isinstance(dest, Path):
            self.status_label.setText(f"Snapshot saved: {dest}")
            QMessageBox.information(
                self, "Snapshot Created",
                f"Structural snapshot saved to:\n{dest}"
            )

    @Slot(str, str)
    def _on_snapshot_error(self, message: str, details: str) -> None:
        self._snap_worker = None
        self.progress_bar.setVisible(False)
        self.snap_btn.setEnabled(True)
        self.status_label.setText("")
        from alscan.gui.dialogs.error_dialog import ErrorDialog
        dlg = ErrorDialog(message, details, self)
        dlg.exec()

    def _browse_history(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if path:
            self.hist_path_input.setText(path)
            self._refresh_history()

    def _refresh_history(self) -> None:
        path = self.hist_path_input.text().strip()
        if not path:
            return
        from alscan.gui.workers import ListSnapshotsWorker
        worker = ListSnapshotsWorker(path)
        worker.signals.finished.connect(self._on_history_loaded)
        worker.signals.error.connect(self._on_history_error)
        self._pool.start(worker)

    @Slot(object)
    def _on_history_loaded(self, infos: object) -> None:
        if isinstance(infos, list):
            self.history_table.setRowCount(len(infos))
            for i, info in enumerate(infos):
                ts = datetime.fromtimestamp(info.timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                self.history_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                self.history_table.setItem(i, 1, QTableWidgetItem(ts))
                self.history_table.setItem(i, 2, QTableWidgetItem(f"{info.tempo} BPM"))
                self.history_table.setItem(i, 3, QTableWidgetItem(str(info.track_count)))
                self.history_table.setItem(i, 4, QTableWidgetItem(str(info.device_count)))

    @Slot(str, str)
    def _on_history_error(self, message: str, details: str) -> None:
        self.status_label.setText(f"Error: {message}")

    def _open_snaps_folder(self) -> None:
        path = self.hist_path_input.text().strip()
        if path:
            import subprocess
            snaps_path = Path(path).resolve() / ".alscan" / "snapshots"
            if snaps_path.exists():
                subprocess.Popen(["explorer", str(snaps_path)])
            else:
                QMessageBox.information(
                    self, "No Snapshots",
                    f"No snapshots folder found at:\n{snaps_path}"
                )
