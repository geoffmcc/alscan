# SPDX-License-Identifier: GPL-3.0-only
"""Home page with quick actions and recent projects."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QFrame,
)
from PySide6.QtCore import Qt, Signal

from alscan.gui import APP_NAME, APP_DESCRIPTION, APP_VERSION
from alscan.gui.widgets.drop_area import DropArea


class HomePage(QWidget):
    navigate = Signal(str)
    scan_path = Signal(str)
    scan_folder = Signal(str)
    compare_requested = Signal()
    snapshot_requested = Signal()
    three_way_requested = Signal()

    def __init__(self, recent_paths: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._recent_paths = recent_paths or []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel(APP_NAME)
        heading.setObjectName("heading")
        heading.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(heading)

        subtitle = QLabel(APP_DESCRIPTION)
        subtitle.setObjectName("subheading")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setObjectName("subheading")
        layout.addWidget(version_label)

        layout.addSpacing(8)

        actions_label = QLabel("Quick Actions")
        actions_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(actions_label)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        scan_btn = QPushButton("Scan Project")
        scan_btn.setObjectName("primaryButton")
        scan_btn.clicked.connect(self._on_scan_project)
        actions_layout.addWidget(scan_btn)

        scan_folder_btn = QPushButton("Scan Folder")
        scan_folder_btn.clicked.connect(self._on_scan_folder)
        actions_layout.addWidget(scan_folder_btn)

        compare_btn = QPushButton("Compare Versions")
        compare_btn.clicked.connect(self.compare_requested.emit)
        actions_layout.addWidget(compare_btn)

        snap_btn = QPushButton("Create Snapshot")
        snap_btn.clicked.connect(self.snapshot_requested.emit)
        actions_layout.addWidget(snap_btn)

        three_way_btn = QPushButton("Three-Way Analysis")
        three_way_btn.clicked.connect(self.three_way_requested.emit)
        actions_layout.addWidget(three_way_btn)

        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        drop_area = DropArea("Drop an .als file or project folder to scan")
        drop_area.path_dropped.connect(self._on_dropped)
        layout.addWidget(drop_area)

        layout.addSpacing(8)

        recent_label = QLabel("Recent Projects")
        recent_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(recent_label)

        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(200)
        self.recent_list.itemDoubleClicked.connect(self._on_recent_clicked)
        layout.addWidget(self.recent_list, 1)

        self._refresh_recent()

        layout.addStretch()

    def _on_scan_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Ableton Project",
            "", "Ableton Live Set (*.als);;All Files (*)"
        )
        if path:
            self.scan_path.emit(path)

    def _on_scan_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Folder Containing Projects"
        )
        if path:
            self.scan_folder.emit(path)

    def _on_dropped(self, path: str) -> None:
        p = Path(path)
        if p.is_dir():
            self.scan_folder.emit(path)
        else:
            self.scan_path.emit(path)

    def _on_recent_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.scan_path.emit(path)

    def _refresh_recent(self) -> None:
        self.recent_list.clear()
        for p in self._recent_paths:
            item = QListWidgetItem(p)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.recent_list.addItem(item)
        if not self._recent_paths:
            item = QListWidgetItem("No recent projects yet")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.recent_list.addItem(item)

    def update_recent(self, paths: list[str]) -> None:
        self._recent_paths = paths
        self._refresh_recent()
