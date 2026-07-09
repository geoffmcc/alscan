# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from alscan.gui.workers import (
    ScanWorker, ScanTaskInput,
    BatchScanWorker, BatchScanTaskInput,
    SnapshotWorker, SnapshotTaskInput,
    ListSnapshotsWorker,
    CompareWorker, CompareTaskInput,
    ThreeWayWorker, ThreeWayTaskInput,
    WorkerSignals,
)


class TestScanWorker:
    def test_create(self):
        worker = ScanWorker(ScanTaskInput(path="/nonexistent.als"))
        assert worker.input_data.path == "/nonexistent.als"
        assert worker._cancelled is False
        assert isinstance(worker.signals, WorkerSignals)

    def test_cancel(self):
        worker = ScanWorker(ScanTaskInput(path="/test.als"))
        worker.cancel()
        assert worker._cancelled is True

    def test_cancelled_cb_returns_false(self):
        worker = ScanWorker(ScanTaskInput(path="/test.als"))
        assert worker._cancelled is False


class TestBatchScanWorker:
    def test_create(self):
        worker = BatchScanWorker(BatchScanTaskInput(root="/nonexistent"))
        assert worker.input_data.root == "/nonexistent"

    def test_cancel(self):
        worker = BatchScanWorker(BatchScanTaskInput(root="/test"))
        worker.cancel()
        assert worker._cancelled is True


class TestSnapshotWorker:
    def test_create(self):
        worker = SnapshotWorker(SnapshotTaskInput(path="/test.als"))
        assert worker.input_data.path == "/test.als"

    def test_cancel(self):
        worker = SnapshotWorker(SnapshotTaskInput(path="/test.als"))
        worker.cancel()
        assert worker._cancelled is True


class TestListSnapshotsWorker:
    def test_create(self):
        worker = ListSnapshotsWorker(path="/snapshots")
        assert worker.path == "/snapshots"


class TestCompareWorker:
    def test_create(self):
        worker = CompareWorker(CompareTaskInput(path_a="/a.als", path_b="/b.als"))
        assert worker.input_data.path_a == "/a.als"
        assert worker.input_data.path_b == "/b.als"


class TestThreeWayWorker:
    def test_create(self):
        worker = ThreeWayWorker(
            ThreeWayTaskInput(base="/base.als", ours="/ours.als", theirs="/theirs.als")
        )
        assert worker.input_data.base == "/base.als"
        assert worker.input_data.allow_unrelated is False

    def test_allow_unrelated(self):
        worker = ThreeWayWorker(
            ThreeWayTaskInput(base="/b.als", ours="/o.als", theirs="/t.als", allow_unrelated=True)
        )
        assert worker.input_data.allow_unrelated is True

    def test_cancel(self):
        worker = ThreeWayWorker(
            ThreeWayTaskInput(base="/b.als", ours="/o.als", theirs="/t.als")
        )
        worker.cancel()
        assert worker._cancelled is True
