# SPDX-License-Identifier: GPL-3.0-only
"""Error display dialog with expandable technical details."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QDialogButtonBox,
)
from PySide6.QtCore import Qt


class ErrorDialog(QDialog):
    def __init__(self, message: str, details: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Error")
        self.setMinimumSize(500, 300)
        layout = QVBoxLayout(self)

        icon_label = QLabel("\u26A0\uFE0F Error")
        icon_label.setObjectName("errorText")
        icon_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(icon_label)

        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(msg_label)

        if details:
            expand_btn = QPushButton("Show Technical Details")
            expand_btn.setCheckable(True)
            expand_btn.setChecked(False)
            layout.addWidget(expand_btn)

            details_edit = QTextEdit()
            details_edit.setPlainText(details)
            details_edit.setReadOnly(True)
            details_edit.setVisible(False)
            details_edit.setMaximumHeight(200)
            layout.addWidget(details_edit)

            expand_btn.toggled.connect(details_edit.setVisible)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)
