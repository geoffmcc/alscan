# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import json

import pytest

from alscan.merge.manifest import MergeManifest, MANIFEST_FORMAT_VERSION
from alscan.merge.operation import (
    ActivityCategory,
    ExecutionMode,
    MergeInstruction,
    MergeOperation,
    OperationState,
    RiskLevel,
    SupportClassification,
    VALID_STATE_TRANSITIONS,
    VerificationResult,
    VerificationRule,
)
from alscan.merge.session import (
    COMPLETION_STATES,
    FoundationRecommendation,
    MergeSession,
    SafetyPreflight,
    SourceRecord,
    WORKFLOW_STATES,
)


class TestMergeSession:
    def test_default_session_has_id(self):
        session = MergeSession()
        assert session.session_id
        assert len(session.session_id) == 16

    def test_session_created_at_populated(self):
        session = MergeSession()
        assert session.created_at_utc
        assert "T" in session.created_at_utc

    def test_initial_state_is_preflight(self):
        session = MergeSession()
        assert session.workflow_state == "preflight"

    def test_valid_state_transitions(self):
        session = MergeSession()
        path = [
            "analyzing",
            "choosing_foundation",
            "reviewing_decisions",
            "preparing_destination",
            "performing_merge",
            "collect_and_save",
            "verifying",
            "completed",
        ]
        for state in path:
            session.transition_to(state)
            assert session.workflow_state == state

    def test_invalid_state_transition(self):
        session = MergeSession()
        with pytest.raises(ValueError):
            session.transition_to("completed")

    def test_is_active(self):
        session = MergeSession()
        assert session.is_active()
        session.transition_to("analyzing")
        assert session.is_active()
        path = [
            "choosing_foundation",
            "reviewing_decisions",
            "preparing_destination",
            "performing_merge",
            "collect_and_save",
            "verifying",
            "completed",
        ]
        for state in path:
            session.transition_to(state)
        assert not session.is_active()

        session2 = MergeSession()
        session2.workflow_state = "cancelled"
        assert not session2.is_active()

    def test_to_dict_includes_all_fields(self):
        session = MergeSession()
        d = session.to_dict()
        expected_fields = {
            "session_id",
            "created_at_utc",
            "alscan_version",
            "supported_live_generation",
            "sources",
            "safety_preflight",
            "foundation_recommendation",
            "selected_foundation",
            "destination_path",
            "workflow_state",
            "verification_status",
            "completion_state",
            "notes",
            "warnings",
            "errors",
        }
        assert set(d.keys()) == expected_fields

    def test_source_record_defaults(self):
        sr = SourceRecord(path="test.als")
        assert sr.path == "test.als"
        assert sr.resolved == ""
        assert sr.label == ""
        assert sr.sha256 == ""
        assert sr.size == 0
        assert sr.mtime == 0.0


