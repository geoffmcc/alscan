# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from alscan.gui.settings import AppSettings
from alscan.models import Finding


@pytest.fixture(scope="session")
def qapp_cls():
    return QApplication


@pytest.fixture(scope="session")
def qapp_args():
    return []


@pytest.fixture
def app_settings(tmp_path):
    s = AppSettings()
    s._settings.clear()
    yield s
    s._settings.clear()


@pytest.fixture
def sample_findings():
    return [
        Finding(
            check_name="missing_wav",
            severity="error",
            title="Missing Audio File",
            message="Kick.wav not found on disk",
            location="Samples/Kick.wav",
        ),
        Finding(
            check_name="low_sample_rate",
            severity="warning",
            title="Low Sample Rate",
            message="Project uses 22050 Hz sample rate",
            location="Project Settings",
        ),
        Finding(
            check_name="invalid_chars",
            severity="info",
            title="Invalid Characters",
            message="Track name contains invalid characters",
            location="Track 1",
        ),
    ]


@pytest.fixture(autouse=True)
def _cleanup_widgets():
    yield
    QApplication.instance().processEvents()
    for w in QApplication.topLevelWidgets():
        w.deleteLater()
    QApplication.instance().processEvents()
