# SPDX-License-Identifier: GPL-3.0-only
"""Application settings page."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QSpinBox, QGroupBox, QFileDialog,
    QLineEdit, QMessageBox,
)
from PySide6.QtCore import Qt

from alscan.gui.settings import AppSettings
from alscan.gui.theme import ThemeMode


class SettingsPage(QWidget):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        heading = QLabel("Settings")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        appearance_group = QGroupBox("Appearance")
        appearance_layout = QVBoxLayout(appearance_group)
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["system", "light", "dark"])
        current = self._settings.theme
        idx = self.theme_combo.findText(current)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        appearance_layout.addLayout(theme_row)
        layout.addWidget(appearance_group)

        scan_group = QGroupBox("Scan Defaults")
        scan_layout = QVBoxLayout(scan_group)
        self.verbose_check = QCheckBox("Verbose output by default")
        self.verbose_check.setChecked(
            self._settings.verbose_scan
        )
        self.verbose_check.toggled.connect(
            lambda v: setattr(self._settings, 'verbose_scan', v)
        )
        scan_layout.addWidget(self.verbose_check)
        layout.addWidget(scan_group)

        output_group = QGroupBox("Reports & Output")
        output_layout = QVBoxLayout(output_group)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Default output directory:"))
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setText(self._settings.default_output_dir)
        self.output_dir_input.setPlaceholderText("Leave empty to use project directory")
        dir_row.addWidget(self.output_dir_input, 1)
        browse_dir_btn = QPushButton("Browse...")
        browse_dir_btn.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(browse_dir_btn)
        output_layout.addLayout(dir_row)

        self.auto_open_check = QCheckBox("Automatically open generated reports")
        self.auto_open_check.setChecked(self._settings.auto_open_reports)
        self.auto_open_check.toggled.connect(
            lambda v: setattr(self._settings, 'auto_open_reports', v)
        )
        output_layout.addWidget(self.auto_open_check)

        self.confirm_overwrite_check = QCheckBox("Confirm before overwriting output files")
        self.confirm_overwrite_check.setChecked(self._settings.confirm_overwrite)
        self.confirm_overwrite_check.toggled.connect(
            lambda v: setattr(self._settings, 'confirm_overwrite', v)
        )
        output_layout.addWidget(self.confirm_overwrite_check)

        max_row = QHBoxLayout()
        max_row.addWidget(QLabel("Maximum recent items:"))
        self.max_recent_spin = QSpinBox()
        self.max_recent_spin.setRange(1, 50)
        self.max_recent_spin.setValue(self._settings.max_recent)
        self.max_recent_spin.valueChanged.connect(
            lambda v: setattr(self._settings, 'max_recent', v)
        )
        max_row.addWidget(self.max_recent_spin)
        max_row.addStretch()
        output_layout.addLayout(max_row)
        layout.addWidget(output_group)

        layout.addStretch()

        reset_btn = QPushButton("Reset All Settings")
        reset_btn.setObjectName("dangerButton")
        reset_btn.clicked.connect(self._reset_settings)
        layout.addWidget(reset_btn)

    def _on_theme_changed(self, value: str) -> None:
        self._settings.theme = value
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            from alscan.gui.theme import apply_theme
            apply_theme(app, value)

    def _browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.output_dir_input.setText(path)
            self._settings.default_output_dir = path

    def _reset_settings(self) -> None:
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Are you sure you want to reset all settings to defaults?\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._settings.reset()
            self.theme_combo.setCurrentIndex(0)
            self.verbose_check.setChecked(False)
            self.output_dir_input.setText("")
            self.auto_open_check.setChecked(True)
            self.confirm_overwrite_check.setChecked(True)
            self.max_recent_spin.setValue(10)
            QMessageBox.information(
                self, "Reset Complete",
                "Settings have been reset to defaults."
            )
