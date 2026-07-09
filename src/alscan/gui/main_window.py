# SPDX-License-Identifier: GPL-3.0-only
"""Main application window with navigation sidebar."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QStatusBar, QLabel, QFrame,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from alscan.gui import APP_NAME, APP_VERSION
from alscan.gui.settings import AppSettings
from alscan.gui.pages.home_page import HomePage
from alscan.gui.pages.scan_page import ScanPage
from alscan.gui.pages.batch_page import BatchPage
from alscan.gui.pages.checks_page import ChecksPage
from alscan.gui.pages.snapshots_page import SnapshotsPage
from alscan.gui.pages.compare_page import ComparePage
from alscan.gui.pages.three_way_page import ThreeWayPage
from alscan.gui.pages.settings_page import SettingsPage


class NavButton(QPushButton):
    def __init__(self, text: str, page_id: str, parent=None) -> None:
        super().__init__(text, parent)
        self.page_id = page_id
        self.setCheckable(True)
        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self._settings = settings
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1000, 650)

        self._setup_ui()

        geo = self._settings.window_geometry
        if geo:
            self.restoreGeometry(geo)

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        nav_frame = QFrame()
        nav_frame.setFixedWidth(200)
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(8, 16, 8, 16)
        nav_layout.setSpacing(4)

        app_label = QLabel(APP_NAME)
        app_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 8px;")
        nav_layout.addWidget(app_label)

        nav_layout.addSpacing(12)

        self._nav_buttons: list[NavButton] = []
        nav_items = [
            ("Home", "home"),
            ("Scan", "scan"),
            ("Batch Scan", "batch"),
            ("Snapshots", "snapshots"),
            ("Compare", "compare"),
            ("Three-Way Analysis", "threeway"),
            ("Checks", "checks"),
            ("Settings", "settings"),
        ]

        for text, page_id in nav_items:
            btn = NavButton(text, page_id)
            btn.clicked.connect(lambda checked=False, pid=page_id: self._navigate_to(pid))
            nav_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        nav_layout.addStretch()

        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setObjectName("subheading")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(version_label)

        main_layout.addWidget(nav_frame)

        content_frame = QFrame()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)

        main_layout.addWidget(content_frame, 1)

        self.home_page = HomePage(
            recent_paths=self._settings.recent_paths
        )
        self.scan_page = ScanPage(self._settings)
        self.batch_page = BatchPage()
        self.snapshots_page = SnapshotsPage(self._settings)
        self.compare_page = ComparePage()
        self.three_way_page = ThreeWayPage()
        self.checks_page = ChecksPage()
        self.settings_page = SettingsPage(self._settings)

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.scan_page)
        self.stack.addWidget(self.batch_page)
        self.stack.addWidget(self.snapshots_page)
        self.stack.addWidget(self.compare_page)
        self.stack.addWidget(self.three_way_page)
        self.stack.addWidget(self.checks_page)
        self.stack.addWidget(self.settings_page)

        self._pages = {
            "home": 0,
            "scan": 1,
            "batch": 2,
            "snapshots": 3,
            "compare": 4,
            "threeway": 5,
            "checks": 6,
            "settings": 7,
        }

        self.home_page.scan_path.connect(
            lambda p: self._navigate_to_scan(p)
        )
        self.home_page.scan_folder.connect(
            lambda p: self._navigate_to_batch(p)
        )
        self.home_page.compare_requested.connect(
            lambda: self._navigate_to("compare")
        )
        self.home_page.snapshot_requested.connect(
            lambda: self._navigate_to("snapshots")
        )
        self.home_page.three_way_requested.connect(
            lambda: self._navigate_to("threeway")
        )

        self._navigate_to("home")

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

    def _navigate_to(self, page_id: str) -> None:
        idx = self._pages.get(page_id, 0)
        self.stack.setCurrentIndex(idx)
        for btn in self._nav_buttons:
            btn.setChecked(btn.page_id == page_id)

    def _navigate_to_scan(self, path: str) -> None:
        self.scan_page.set_path(path)
        self._navigate_to("scan")
        self._settings.add_recent_path(path)

    def _navigate_to_batch(self, path: str) -> None:
        self.batch_page.set_path(path)
        self._navigate_to("batch")
        self._settings.add_recent_path(path)

    def closeEvent(self, event) -> None:
        self._settings.window_geometry = self.saveGeometry()
        super().closeEvent(event)
