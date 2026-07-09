# SPDX-License-Identifier: GPL-3.0-only
"""Background task execution for long-running operations."""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QRunnable, Signal, QObject, Slot

from alscan.models import ScanResult
from alscan.merge.plan import MergePlan
from alscan.services import (
    scan_project,
    scan_projects_recursive,
    create_snapshot,
    list_snapshots,
    compare_sources,
    create_merge_plan,
    SnapshotInfo,
    ScanError,
    SnapshotError,
    CompareError,
    MergePlanError,
)
from alscan.versioner import DiffResult


@dataclass
class ScanTaskInput:
    path: str
    verbose: bool = False


@dataclass
class BatchScanTaskInput:
    root: str
    verbose: bool = False


@dataclass
class SnapshotTaskInput:
    path: str


@dataclass
class CompareTaskInput:
    path_a: str
    path_b: str


@dataclass
class ThreeWayTaskInput:
    base: str
    ours: str
    theirs: str
    allow_unrelated: bool = False


class WorkerSignals(QObject):
    started = Signal()
    progress = Signal(int, int, str)
    finished = Signal(object)
    error = Signal(str, str)


class ScanWorker(QRunnable):
    def __init__(self, input_data: ScanTaskInput) -> None:
        super().__init__()
        self.input_data = input_data
        self.signals = WorkerSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        self.signals.started.emit()
        try:
            result = scan_project(
                self.input_data.path,
                progress_cb=self.signals.progress.emit,
                cancelled_cb=lambda: self._cancelled,
            )
            self.signals.finished.emit(result)
        except ScanError as e:
            self.signals.error.emit(str(e), traceback.format_exc())
        except Exception as e:
            self.signals.error.emit(str(e), traceback.format_exc())


class BatchScanWorker(QRunnable):
    def __init__(self, input_data: BatchScanTaskInput) -> None:
        super().__init__()
        self.input_data = input_data
        self.signals = WorkerSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        self.signals.started.emit()
        try:
            results = scan_projects_recursive(
                self.input_data.root,
                progress_cb=self.signals.progress.emit,
                cancelled_cb=lambda: self._cancelled,
            )
            self.signals.finished.emit(results)
        except ScanError as e:
            self.signals.error.emit(str(e), traceback.format_exc())
        except Exception as e:
            self.signals.error.emit(str(e), traceback.format_exc())


class SnapshotWorker(QRunnable):
    def __init__(self, input_data: SnapshotTaskInput) -> None:
        super().__init__()
        self.input_data = input_data
        self.signals = WorkerSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        self.signals.started.emit()
        try:
            dest = create_snapshot(self.input_data.path)
            self.signals.finished.emit(dest)
        except SnapshotError as e:
            self.signals.error.emit(str(e), traceback.format_exc())
        except Exception as e:
            self.signals.error.emit(str(e), traceback.format_exc())


class ListSnapshotsWorker(QRunnable):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path
        self.signals = WorkerSignals()

    def run(self) -> None:
        self.signals.started.emit()
        try:
            infos = list_snapshots(self.path)
            self.signals.finished.emit(infos)
        except SnapshotError as e:
            self.signals.error.emit(str(e), traceback.format_exc())
        except Exception as e:
            self.signals.error.emit(str(e), traceback.format_exc())


class CompareWorker(QRunnable):
    def __init__(self, input_data: CompareTaskInput) -> None:
        super().__init__()
        self.input_data = input_data
        self.signals = WorkerSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        self.signals.started.emit()
        try:
            if self._cancelled:
                return
            result = compare_sources(
                self.input_data.path_a,
                self.input_data.path_b,
            )
            if self._cancelled:
                return
            self.signals.finished.emit(result)
        except CompareError as e:
            if not self._cancelled:
                self.signals.error.emit(str(e), traceback.format_exc())
        except Exception as e:
            if not self._cancelled:
                self.signals.error.emit(str(e), traceback.format_exc())


class ThreeWayWorker(QRunnable):
    def __init__(self, input_data: ThreeWayTaskInput) -> None:
        super().__init__()
        self.input_data = input_data
        self.signals = WorkerSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        self.signals.started.emit()
        try:
            plan = create_merge_plan(
                self.input_data.base,
                self.input_data.ours,
                self.input_data.theirs,
                allow_unrelated=self.input_data.allow_unrelated,
            )
            self.signals.finished.emit(plan)
        except MergePlanError as e:
            self.signals.error.emit(str(e), traceback.format_exc())
        except Exception as e:
            self.signals.error.emit(str(e), traceback.format_exc())