class TestMergeOperation:
    def test_default_operation_state(self):
        op = MergeOperation()
        assert op.state == OperationState.PROPOSED

    def test_valid_state_transitions(self):
        for target in VALID_STATE_TRANSITIONS[OperationState.PROPOSED]:
            op = MergeOperation()
            op.transition_to(target)
            assert op.state == target

    def test_invalid_state_transition(self):
        op = MergeOperation()
        with pytest.raises(ValueError):
            op.transition_to(OperationState.READY)

    def test_proposed_to_accepted_to_ready(self):
        op = MergeOperation()
        op.transition_to(OperationState.ACCEPTED)
        assert op.state == OperationState.ACCEPTED
        op.transition_to(OperationState.READY)
        assert op.state == OperationState.READY

    def test_cannot_transition_from_rejected(self):
        op = MergeOperation()
        op.transition_to(OperationState.REJECTED)
        with pytest.raises(ValueError):
            op.transition_to(OperationState.READY)

    def test_ready_to_in_progress_to_completed_manual(self):
        op = MergeOperation()
        op.transition_to(OperationState.ACCEPTED)
        op.transition_to(OperationState.READY)
        op.transition_to(OperationState.IN_PROGRESS)
        assert op.state == OperationState.IN_PROGRESS
        op.transition_to(OperationState.COMPLETED_MANUAL)
        assert op.state == OperationState.COMPLETED_MANUAL

    def test_completed_to_verified(self):
        op = MergeOperation()
        op.transition_to(OperationState.ACCEPTED)
        op.transition_to(OperationState.READY)
        op.transition_to(OperationState.IN_PROGRESS)
        op.transition_to(OperationState.COMPLETED_MANUAL)
        op.transition_to(OperationState.VERIFICATION_PASSED)
        assert op.state == OperationState.VERIFICATION_PASSED

    def test_failed_verification_can_retry(self):
        op = MergeOperation()
        op.transition_to(OperationState.ACCEPTED)
        op.transition_to(OperationState.READY)
        op.transition_to(OperationState.IN_PROGRESS)
        op.transition_to(OperationState.COMPLETED_MANUAL)
        op.transition_to(OperationState.VERIFICATION_FAILED)
        assert op.state == OperationState.VERIFICATION_FAILED
        op.transition_to(OperationState.IN_PROGRESS)
        assert op.state == OperationState.IN_PROGRESS

    def test_can_automate(self):
        manual_op = MergeOperation(execution_mode=ExecutionMode.MANUAL_ONLY)
        assert not manual_op.can_automate()
        auto_op = MergeOperation(execution_mode=ExecutionMode.AUTOMATIC_EXPERIMENTAL)
        assert auto_op.can_automate()

    def test_is_completed(self):
        op = MergeOperation()
        assert not op.is_completed()
        op.state = OperationState.COMPLETED_MANUAL
        assert op.is_completed()
        op.state = OperationState.COMPLETED_AUTOMATIC
        assert op.is_completed()

    def test_is_verified(self):
        op = MergeOperation()
        op.state = OperationState.VERIFICATION_PASSED
        assert op.is_verified()
        assert op.has_verification_result()
        op.state = OperationState.VERIFICATION_FAILED
        assert not op.is_verified()
        assert op.has_verification_result()

    def test_to_dict_serialization(self):
        op = MergeOperation(
            operation_id="op-1",
            title="Test Operation",
            category=ActivityCategory.TRACK_ADDITION,
            risk_level=RiskLevel.HIGH,
            support_classification=SupportClassification.SUGGESTED_RESOLUTION,
            execution_mode=ExecutionMode.AUTOMATIC_SUPPORTED,
            state=OperationState.ACCEPTED,
        )
        d = op.to_dict()
        assert d["category"] == "track_addition"
        assert d["risk_level"] == "high"
        assert d["support_classification"] == "suggested_resolution"
        assert d["execution_mode"] == "automatic_supported"
        assert d["state"] == "accepted"

    def test_execution_mode_enum_values(self):
        assert ExecutionMode.MANUAL_ONLY.value == "manual_only"
        assert ExecutionMode.AUTOMATABLE_BUT_DISABLED.value == "automatable_but_disabled"
        assert ExecutionMode.AUTOMATIC_EXPERIMENTAL.value == "automatic_experimental"
        assert ExecutionMode.AUTOMATIC_SUPPORTED.value == "automatic_supported"
        assert ExecutionMode.UNSUPPORTED.value == "unsupported"

    def test_operation_state_values(self):
        assert OperationState.PROPOSED.value == "proposed"
        assert OperationState.AWAITING_DECISION.value == "awaiting_decision"
        assert OperationState.ACCEPTED.value == "accepted"
        assert OperationState.REJECTED.value == "rejected"
        assert OperationState.DEFERRED.value == "deferred"
        assert OperationState.READY.value == "ready"
        assert OperationState.IN_PROGRESS.value == "in_progress"
        assert OperationState.COMPLETED_MANUAL.value == "completed_manual"
        assert OperationState.COMPLETED_AUTOMATIC.value == "completed_automatic"
        assert OperationState.VERIFICATION_PASSED.value == "verification_passed"
        assert OperationState.VERIFICATION_FAILED.value == "verification_failed"
        assert OperationState.BLOCKED.value == "blocked"
        assert OperationState.UNSUPPORTED.value == "unsupported"

    def test_blocked_can_be_unblocked(self):
        op = MergeOperation()
        op.transition_to(OperationState.ACCEPTED)
        op.transition_to(OperationState.BLOCKED)
        assert op.state == OperationState.BLOCKED
        op.transition_to(OperationState.AWAITING_DECISION)
        assert op.state == OperationState.AWAITING_DECISION

        op2 = MergeOperation()
        op2.transition_to(OperationState.ACCEPTED)
        op2.transition_to(OperationState.READY)
        op2.transition_to(OperationState.BLOCKED)
        assert op2.state == OperationState.BLOCKED
        op2.transition_to(OperationState.READY)
        assert op2.state == OperationState.READY


