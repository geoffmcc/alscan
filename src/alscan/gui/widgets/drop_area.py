# SPDX-License-Identifier: GPL-3.0-only
"""Drag-and-drop file/folder area widget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent


class DropArea(QFrame):
    path_dropped = Signal(str)

    ACCEPTED_EXTS = {".als", ".json"}

    def __init__(self, text: str = "Drop .als file or project folder here", parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMinimumHeight(80)
        self.setCursor(Qt.CursorShape.DragCopyCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setObjectName("subheading")
        layout.addWidget(self.label)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if not urls:
            return
        path = Path(urls[0].toLocalFile())
        if path.suffix.lower() in self.ACCEPTED_EXTS or path.is_dir():
            self.path_dropped.emit(str(path))


class ThreeWayDropArea(QFrame):
    paths_dropped = Signal(str, str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMinimumHeight(100)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label = QLabel(
            "Drop three files here\n"
            "or use individual file pickers below"
        )
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setObjectName("subheading")
        layout.addWidget(self.label)
        self._paths: list[str] = []

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and len(event.mimeData().urls()) <= 5:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) < 3:
            return
        self._paths = [urls[0].toLocalFile(), urls[1].toLocalFile(), urls[2].toLocalFile()]
        self.paths_dropped.emit(self._paths[0], self._paths[1], self._paths[2])
