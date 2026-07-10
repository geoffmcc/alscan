# SPDX-License-Identifier: GPL-3.0-only
"""Guided Merge wizard page — multi-stage guided merge workflow."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QStackedWidget, QFrame,
    QProgressBar, QMessageBox, QCheckBox, QGroupBox,
    QListWidget, QListWidgetItem, QScrollArea, QSizePolicy,
    QTextEdit, QSplitter,
)
from PySide6.QtCore import Qt, QThreadPool, Signal, Slot, QObject

from alscan.gui.workers import WorkerSignals
from alscan.merge.guided import create_merge_session, build_merge_operations, GuidedMergeError
from alscan.merge.manifest import MergeManifest
from alscan.merge.verification import verify_destination, VerificationReport
from alscan.merge.plan import MergePlan
from alscan.merge.session import MergeSession, FoundationRecommendation
from alscan.merge.operation import MergeOperation, OperationState, ExecutionMode
from alscan.io_safety import capture_identity, are_same_file


class GuidedMergeWorker(WorkerSignals, QObject):
    """Signals-only wrapper for use as QObject in worker pattern."""

    finished = Signal(object)
    error = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)


class GuidedMergePage(QWidget):
    """Multi-stage guided merge wizard."""

    _stage_titles = [
        "Select Sets", "Analyze", "Choose Foundation",
        "Review Decisions", "Prepare Destination", "Perform Merge",
        "Collect and Save", "Verify", "Completion",
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session: MergeSession | None = None
        self._plan: MergePlan | None = None
        self._operations: list[MergeOperation] = []
        self._manifest: MergeManifest | None = None
        self._manifest_path: Path | None = None
        self._dirty: bool = False
        self._pool = QThreadPool.globalInstance()
        self._current_op_index: int = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        top_bar = QHBoxLayout()
        heading = QLabel("Guided Merge")
        heading.setObjectName("heading")
        top_bar.addWidget(heading)
        top_bar.addStretch()

        self._save_btn = QPushButton("Save Session")
        self._save_btn.setToolTip("Save the current merge session to a manifest file.")
        self._save_btn.clicked.connect(self._save_session)
        self._save_btn.setEnabled(False)
        top_bar.addWidget(self._save_btn)

        self._save_as_btn = QPushButton("Save Session As...")
        self._save_as_btn.setToolTip("Save the session to a new manifest file.")
        self._save_as_btn.clicked.connect(self._save_session_as)
        self._save_as_btn.setEnabled(False)
        top_bar.addWidget(self._save_as_btn)

        self._open_btn = QPushButton("Open Session...")
        self._open_btn.setToolTip("Open a previously saved merge session.")
        self._open_btn.clicked.connect(self._open_session)
        top_bar.addWidget(self._open_btn)
        layout.addLayout(top_bar)

        self.info_label = QLabel(
            "A safe, step-by-step workflow for merging changes from two "
            "divergent versions of an Ableton Live Set. ALScan analyzes "
            "the differences, recommends the best starting point, and "
            "guides you through each manual change. No source file is "
            "ever modified."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setObjectName("subheading")
        layout.addWidget(self.info_label)

        self._status_label_global = QLabel("")
        self._status_label_global.setObjectName("subheading")
        layout.addWidget(self._status_label_global)

        stage_nav = QHBoxLayout()
        self._stage_labels: list[QLabel] = []
        for i, title in enumerate(self._stage_titles):
            lbl = QLabel(f"{i + 1}. {title}")
            lbl.setObjectName("subheading")
            lbl.setStyleSheet("padding: 4px 8px;")
            stage_nav.addWidget(lbl)
            self._stage_labels.append(lbl)
            if i < len(self._stage_titles) - 1:
                stage_nav.addWidget(QLabel(">"))
        stage_nav.addStretch()
        layout.addLayout(stage_nav)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.stage_stack = QStackedWidget()
        layout.addWidget(self.stage_stack, 1)

        self._stage_0_select_sets = self._build_select_sets()
        self._stage_1_analyze = self._build_analyze()
        self._stage_2_foundation = self._build_foundation()
        self._stage_3_decisions = self._build_decisions()
        self._stage_4_destination = self._build_destination()
        self._stage_5_perform = self._build_perform()
        self._stage_6_collect = self._build_collect()
        self._stage_7_verify = self._build_verify()
        self._stage_8_completion = self._build_completion()

        for w in [
            self._stage_0_select_sets, self._stage_1_analyze,
            self._stage_2_foundation, self._stage_3_decisions,
            self._stage_4_destination, self._stage_5_perform,
            self._stage_6_collect, self._stage_7_verify,
            self._stage_8_completion,
        ]:
            self.stage_stack.addWidget(w)

        self._update_stage_highlight(0)

    def _update_stage_highlight(self, current: int) -> None:
        for i, lbl in enumerate(self._stage_labels):
            if i == current:
                lbl.setStyleSheet("padding: 4px 8px; font-weight: bold; color: #cba6f7;")
            elif i < current:
                lbl.setStyleSheet("padding: 4px 8px; color: #a6adc8;")
            else:
                lbl.setStyleSheet("padding: 4px 8px; color: #6c7086;")

    def _navigate_stage(self, index: int) -> None:
        self.stage_stack.setCurrentIndex(index)
        self._update_stage_highlight(index)

    # ── Stage 0: Select Sets ──────────────────────────────────────────

    def _build_select_sets(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel("Select the three versions of your Ableton Live Set:"))

        self._base_input = self._make_file_row("Base (common ancestor):", "The version you both started from.")
        layout.addWidget(self._base_input)

        layout.addSpacing(8)

        self._ours_input = self._make_file_row("Ours (your version):", "Your version or one collaborator's version.")
        layout.addWidget(self._ours_input)

        layout.addSpacing(8)

        self._theirs_input = self._make_file_row("Theirs (other version):", "The other collaborator's version.")
        layout.addWidget(self._theirs_input)

        layout.addSpacing(12)

        opts = QHBoxLayout()
        self._allow_unrelated_cb = QCheckBox("Allow unrelated projects")
        self._allow_unrelated_cb.setToolTip("Analyze projects that may not share common ancestry.")
        opts.addWidget(self._allow_unrelated_cb)

        self._allow_plausible_cb = QCheckBox("Allow plausible identity matching")
        self._allow_plausible_cb.setToolTip("Match tracks by structural evidence when track IDs differ.")
        opts.addWidget(self._allow_plausible_cb)
        opts.addStretch()
        layout.addLayout(opts)

        layout.addSpacing(12)

        btn_layout = QHBoxLayout()
        self._analyze_btn = QPushButton("Analyze Versions")
        self._analyze_btn.setObjectName("primaryButton")
        self._analyze_btn.clicked.connect(self._on_analyze)
        btn_layout.addWidget(self._analyze_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        return w

    def _make_file_row(self, label: str, tooltip: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setMinimumWidth(180)
        layout.addWidget(lbl)
        edit = QLineEdit()
        edit.setPlaceholderText("Select .als file...")
        layout.addWidget(edit, 1)
        btn = QPushButton("Browse...")
        btn.setToolTip(tooltip)
        btn.clicked.connect(lambda: self._browse_als(edit))
        layout.addWidget(btn)
        return row

    def _browse_als(self, target: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Ableton Live Set",
            "", "Ableton Live Set (*.als);;Snapshot JSON (*.json);;All Files (*)"
        )
        if path:
            target.setText(path)

    def _get_base_input(self) -> QLineEdit:
        return self._base_input.findChild(QLineEdit)

    def _get_ours_input(self) -> QLineEdit:
        return self._ours_input.findChild(QLineEdit)

    def _get_theirs_input(self) -> QLineEdit:
        return self._theirs_input.findChild(QLineEdit)

    def _on_analyze(self) -> None:
        base = self._get_base_input().text().strip()
        ours = self._get_ours_input().text().strip()
        theirs = self._get_theirs_input().text().strip()

        if not base or not ours or not theirs:
            QMessageBox.warning(self, "Input Error", "All three file paths are required.")
            return
        for label, p in [("Base", base), ("Ours", ours), ("Theirs", theirs)]:
            if not Path(p).exists():
                QMessageBox.warning(self, "Input Error", f"{label} file not found:\n{p}")
                return

        self._navigate_stage(1)
        self._status_1.setText("Analyzing...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)

        self._analyze_worker = GuidedMergeWorker(self)
        self._analyze_worker.finished.connect(self._on_analysis_done)
        self._analyze_worker.error.connect(self._on_analysis_error)

        from PySide6.QtCore import QRunnable
        class AnalyzeTask(QRunnable):
            def __init__(s, parent, b, o, t, allow_u, allow_p):
                super().__init__()
                s._parent = parent
                s.b, s.o, s.t = b, o, t
                s.allow_u, s.allow_p = allow_u, allow_p
            def run(s):
                try:
                    session, plan = create_merge_session(
                        s.b, s.o, s.t,
                        allow_unrelated=s.allow_u,
                        allow_plausible=s.allow_p,
                    )
                    s._parent.finished.emit((session, plan))
                except Exception as e:
                    import traceback
                    s._parent.error.emit(str(e), traceback.format_exc())

        task = AnalyzeTask(
            self._analyze_worker, base, ours, theirs,
            self._allow_unrelated_cb.isChecked(),
            self._allow_plausible_cb.isChecked(),
        )
        self._pool.start(task)

    def _on_analysis_done(self, result: tuple) -> None:
        self._session, self._plan = result
        self.progress_bar.setVisible(False)
        self._save_btn.setEnabled(True)
        self._save_as_btn.setEnabled(True)
        self._mark_dirty()
        self._populate_results()

    def _on_analysis_error(self, message: str, details: str) -> None:
        self.progress_bar.setVisible(False)
        QMessageBox.warning(self, "Analysis Error", f"{message}\n\n{details}")

    # ── Stage 1: Analyze ──────────────────────────────────────────────

    def _build_analyze(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self._status_1 = QLabel("Ready to analyze.")
        self._status_1.setWordWrap(True)
        layout.addWidget(self._status_1)
        self._results_1 = QTextEdit()
        self._results_1.setReadOnly(True)
        self._results_1.setMaximumHeight(300)
        layout.addWidget(self._results_1)
        btn_layout = QHBoxLayout()
        self._continue_1 = QPushButton("Review Foundation")
        self._continue_1.clicked.connect(lambda: self._navigate_stage(2))
        self._continue_1.setEnabled(False)
        btn_layout.addWidget(self._continue_1)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()
        return w

    def _populate_results(self) -> None:
        plan = self._plan
        session = self._session
        if not plan or not session:
            return

        preflight = session.safety_preflight
        parts = []
        parts.append("=== Analysis Results ===\n")
        parts.append(f"Lineage confidence: {plan.lineage_confidence}")
        parts.append(f"Conflicts: {plan.conflict_count}")
        parts.append(f"Reconcilable changes: {len(plan.auto_resolved)}")
        parts.append(f"Track changes: {len(plan.track_changes)}")
        parts.append(f"Locator changes: {len(plan.locator_changes)}")
        parts.append(f"Warnings: {plan.warning_count}")
        parts.append(f"Input mode: {plan.input_mode}")
        parts.append("")

        if preflight:
            parts.append("--- Safety Preflight ---")
            parts.append(f"Path collisions: {'None' if preflight.path_collision_check else 'DETECTED'}")
            parts.append(f"Version check: {'Passed' if preflight.version_check else 'Failed'}")
            for w in preflight.warnings:
                parts.append(f"  Warning: {w}")
            for d in preflight.version_details:
                parts.append(f"  Version: {d}")

        for w in plan.warnings:
            parts.append(f"Warning: {w}")

        self._results_1.setText("\n".join(parts))
        self._continue_1.setEnabled(True)
        self._status_1.setText("Analysis complete. Review the results above, then continue.")

    # ── Stage 2: Choose Foundation ────────────────────────────────────

    def _build_foundation(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Select which Set to use as the foundation for your merged result:"))
        self._foundation_list = QListWidget()
        self._foundation_list.setMinimumHeight(150)
        layout.addWidget(self._foundation_list)
        self._foundation_explanation = QLabel("")
        self._foundation_explanation.setWordWrap(True)
        layout.addWidget(self._foundation_explanation)

        btn_layout = QHBoxLayout()
        self._select_foundation_btn = QPushButton("Continue with Selected")
        self._select_foundation_btn.clicked.connect(self._on_select_foundation)
        self._select_foundation_btn.setEnabled(False)
        btn_layout.addWidget(self._select_foundation_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()
        return w

    def _on_stage_2_shown(self) -> None:
        self._foundation_list.clear()
        session = self._session
        rec = session.foundation_recommendation if session else None
        if not rec:
            return

        for key, comp in rec.comparisons.items():
            star = " (recommended)" if key == rec.recommended else ""
            label = comp.get("label", key)
            text = (
                f"{label}{star} — "
                f"Actions: {comp.get('estimated_manual_actions', '?')}, "
                f"Conflicts: {comp.get('conflicts', '?')}, "
                f"Risk: {comp.get('risk_level', '?')}, "
                f"Penalty: {comp.get('penalty_score', '?')}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, key)
            if key == rec.recommended:
                item.setSelected(True)
            self._foundation_list.addItem(item)

        self._foundation_explanation.setText(rec.explanation)
        self._select_foundation_btn.setEnabled(True)

    def _on_select_foundation(self) -> None:
        item = self._foundation_list.currentItem()
        if not item:
            return
        selected = item.data(Qt.ItemDataRole.UserRole)
        if self._session:
            self._session.selected_foundation = selected
        self._mark_dirty()
        self._populate_decisions()
        self._navigate_stage(3)

    # ── Stage 3: Review Decisions ─────────────────────────────────────

    def _build_decisions(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Review and decide on each operation in the merge plan:"))
        self._decision_list = QListWidget()
        self._decision_list.setMinimumHeight(200)
        self._decision_list.setWordWrap(True)
        layout.addWidget(self._decision_list)

        detail_group = QGroupBox("Operation Details")
        detail_layout = QVBoxLayout(detail_group)
        self._decision_detail = QTextEdit()
        self._decision_detail.setReadOnly(True)
        self._decision_detail.setMaximumHeight(150)
        detail_layout.addWidget(self._decision_detail)
        layout.addWidget(detail_group)

        btn_layout = QHBoxLayout()
        self._accept_btn = QPushButton("Accept Recommendation")
        self._accept_btn.clicked.connect(lambda: self._decide("accept"))
        btn_layout.addWidget(self._accept_btn)
        self._skip_btn = QPushButton("Skip")
        self._skip_btn.clicked.connect(lambda: self._decide("skip"))
        btn_layout.addWidget(self._skip_btn)
        self._defer_btn = QPushButton("Decide Later")
        self._defer_btn.clicked.connect(lambda: self._decide("defer"))
        btn_layout.addWidget(self._defer_btn)
        btn_layout.addStretch()

        self._continue_3 = QPushButton("Continue to Destination")
        self._continue_3.clicked.connect(lambda: self._navigate_stage(4))
        btn_layout.addWidget(self._continue_3)
        layout.addLayout(btn_layout)
        layout.addStretch()
        return w

    def _populate_decisions(self) -> None:
        if not self._session or not self._plan:
            return
        foundation = self._session.selected_foundation or "ours"
        self._operations = build_merge_operations(
            self._session, self._plan, foundation
        )
        self._decision_list.clear()
        for op in self._operations:
            state = op.state
            prefix = {
                OperationState.ACCEPTED: "[OK] ",
                OperationState.AWAITING_DECISION: "[?]  ",
                OperationState.COMPLETED_MANUAL: "[DONE] ",
            }.get(state, "[ ]  ")
            item = QListWidgetItem(f"{prefix}{op.title}")
            item.setData(Qt.ItemDataRole.UserRole, op.operation_id)
            if op.required_user_decision:
                item.setForeground(Qt.GlobalColor.yellow)
            self._decision_list.addItem(item)
        self._decision_list.currentRowChanged.connect(self._show_decision_detail)

    def _show_decision_detail(self, row: int) -> None:
        if row < 0 or row >= len(self._operations):
            return
        op = self._operations[row]
        parts = [
            f"Operation: {op.title}",
            f"ID: {op.operation_id}",
            f"Category: {op.category.value if hasattr(op.category, 'value') else op.category}",
            f"State: {op.state.value if hasattr(op.state, 'value') else op.state}",
            f"Risk: {op.risk_level.value if hasattr(op.risk_level, 'value') else op.risk_level}",
            f"Support: {op.support_classification.value if hasattr(op.support_classification, 'value') else op.support_classification}",
            f"Description: {op.description}",
        ]
        if op.base_value is not None:
            parts.append(f"Base value: {op.base_value}")
        if op.ours_value is not None:
            parts.append(f"Ours value: {op.ours_value}")
        if op.theirs_value is not None:
            parts.append(f"Theirs value: {op.theirs_value}")
        if op.recommended_result is not None:
            parts.append(f"Recommended: {op.recommended_result}")
        if op.recommendation_rationale:
            parts.append(f"Rationale: {op.recommendation_rationale}")
        self._decision_detail.setText("\n".join(parts))

        has_decision = op.required_user_decision and op.state not in {OperationState.ACCEPTED, OperationState.REJECTED}
        self._accept_btn.setVisible(has_decision)
        self._skip_btn.setVisible(has_decision)
        self._defer_btn.setVisible(has_decision)

    def _decide(self, choice: str) -> None:
        row = self._decision_list.currentRow()
        if row < 0 or row >= len(self._operations):
            return
        op = self._operations[row]
        try:
            if choice == "accept":
                op.transition_to(OperationState.ACCEPTED)
            elif choice == "skip":
                op.transition_to(OperationState.REJECTED)
            elif choice == "defer":
                op.transition_to(OperationState.DEFERRED)
        except ValueError:
            pass
        self._mark_dirty()
        self._populate_decisions()
        if row < self._decision_list.count():
            self._decision_list.setCurrentRow(row)

    # ── Stage 4: Prepare Destination ──────────────────────────────────

    def _build_destination(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Prepare your destination Set:"))
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setMaximumHeight(200)
        instructions.setText(
            "1. Open the selected foundation Set in Ableton Live.\n"
            "2. Choose File > Save Live Set As...\n"
            "3. Save to a NEW Project folder, separate from all source folders.\n"
            "4. Choose a filename that makes it clear this is the merge destination.\n"
            "5. Return to ALScan and select the saved .als file below.\n\n"
            "ALScan will verify that the destination:\n"
            "- Exists and is readable\n"
            "- Is not the same file as Base, Ours, or Theirs\n"
            "- Is not inside any source Project folder"
        )
        layout.addWidget(instructions)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Destination .als:"))
        self._dest_input = QLineEdit()
        self._dest_input.setPlaceholderText("Select destination .als...")
        dest_row.addWidget(self._dest_input, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(lambda: self._browse_als(self._dest_input))
        dest_row.addWidget(browse_btn)
        layout.addLayout(dest_row)

        self._dest_status = QLabel("")
        self._dest_status.setWordWrap(True)
        layout.addWidget(self._dest_status)

        btn_layout = QHBoxLayout()
        self._validate_dest_btn = QPushButton("Validate Destination")
        self._validate_dest_btn.clicked.connect(self._validate_destination)
        btn_layout.addWidget(self._validate_dest_btn)

        self._continue_4 = QPushButton("Begin Merge")
        self._continue_4.clicked.connect(self._start_perform)
        self._continue_4.setEnabled(False)
        btn_layout.addWidget(self._continue_4)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()
        return w

    def _validate_destination(self) -> None:
        dest = self._dest_input.text().strip()
        if not dest:
            self._dest_status.setText("Error: No destination path selected.")
            return
        dp = Path(dest)
        if not dp.exists():
            self._dest_status.setText("Error: Destination file does not exist.")
            return
        if not dp.suffix.lower() == ".als":
            self._dest_status.setText("Error: Destination must be an .als file.")
            return

        sources = {
            "base": self._get_base_input().text().strip(),
            "ours": self._get_ours_input().text().strip(),
            "theirs": self._get_theirs_input().text().strip(),
        }
        collisions = []
        for role, sp in sources.items():
            if dp == Path(sp).resolve():
                collisions.append(role)
        if collisions:
            self._dest_status.setText(
                f"Error: Destination is the same file as: {', '.join(collisions)}"
            )
            return

        self._dest_status.setText(
            "Destination validated. Source hashes verified, no path collisions detected."
        )
        if self._session:
            self._session.destination_path = str(dp)
        self._continue_4.setEnabled(True)

    # ── Stage 5: Perform Merge ────────────────────────────────────────

    def _build_perform(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self._perform_title = QLabel("")
        self._perform_title.setWordWrap(True)
        self._perform_title.setObjectName("heading")
        layout.addWidget(self._perform_title)

        self._perform_instructions = QTextEdit()
        self._perform_instructions.setReadOnly(True)
        self._perform_instructions.setMinimumHeight(120)
        layout.addWidget(self._perform_instructions)

        self._perform_status = QLabel("")
        layout.addWidget(self._perform_status)

        btn_layout = QHBoxLayout()
        self._mark_complete_btn = QPushButton("Mark Complete")
        self._mark_complete_btn.clicked.connect(self._mark_current_complete)
        btn_layout.addWidget(self._mark_complete_btn)
        self._skip_op_btn = QPushButton("Skip")
        self._skip_op_btn.clicked.connect(self._skip_current_op)
        btn_layout.addWidget(self._skip_op_btn)
        self._defer_op_btn = QPushButton("Defer")
        self._defer_op_btn.clicked.connect(self._defer_current_op)
        btn_layout.addWidget(self._defer_op_btn)
        btn_layout.addStretch()

        self._continue_5 = QPushButton("Continue to Collect and Save")
        self._continue_5.clicked.connect(lambda: self._navigate_stage(6))
        btn_layout.addWidget(self._continue_5)
        layout.addLayout(btn_layout)
        layout.addStretch()
        return w

    def _start_perform(self) -> None:
        self._current_op_index = 0
        self._navigate_stage(5)
        self._show_current_op()

    def _show_current_op(self) -> None:
        active = [
            op for op in self._operations
            if op.state not in {
                OperationState.REJECTED, OperationState.DEFERRED,
            }
        ]
        if self._current_op_index >= len(active):
            self._perform_title.setText("All operations handled.")
            self._perform_instructions.setText(
                "You have reviewed all operations. Click 'Continue to Collect and Save' to proceed."
            )
            self._mark_complete_btn.setEnabled(False)
            self._skip_op_btn.setEnabled(False)
            self._defer_op_btn.setEnabled(False)
            return

        op = active[self._current_op_index]
        self._perform_title.setText(f"Step {self._current_op_index + 1}: {op.title}")
        text = op.description + "\n\n"
        if op.instructions:
            text += f"Instructions: {op.instructions.description}\n\n"
            for w in op.instructions.warnings:
                text += f"Warning: {w}\n"
        self._perform_instructions.setText(text)

        state_info = op.state.value if hasattr(op.state, 'value') else str(op.state)
        self._perform_status.setText(f"Status: {state_info} | Mode: manual only")

        self._mark_complete_btn.setEnabled(True)
        self._skip_op_btn.setEnabled(True)
        self._defer_op_btn.setEnabled(True)

    def _mark_current_complete(self) -> None:
        active = [
            op for op in self._operations
            if op.state not in {
                OperationState.REJECTED, OperationState.DEFERRED,
            }
        ]
        if self._current_op_index < len(active):
            op = active[self._current_op_index]
            try:
                if op.state == OperationState.ACCEPTED:
                    op.transition_to(OperationState.READY)
                if op.state == OperationState.READY:
                    op.transition_to(OperationState.IN_PROGRESS)
                if op.state == OperationState.IN_PROGRESS:
                    op.transition_to(OperationState.COMPLETED_MANUAL)
            except ValueError:
                pass
        self._current_op_index += 1
        self._show_current_op()

    def _skip_current_op(self) -> None:
        active = [
            op for op in self._operations
            if op.state not in {
                OperationState.REJECTED, OperationState.DEFERRED,
            }
        ]
        if self._current_op_index < len(active):
            try:
                active[self._current_op_index].transition_to(OperationState.REJECTED)
            except ValueError:
                pass
        self._current_op_index += 1
        self._show_current_op()

    def _defer_current_op(self) -> None:
        active = [
            op for op in self._operations
            if op.state not in {
                OperationState.REJECTED, OperationState.DEFERRED,
            }
        ]
        if self._current_op_index < len(active):
            try:
                active[self._current_op_index].transition_to(OperationState.DEFERRED)
            except ValueError:
                pass
        self._current_op_index += 1
        self._show_current_op()

    # ── Stage 6: Collect and Save ─────────────────────────────────────

    def _build_collect(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Finalize the destination Set:"))
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setMinimumHeight(200)
        instructions.setText(
            "In Ableton Live:\n\n"
            "1. Select File > Collect All and Save\n"
            "   This copies all referenced samples and media into the destination Project.\n\n"
            "2. Wait for the collection to complete.\n"
            "   Large libraries or multisample content may take time.\n\n"
            "3. Save the Set (Ctrl+S / Cmd+S).\n\n"
            "4. Close the Set.\n\n"
            "5. Reopen the Set to verify it loads correctly.\n\n"
            "Caution: Max for Live devices may reference external files "
            "not captured by Collect All and Save."
        )
        layout.addWidget(instructions)
        self._collect_ack = QCheckBox("I have completed Collect All and Save in Ableton Live")
        layout.addWidget(self._collect_ack)

        btn_layout = QHBoxLayout()
        self._continue_6 = QPushButton("Run Verification")
        self._continue_6.clicked.connect(self._run_verification)
        btn_layout.addWidget(self._continue_6)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()
        return w

    # ── Stage 7: Verify ───────────────────────────────────────────────

    def _build_verify(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Verification Results:"))
        self._verify_results = QTextEdit()
        self._verify_results.setReadOnly(True)
        layout.addWidget(self._verify_results, 1)

        btn_layout = QHBoxLayout()
        self._reverify_btn = QPushButton("Re-verify")
        self._reverify_btn.clicked.connect(self._run_verification)
        btn_layout.addWidget(self._reverify_btn)

        self._continue_7 = QPushButton("View Completion")
        self._continue_7.clicked.connect(self._show_completion)
        self._continue_7.setEnabled(False)
        btn_layout.addWidget(self._continue_7)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        return w

    def _run_verification(self) -> None:
        if not self._collect_ack.isChecked():
            QMessageBox.warning(self, "Confirmation Required",
                                "Please confirm you have completed Collect All and Save in Ableton Live.")
            return

        self._navigate_stage(7)
        dest = self._dest_input.text().strip()
        if not dest or not Path(dest).exists():
            self._verify_results.setText("Error: Destination file not found. Please return to the 'Prepare Destination' stage.")
            return

        if not self._operations:
            if self._session and self._plan:
                foundation = self._session.selected_foundation or "ours"
                self._operations = build_merge_operations(self._session, self._plan, foundation)

        manifest = MergeManifest.create(self._session or MergeSession(), self._operations)
        source_paths = {
            r: str(Path(self._get_base_input() if r == "base" else self._get_ours_input() if r == "ours" else self._get_theirs_input()).text().strip())
            for r in ("base", "ours", "theirs")
        }
        hashes = {}
        if self._session:
            hashes = {
                r: self._session.sources[r].sha256
                for r in ("base", "ours", "theirs")
                if r in self._session.sources and self._session.sources[r]
            }
        manifest.source_hashes_captured = hashes

        report = verify_destination(dest, manifest, source_paths, hashes)

        self._manifest = manifest
        parts = [
            "=== Verification Report ===",
            f"Passed: {report.passed}",
            f"Failed: {report.failed}",
            f"Partial: {report.partial}",
            f"Unverifiable: {report.unverifiable}",
            f"Blocked: {report.blocked}",
            f"Source hashes stable: {'YES' if report.source_hashes_stable else 'NO — DO NOT TRUST RESULT'}",
            "",
        ]
        for detail in report.source_hash_details:
            parts.append(f"  {detail.get('role')}: {detail.get('status')}")
        for error in report.errors:
            parts.append(f"Error: {error}")
        self._verify_results.setText("\n".join(parts))
        self._continue_7.setEnabled(True)

    # ── Stage 8: Completion ───────────────────────────────────────────

    def _build_completion(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Guided Merge Complete"))
        self._completion_text = QTextEdit()
        self._completion_text.setReadOnly(True)
        layout.addWidget(self._completion_text, 1)

        btn_layout = QHBoxLayout()
        self._save_manifest_btn = QPushButton("Save Manifest")
        self._save_manifest_btn.clicked.connect(self._save_session_as)
        btn_layout.addWidget(self._save_manifest_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()
        return w

    def _show_completion(self) -> None:
        self._navigate_stage(8)
        session = self._session
        parts = [
            "=== Guided Merge Complete ===\n",
            f"Session: {session.session_id if session else 'N/A'}",
            f"Foundation: {session.selected_foundation if session else 'N/A'}",
            f"Destination: {session.destination_path if session else 'N/A'}",
        ]
        if self._operations:
            completed = sum(1 for o in self._operations if o.is_completed() or o.is_verified())
            parts.append(f"Completed operations: {completed}/{len(self._operations)}")
        parts.append("\nWhat's next:")
        parts.append("- Open the destination in Ableton Live and verify contents.")
        parts.append("- Keep your source Sets until you've fully validated the result.")
        parts.append("- Save the manifest for future reference.")
        self._completion_text.setText("\n".join(parts))

    def _save_manifest_to(self, path: Path) -> bool:
        if not self._session:
            return False
        manifest = MergeManifest.create(self._session, self._operations)
        hashes = {}
        for r in ("base", "ours", "theirs"):
            if r in self._session.sources and self._session.sources[r]:
                hashes[r] = self._session.sources[r].sha256
        manifest.source_hashes_captured = hashes
        self._manifest = manifest
        try:
            from alscan.io_safety import atomic_write, validate_output_dest
            validate_output_dest(path, [
                Path(self._get_base_input().text().strip()) if self._get_base_input().text().strip() else Path("."),
                Path(self._get_ours_input().text().strip()) if self._get_ours_input().text().strip() else Path("."),
                Path(self._get_theirs_input().text().strip()) if self._get_theirs_input().text().strip() else Path("."),
            ], reject_ableton_exts=True, reject_backup=True, reject_alscan=True)
            atomic_write(path, manifest.to_json())
            self._manifest_path = path
            self._dirty = False
            return True
        except (ValueError, FileExistsError) as e:
            QMessageBox.warning(self, "Save Error", str(e))
            return False
        except OSError as e:
            QMessageBox.warning(self, "Save Error", f"Could not write: {e}")
            return False

    def _save_session(self) -> None:
        if not self._session:
            return
        if self._manifest_path and not self._dirty:
            return
        if self._manifest_path:
            if self._save_manifest_to(self._manifest_path):
                self._set_status("Session saved.")
        else:
            self._save_session_as()

    def _save_session_as(self) -> None:
        if not self._session:
            return
        suggested = "merge-session.json"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Merge Session", suggested, "JSON (*.json);;All Files (*)"
        )
        if not path_str:
            return
        if self._save_manifest_to(Path(path_str)):
            self._set_status(f"Session saved to: {path_str}")

    def _open_session(self) -> None:
        if self._dirty and self._session:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Open a new session without saving?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open Merge Session", "", "JSON (*.json);;All Files (*)"
        )
        if not path_str:
            return
        self._resume_from_path(Path(path_str))

    def _resume_from_path(self, path: Path) -> None:
        try:
            raw = path.read_text(encoding="utf-8")
            manifest = MergeManifest.from_json(raw)
        except (ValueError, json.JSONDecodeError) as e:
            QMessageBox.warning(self, "Invalid Manifest", f"Cannot read manifest:\n{e}")
            return

        import json as _json
        session = manifest.get_session()
        operations = manifest.get_operations()

        changed = []
        for role in ("base", "ours", "theirs"):
            if role not in session.sources:
                continue
            src = session.sources[role]
            sp = Path(src.path) if hasattr(src, 'path') else Path(src.get("path", ""))
            if not sp or not sp.exists():
                changed.append(f"{role}: file missing ({sp})")
                continue
            try:
                ident = capture_identity(sp)
                expected = manifest.source_hashes_captured.get(role, "")
                if expected and ident.sha256 != expected:
                    changed.append(
                        f"{role}: hash changed (expected {expected[:12]}..., "
                        f"observed {ident.sha256[:12]}...)"
                    )
            except Exception:
                changed.append(f"{role}: unreadable")

        if changed:
            msg = "Source files have changed since this session was saved:\n\n"
            msg += "\n".join(f"  - {c}" for c in changed)
            msg += "\n\nThe session cannot be safely resumed with changed sources."
            reply = QMessageBox.warning(
                self, "Changed Sources Detected", msg,
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Abort,
            )
            return

        self._session = session
        self._manifest = manifest
        self._manifest_path = path
        self._dirty = False
        self._operations = operations
        self._current_op_index = 0

        # Restore inputs
        for role, input_field in [
            ("base", self._get_base_input()), ("ours", self._get_ours_input()), ("theirs", self._get_theirs_input())
        ]:
            if role in session.sources:
                src = session.sources[role]
                p = src.path if hasattr(src, 'path') else src.get("path", "")
                input_field.setText(p)

        if session.destination_path:
            self._dest_input.setText(session.destination_path)

        # Determine stage
        state = session.workflow_state
        stage_map = {
            "preflight": 0, "analyzing": 1, "choosing_foundation": 2,
            "reviewing_decisions": 3, "preparing_destination": 4,
            "performing_merge": 5, "collect_and_save": 6,
            "verifying": 7, "completed": 8,
        }
        target = stage_map.get(state, 0)
        if target >= 1:
            self._populate_results()
        if target >= 2:
            self._on_stage_2_shown()
        if target >= 3:
            self._populate_decisions()
        self._navigate_stage(target)

        self._set_status(f"Session resumed from: {path.name}")
        self._save_btn.setEnabled(True)
        self._save_as_btn.setEnabled(True)

    def _set_status(self, text: str) -> None:
        self._status_label_global.setText(text)

    def _mark_dirty(self) -> None:
        self._dirty = True
        if self._manifest_path:
            title = f"Guided Merge — {self._manifest_path.name} *"
        else:
            title = "Guided Merge *"
        self._status_label_global.setText(title)