class TestMergeManifest:
    def test_default_format_version(self):
        assert MANIFEST_FORMAT_VERSION == "1"

    def test_create_from_session(self):
        session = MergeSession()
        manifest = MergeManifest.create(session)
        assert manifest.document_type == "alscan-merge-manifest"
        assert manifest.format_version == "1"
        assert manifest.session["session_id"] == session.session_id
        assert manifest.operations == []
        assert manifest.source_hashes_captured == {}
        assert manifest.source_hashes_final == {}
        assert manifest.verification_summary == {}

    def test_create_with_operations(self):
        session = MergeSession()
        op1 = MergeOperation(operation_id="op-1", title="Track Add")
        op2 = MergeOperation(operation_id="op-2", title="Device Set")
        manifest = MergeManifest.create(session, operations=[op1, op2])
        assert len(manifest.operations) == 2
        assert manifest.operations[0]["operation_id"] == "op-1"
        assert manifest.operations[0]["title"] == "Track Add"
        assert manifest.operations[1]["operation_id"] == "op-2"

    def test_to_json_and_from_json_roundtrip(self):
        session = MergeSession()
        op = MergeOperation(
            operation_id="op-roundtrip",
            title="Roundtrip Test",
            category=ActivityCategory.SET_LEVEL,
            risk_level=RiskLevel.LOW,
            support_classification=SupportClassification.NO_DIRECT_CONFLICT,
            execution_mode=ExecutionMode.MANUAL_ONLY,
            state=OperationState.PROPOSED,
        )
        manifest = MergeManifest.create(session, operations=[op])
        manifest.source_hashes_captured = {"base": "abc123"}
        json_str = manifest.to_json()
        restored = MergeManifest.from_json(json_str)
        assert restored.document_type == "alscan-merge-manifest"
        assert restored.format_version == "1"
        restored_session = restored.get_session()
        assert restored_session.session_id == session.session_id
        restored_ops = restored.get_operations()
        assert len(restored_ops) == 1
        assert restored_ops[0].operation_id == "op-roundtrip"
        assert restored.source_hashes_captured == {"base": "abc123"}

    def test_get_session(self):
        session = MergeSession()
        manifest = MergeManifest.create(session)
        recovered = manifest.get_session()
        assert isinstance(recovered, MergeSession)
        assert recovered.session_id == session.session_id

    def test_get_operations(self):
        session = MergeSession()
        op = MergeOperation(operation_id="op-get", category=ActivityCategory.TRACK_ADDITION)
        manifest = MergeManifest.create(session, operations=[op])
        recovered = manifest.get_operations()
        assert len(recovered) == 1
        assert isinstance(recovered[0], MergeOperation)
        assert recovered[0].operation_id == "op-get"

    def test_redacted_copy_removes_paths(self):
        session = MergeSession()
        session.sources = {
            "base": SourceRecord(path="/secret/base.als", label="base"),
            "ours": SourceRecord(path="/secret/ours.als", label="ours"),
        }
        manifest = MergeManifest.create(session)
        manifest.source_hashes_captured = {"base": "aaaa", "ours": "bbbb"}
        manifest.source_hashes_final = {"base": "cccc", "ours": "dddd"}
        redacted = manifest.redacted_copy()
        redacted_session = redacted.get_session()
        for role in ("base", "ours"):
            src = redacted_session.sources[role]
            if isinstance(src, dict):
                assert src["path"] == "[redacted path]"
                assert src["resolved"] == "[redacted path]"
                assert src["label"] == "[redacted label]"
            else:
                assert src.path == "[redacted path]"
        assert redacted.source_hashes_captured["base"] == "[redacted]"
        assert redacted.source_hashes_final["base"] == "[redacted]"

    def test_from_json_rejects_wrong_type(self):
        with pytest.raises(ValueError, match="alscan-merge-manifest"):
            MergeManifest.from_json(json.dumps({"document_type": "not-alscan"}))

    def test_sync_from_objects(self):
        session = MergeSession()
        op = MergeOperation(operation_id="op-sync")
        manifest = MergeManifest.create(session, operations=[op])
        original_updated = manifest.updated_at_utc
        op.title = "Synced Title"
        op.state = OperationState.ACCEPTED
        manifest.get_operations()
        manifest.sync_from_objects()
        assert manifest.updated_at_utc != original_updated
        assert manifest.operations[0]["title"] == "Synced Title"
        assert manifest.operations[0]["state"] == "accepted"

    def test_schema_version_behavior(self):
        manifest = MergeManifest()
        assert manifest.format_version == "1"
        future_json = json.dumps({
            "document_type": "alscan-merge-manifest",
            "format_version": "999",
            "alscan_version": "9.9.9",
            "created_at_utc": "",
            "updated_at_utc": "",
            "session": {},
            "operations": [],
            "source_hashes_captured": {},
            "source_hashes_final": {},
            "verification_summary": {},
        })
        with pytest.raises(ValueError, match="newer alscan"):
            MergeManifest.from_json(future_json)

    def test_source_hashes_preserved(self):
        session = MergeSession()
        manifest = MergeManifest.create(session)
        manifest.source_hashes_captured = {"base": "hash1", "ours": "hash2"}
        manifest.source_hashes_final = {"base": "hash3", "ours": "hash4"}
        json_str = manifest.to_json()
        restored = MergeManifest.from_json(json_str)
        assert restored.source_hashes_captured == {"base": "hash1", "ours": "hash2"}
        assert restored.source_hashes_final == {"base": "hash3", "ours": "hash4"}


