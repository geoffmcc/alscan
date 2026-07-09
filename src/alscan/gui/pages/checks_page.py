# SPDX-License-Identifier: GPL-3.0-only
"""Health checks browser page."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QTextEdit,
)
from PySide6.QtCore import Qt

from alscan.services import get_checks


class ChecksPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QLabel("Health Checks Reference")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        desc = QLabel(
            "All checks registered in the ALScan check registry. "
            "These are the same checks used by the CLI command alscan list-checks."
        )
        desc.setWordWrap(True)
        desc.setObjectName("subheading")
        layout.addWidget(desc)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Check ID", "Severity", "Description"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)

        self.detail_label = QLabel("Select a check to see details")
        self.detail_label.setObjectName("subheading")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        self._populate()

    def _populate(self) -> None:
        checks = get_checks()
        self.table.setRowCount(len(checks))
        for i, c in enumerate(checks):
            self.table.setItem(i, 0, QTableWidgetItem(c.name))
            sev_item = QTableWidgetItem(c.severity.upper() if c.severity else "")
            if c.severity == "error":
                sev_item.setForeground(Qt.GlobalColor.red)
            elif c.severity == "warning":
                sev_item.setForeground(Qt.GlobalColor.darkYellow)
            elif c.severity == "info":
                sev_item.setForeground(Qt.GlobalColor.darkCyan)
            self.table.setItem(i, 1, sev_item)
            self.table.setItem(i, 2, QTableWidgetItem(c.description))

    def _on_selection_changed(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            name_item = self.table.item(row, 0)
            desc_item = self.table.item(row, 2)
            if name_item and desc_item:
                self.detail_label.setText(
                    f"<b>{name_item.text()}</b><br>{desc_item.text()}"
                )
