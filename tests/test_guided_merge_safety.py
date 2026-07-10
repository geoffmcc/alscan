# SPDX-License-Identifier: GPL-3.0-only

import gzip
import json
from pathlib import Path

import pytest

from alscan.io_safety import capture_identity, are_same_file
from alscan.merge.guided import create_merge_session, build_merge_operations
from alscan.merge.manifest import MergeManifest
from alscan.merge.verification import verify_destination
from alscan.merge.operation import OperationState, ExecutionMode

BASE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12" Creator="Ableton Live 12">
  <LiveSet>
    <Tempo><Manual Value="120"/></Tempo>
    <TimeSignature>
      <TimeSignatures>
        <RemoteableTimeSignature>
          <Numerator Value="4"/><Denominator Value="4"/>
        </RemoteableTimeSignature>
      </TimeSignatures>
    </TimeSignature>
    <Locators><Locators/></Locators>
    <Tracks>
      <AudioTrack Id="0">
        <Name><EffectiveName Value="Kick"/></Name>
        <ColorIndex Value="1"/>
        <DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain>
      </AudioTrack>
    </Tracks>
  </LiveSet>
</Ableton>"""

WEAK_OURS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12" Creator="Ableton Live 12">
  <LiveSet>
    <Tempo><Manual Value="128"/></Tempo>
    <TimeSignature>
      <TimeSignatures>
        <RemoteableTimeSignature>
          <Numerator Value="4"/><Denominator Value="4"/>
        </RemoteableTimeSignature>
      </TimeSignatures>
    </TimeSignature>
    <Locators><Locators/></Locators>
    <Tracks>
      <AudioTrack Id="5">
        <Name><EffectiveName Value="Bass"/></Name>
        <ColorIndex Value="2"/>
        <DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain>
      </AudioTrack>
    </Tracks>
  </LiveSet>
</Ableton>"""

WEAK_THEIRS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12" Creator="Ableton Live 12">
  <LiveSet>
    <Tempo><Manual Value="132"/></Tempo>
    <TimeSignature>
      <TimeSignatures>
        <RemoteableTimeSignature>
          <Numerator Value="4"/><Denominator Value="4"/>
        </RemoteableTimeSignature>
      </TimeSignatures>
    </TimeSignature>
    <Locators><Locators/></Locators>
    <Tracks>
      <AudioTrack Id="9">
        <Name><EffectiveName Value="Pad"/></Name>
        <ColorIndex Value="3"/>
        <DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain>
      </AudioTrack>
    </Tracks>
  </LiveSet>