class TestSafetyPreflight:
    def test_passed_all_checks(self):
        preflight = SafetyPreflight(
            path_collision_check=True,
            all_hashes_stable=True,
            version_check=True,
        )
        assert preflight.passed()

    def test_failed_collision(self):
        preflight = SafetyPreflight(
            path_collision_check=False,
            all_hashes_stable=True,
            version_check=True,
        )
        assert not preflight.passed()

    def test_failed_hash_stability(self):
        preflight = SafetyPreflight(
            path_collision_check=True,
            all_hashes_stable=False,
            version_check=True,
        )
        assert not preflight.passed()


class TestMergeManifestPersistence:
    def test_save_reload_roundtrip_decisions_preserved(self):
        session = MergeSession()
        session.selected_foundation = "theirs"
        ops = [
            MergeOperation(operation_id="op-1", title="Test", state=OperationState.ACCEPTED),
            MergeOperation(operation_id="op-2", title="Test 2", state=OperationState.REJECTED),
            MergeOperation(operation_id="op-3", title="Test 3", state=OperationState.COMPLETED_MANUAL),
        ]
        manifest = MergeManifest.create(session, ops)
        manifest.source_hashes_captured = {"base": "abc", "ours": "def", "theirs": "ghi"}

        json_str = manifest.to_json()
        reloaded = MergeManifest.from_json(json_str)
        reloaded_session = reloaded.get_session()
        reloaded_ops = reloaded.get_operations()

        assert reloaded_session.selected_foundation == "theirs"
        assert len(reloaded_ops) == 3
        assert reloaded_ops[0].state == OperationState.ACCEPTED
        assert reloaded_ops[1].state == OperationState.REJECTED
        assert reloaded_ops[2].state == OperationState.COMPLETED_MANUAL
        assert reloaded.source_hashes_captured["base"] == "abc"

    def test_verification_results_preserved(self):
        session = MergeSession()
        op = MergeOperation(operation_id="op-1", state=OperationState.VERIFICATION_PASSED)
        op.verification_result = VerificationResult(status="pass", expected=120, observed=120, explanation="Match")
        manifest = MergeManifest.create(session, [op])
        reloaded = MergeManifest.from_json(manifest.to_json())
        ops = reloaded.get_operations()
        assert ops[0].state == OperationState.VERIFICATION_PASSED

    def test_redacted_export_does_not_mutate_original(self):
        session = MergeSession()
        session.sources["base"] = SourceRecord(path="/secret/base.als", label="Secret", sha256="abc")
        manifest = MergeManifest.create(session)
        original_json = manifest.to_json()
        manifest.redacted_copy()
        after_json = manifest.to_json()
        assert original_json == after_json

    def test_changed_source_detection_via_hash(self):
        session = MergeSession()
        session.sources["base"] = SourceRecord(path="/tmp/test.als", label="test.als", sha256="abc123")
        manifest = MergeManifest.create(session)
        manifest.source_hashes_captured = {"base": "abc123", "ours": "def456", "theirs": "ghi789"}
        reloaded = MergeManifest.from_json(manifest.to_json())
        expected = reloaded.source_hashes_captured.get("base", "")
        assert expected == "abc123"

    def test_schema_version_preserved(self):
        manifest = MergeManifest()
        assert manifest.format_version == MANIFEST_FORMAT_VERSION
        reloaded = MergeManifest.from_json(manifest.to_json())
        assert reloaded.format_version == MANIFEST_FORMAT_VERSION


