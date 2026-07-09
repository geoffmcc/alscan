# SPDX-License-Identifier: GPL-3.0-only
"""Badge widget for change types in compare results."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt

from alscan.gui.compare_analysis import ChangeType


_BADGE_CLASS = {
    "added": "badgeAdded",
    "removed": "badgeRemoved",
    "modified": "badgeModified",
    "moved": "badgeMoved",
    "renamed": "badgeRenamed",
}

_BADGE_TEXT = {
    "added": "Added",
    "removed": "Removed",
    "modified": "Modified",
    "moved": "Moved",
    "renamed": "Renamed",
}


class BadgeWidget(QLabel):
    def __init__(self, change_type: ChangeType, parent=None) -> None:
        super().__init__(parent)
        label = _BADGE_TEXT.get(change_type, change_type.title())
        self.setText(label)
        self.setObjectName(_BADGE_CLASS.get(change_type, "badgeModified"))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(22)
        self.setMinimumWidth(64)
        self.setToolTip(label)
