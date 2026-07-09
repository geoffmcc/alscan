# SPDX-License-Identifier: GPL-3.0-only
"""Sortable scan findings table with severity filtering and search."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QLineEdit,
    QComboBox, QLabel, QPushButton, QHeaderView, QSplitter,
    QAbstractItemView, QTextEdit,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QColor

from alscan.models import Finding


class FindingsTableModel(QAbstractTableModel):
    COLUMNS = ["Severity", "Check", "Title", "Location", "Message"]

    def __init__(self, findings: list[Finding], parent=None) -> None:
        super().__init__(parent)
        self._findings = findings

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._findings)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        f = self._findings[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return f.severity.upper()
            elif col == 1:
                return f.check_name
            elif col == 2:
                return f.title
            elif col == 3:
                return f.location
            elif col == 4:
                return f.message
        if role == Qt.ItemDataRole.ForegroundRole and col == 0:
            if f.severity == "error":
                return QColor("#f38ba8")
            elif f.severity == "warning":
                return QColor("#fab387")
            elif f.severity == "info":
                return QColor("#89b4fa")
        if role == Qt.ItemDataRole.UserRole:
            return f
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        self.layoutAboutToBeChanged.emit()
        rev = order == Qt.SortOrder.DescendingOrder
        self._findings.sort(key=lambda f: (
            {"error": 0, "warning": 1, "info": 2, "suggestion": 3}.get(f.severity, 4),
            f.check_name,
            f.title,
        ), reverse=rev)
        self.layoutChanged.emit()


class FindingsFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._severity_filter: str = ""
        self._search_text: str = ""

    def set_severity_filter(self, severity: str) -> None:
        self._severity_filter = severity
        self.invalidate()

    def set_search_text(self, text: str) -> None:
        self._search_text = text.lower()
        self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model: FindingsTableModel = self.sourceModel()
        idx = model.index(source_row, 0, source_parent)
        f: Finding | None = model.data(idx, Qt.ItemDataRole.UserRole)
        if f is None:
            return False
        if self._severity_filter and f.severity != self._severity_filter:
            return False
        if self._search_text:
            text = f"{f.severity} {f.check_name} {f.title} {f.location} {f.message}".lower()
            if self._search_text not in text:
                return False
        return True


class ResultTableWidget(QWidget):
    finding_selected = Signal(Finding)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        filter_layout = QHBoxLayout()
        self.severity_combo = QComboBox()
        self.severity_combo.addItems(["All", "error", "warning", "info", "suggestion"])
        self.severity_combo.currentTextChanged.connect(self._on_severity_changed)
        filter_layout.addWidget(QLabel("Severity:"))
        filter_layout.addWidget(self.severity_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search findings...")
        self.search_input.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_input, 1)

        self.count_label = QLabel("")
        filter_layout.addWidget(self.count_label)

        layout.addLayout(filter_layout)

        self.model = FindingsTableModel([])
        self.proxy = FindingsFilterProxy()
        self.proxy.setSourceModel(self.model)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().setVisible(False)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)

        self.detail_panel = QTextEdit()
        self.detail_panel.setReadOnly(True)
        self.detail_panel.setMaximumHeight(120)
        self.detail_panel.setVisible(False)
        layout.addWidget(self.detail_panel)

    def set_findings(self, findings: list[Finding]) -> None:
        self.model = FindingsTableModel(findings)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)
        self._update_count()

    def _on_severity_changed(self, text: str) -> None:
        self.proxy.set_severity_filter("" if text == "All" else text)
        self._update_count()

    def _on_search_changed(self, text: str) -> None:
        self.proxy.set_search_text(text)
        self._update_count()

    def _update_count(self) -> None:
        count = self.proxy.rowCount()
        total = self.model.rowCount()
        self.count_label.setText(f"{count} / {total} findings")

    def _on_selection_changed(self) -> None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            self.detail_panel.setVisible(False)
            return
        idx = self.proxy.mapToSource(indexes[0])
        f: Finding | None = self.model.data(idx, Qt.ItemDataRole.UserRole)
        if f is None:
            self.detail_panel.setVisible(False)
            return
        self.finding_selected.emit(f)
        parts = []
        if f.message:
            parts.append(f.message)
        if f.suggestion:
            parts.append(f"Suggestion: {f.suggestion}")
        if f.location:
            parts.append(f"Location: {f.location}")
        if f.file_path:
            parts.append(f"File: {f.file_path}")
        self.detail_panel.setPlainText("\n".join(parts))
        self.detail_panel.setVisible(True)