class TestManualOnlyEnforcement:
    def test_als_writing_disabled_by_default(self):
        from alscan.merge.executor import ALS_WRITING_ENABLED
        assert ALS_WRITING_ENABLED is False

    def test_automatic_executor_registration_rejected(self):
        from alscan.merge.executor import (
            ExecutorRegistry, ALS_WRITING_ENABLED, OperationExecutor,
            ManualInstructionExecutor, VerificationOnlyExecutor,
            PreflightResult, ApplyResult, RiskDescription,
        )
        import pytest
        reg = ExecutorRegistry()
        class FakeAutoExecutor(OperationExecutor):
            def supports(self, op, ctx):
                from alscan.merge.executor import SupportResult, ExecutorSupport
                return SupportResult(supported=True, classification=ExecutorSupport.EXPERIMENTAL)
            def supported_live_versions(self): return ["12"]
            def supported_operation_types(self): return ["tempo"]
            def confidence_requirements(self): return "high"
            def lineage_requirements(self): return "strong"
            def modifies_xml(self): return True
            def copies_opaque_subtree(self): return False
            def validation_guarantees(self): return ["test"]
            def describe_risk(self, op): return RiskDescription()

        with pytest.raises(RuntimeError, match="ALS_WRITING_ENABLED"):
            reg.register("test_auto", FakeAutoExecutor())

    def test_guided_merge_operations_are_manual_only(self):
        from alscan.merge.operation import ExecutionMode
        from alscan.merge.guided import create_merge_session, build_merge_operations
        import gzip
        import tempfile
        from pathlib import Path

        xml = '<?xml version="1.0" encoding="UTF-8"?><Ableton MajorVersion="5" MinorVersion="12" Creator="Ableton Live 12"><LiveSet><Tempo><Manual Value="120"/></Tempo><TimeSignature><TimeSignatures><RemoteableTimeSignature><Numerator Value="4"/><Denominator Value="4"/></RemoteableTimeSignature></TimeSignatures></TimeSignature><Locators><Locators/></Locators><Tracks><AudioTrack Id="0"><Name><EffectiveName Value="Test"/></Name><DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain></AudioTrack></Tracks></LiveSet></Ableton>'

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            for name in ("base.als", "ours.als", "theirs.als"):
                (tdp / name).write_bytes(gzip.compress(xml.encode()))
            session, plan = create_merge_session(
                str(tdp / "base.als"), str(tdp / "ours.als"), str(tdp / "theirs.als")
            )
            ops = build_merge_operations(session, plan, "ours")
            for op in ops:
                assert op.execution_mode in {
                    ExecutionMode.MANUAL_ONLY, ExecutionMode.UNSUPPORTED,
                    ExecutionMode.AUTOMATABLE_BUT_DISABLED,
                }, f"Operation {op.operation_id} has unsafe mode: {op.execution_mode}"
                assert not op.can_automate(), f"Operation {op.operation_id} claims it can automate"