</Ableton>"""


def _write_als(tmp_path, name, xml):
    path = tmp_path / name
    data = xml.encode("utf-8")
    path.write_bytes(gzip.compress(data))
    return path


class TestSourceImmutability:
    def test_sources_unchanged_after_session_creation(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        before_base = capture_identity(base)
        before_ours = capture_identity(ours)
        before_theirs = capture_identity(theirs)
        create_merge_session(str(base), str(ours), str(theirs))
        after_base = capture_identity(base)
        after_ours = capture_identity(ours)
        after_theirs = capture_identity(theirs)
        assert before_base.sha256 == after_base.sha256
        assert before_ours.sha256 == after_ours.sha256
        assert before_theirs.sha256 == after_theirs.sha256

    def test_sources_unchanged_after_operations_build(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        before_base = capture_identity(base)
        before_ours = capture_identity(ours)
        before_theirs = capture_identity(theirs)
        session, plan = create_merge_session(
            str(base), str(ours), str(theirs)
        )
        build_merge_operations(session, plan, "base")
        after_base = capture_identity(base)
        after_ours = capture_identity(ours)
        after_theirs = capture_identity(theirs)
        assert before_base.sha256 == after_base.sha256
        assert before_ours.sha256 == after_ours.sha256
        assert before_theirs.sha256 == after_theirs.sha256

    def test_sources_unchanged_after_manifest_generation(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        before_base = capture_identity(base)
        before_ours = capture_identity(ours)
        before_theirs = capture_identity(theirs)
        session, plan = create_merge_session(
            str(base), str(ours), str(theirs)
        )
        operations = build_merge_operations(session, plan, "base")
        MergeManifest.create(session, operations)
        after_base = capture_identity(base)
        after_ours = capture_identity(ours)
        after_theirs = capture_identity(theirs)
        assert before_base.sha256 == after_base.sha256
        assert before_ours.sha256 == after_ours.sha256
        assert before_theirs.sha256 == after_theirs.sha256


class TestDestinationCollision:
    def test_dest_same_as_source_rejected(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        session, plan = create_merge_session(
            str(base), str(ours), str(theirs)
        )
        operations = build_merge_operations(session, plan, "base")
        manifest = MergeManifest.create(session, operations)
        report = verify_destination(
            str(base),
            manifest,
            {"base": str(base), "ours": str(ours), "theirs": str(theirs)},
            {
                "base": capture_identity(base).sha256,
                "ours": capture_identity(ours).sha256,
                "theirs": capture_identity(theirs).sha256,
            },
        )
        assert any("same file" in e for e in report.errors)

    def test_same_source_twice_rejected_at_input(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        session, _ = create_merge_session(str(base), str(ours), str(base))
        assert session.safety_preflight.path_collision_check is False


class TestWeakLineage:
    def test_weak_lineage_blocks_automation(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", WEAK_OURS_XML)
        theirs = _write_als(tmp_path, "theirs.als", WEAK_THEIRS_XML)
        session, plan = create_merge_session(
            str(base), str(ours), str(theirs), allow_unrelated=True
        )
        assert session.safety_preflight.lineage_confidence in (
            "weak",
            "no_meaningful_relationship",
        )

    def test_strong_lineage_allows_proper_flow(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        session, plan = create_merge_session(
            str(base), str(ours), str(theirs)
        )
        assert session.safety_preflight.lineage_confidence == "strong"


class TestVerificationSafety:
    def test_verification_does_not_modify_dest(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        dest = _write_als(tmp_path, "dest.als", BASE_XML)
        session, plan = create_merge_session(
            str(base), str(ours), str(theirs)
        )
        operations = build_merge_operations(session, plan, "base")
        manifest = MergeManifest.create(session, operations)
        before = capture_identity(dest)
        verify_destination(
            str(dest),
            manifest,
            {"base": str(base), "ours": str(ours), "theirs": str(theirs)},
            {
                "base": capture_identity(base).sha256,
                "ours": capture_identity(ours).sha256,
                "theirs": capture_identity(theirs).sha256,
            },
        )
        after = capture_identity(dest)
        assert before.sha256 == after.sha256

    def test_manifest_json_stays_byte_identical_after_read(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        session, plan = create_merge_session(
            str(base), str(ours), str(theirs)
        )
        operations = build_merge_operations(session, plan, "base")
        manifest = MergeManifest.create(session, operations)
        json1 = manifest.to_json()
        manifest2 = MergeManifest.from_json(json1)
        json2 = manifest2.to_json()
        assert json1 == json2


class TestManifestSafety:
    def test_malformed_json_no_write(self, tmp_path):
        with pytest.raises(ValueError):
            MergeManifest.from_json("not valid json")

    def test_wrong_document_type(self, tmp_path):
        with pytest.raises(ValueError):
            MergeManifest.from_json(
                json.dumps({"document_type": "not-alscan-merge-manifest"})
            )

    def test_manifest_has_no_path_rewrites(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        session, plan = create_merge_session(
            str(base), str(ours), str(theirs)
        )
        operations = build_merge_operations(session, plan, "base")
        manifest = MergeManifest.create(session, operations)
        json_str = manifest.to_json()
        assert "writ" not in json_str.lower()


class TestHashPreservation:
    def test_captured_hashes_in_manifest(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        id_base = capture_identity(base)
        id_ours = capture_identity(ours)
        id_theirs = capture_identity(theirs)
        session, plan = create_merge_session(
            str(base), str(ours), str(theirs)
        )
        assert session.sources["base"].sha256 == id_base.sha256
        assert session.sources["ours"].sha256 == id_ours.sha256
        assert session.sources["theirs"].sha256 == id_theirs.sha256

    def test_hash_stability_across_operations(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        before_base = capture_identity(base)
        before_ours = capture_identity(ours)
        before_theirs = capture_identity(theirs)
        session, plan = create_merge_session(
            str(base), str(ours), str(theirs)
        )
        operations = build_merge_operations(session, plan, "base")
        MergeManifest.create(session, operations)
        after_base = capture_identity(base)
        after_ours = capture_identity(ours)
        after_theirs = capture_identity(theirs)
        assert before_base.sha256 == after_base.sha256
        assert before_ours.sha256 == after_ours.sha256
        assert before_theirs.sha256 == after_theirs.sha256


class TestOperationStateTransitions:
    def test_all_manual_ops_start_correctly(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        session, plan = create_merge_session(
            str(base), str(ours), str(theirs)
        )
        operations = build_merge_operations(session, plan, "base")
        valid_states = {
            OperationState.PROPOSED,
            OperationState.AWAITING_DECISION,
            OperationState.ACCEPTED,
            OperationState.COMPLETED_MANUAL,
        }
        valid_modes = {
            ExecutionMode.MANUAL_ONLY,
            ExecutionMode.UNSUPPORTED,
            ExecutionMode.AUTOMATIC_EXPERIMENTAL,
            ExecutionMode.AUTOMATABLE_BUT_DISABLED,
        }
        for op in operations:
            assert op.state in valid_states
            assert op.execution_mode in valid_modes

    def test_all_operations_have_ids(self, tmp_path):
        base = _write_als(tmp_path, "base.als", BASE_XML)
        ours = _write_als(tmp_path, "ours.als", BASE_XML)
        theirs = _write_als(tmp_path, "theirs.als", BASE_XML)
        session, plan = create_merge_session(
            str(base), str(ours), str(theirs)
        )
        operations = build_merge_operations(session, plan, "base")
        ids = [op.operation_id for op in operations]
        assert all(ids)
        assert len(ids) == len(set(ids))
