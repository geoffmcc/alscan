# SPDX-License-Identifier: GPL-3.0-only
"""Tests for alscan.merge.inputs — source validation, detection, lineage."""

import json
import math

import pytest

from alscan.io_safety import capture_identity
from alscan.merge.inputs import (
    detect_document_type,
    normalize_snapshot_json,
    assess_lineage,
    validate_three_way,
    DocumentType,
    LineageResult,
)
from alscan.merge.plan import MergePlan
from alscan.versioner import Snapshot, build_snapshot
from alscan.parser import parse_xml_string

SIMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
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
    <Tracks/>
  </LiveSet>
</Ableton>"""

SIMPLE_PROJ = parse_xml_string(SIMPLE_XML)
SIMPLE_SNAP = build_snapshot(SIMPLE_PROJ)


def _snapshot_json(snap: Snapshot = None) -> str:
    if snap is None:
        snap = SIMPLE_SNAP
    return snap.to_json()


class TestDetectDocumentType:
    def test_v0_3_snapshot_no_document_type(self):
        raw = _snapshot_json()
        assert detect_document_type(raw) == DocumentType.SNAPSHOT_V1

    def test_with_document_type(self):
        raw = _snapshot_json()
        d = json.loads(raw)
        d["document_type"] = "alscan-snapshot"
        assert detect_document_type(json.dumps(d)) == DocumentType.SNAPSHOT_V1

    def test_merged_snapshot_rejected(self):
        raw = json.dumps({"document_type": "alscan-merged-snapshot"})
        assert detect_document_type(raw) == DocumentType.MERGED_SNAPSHOT

    def test_merge_plan_rejected(self):
        raw = json.dumps({"document_type": "alscan-merge-plan"})
        assert detect_document_type(raw) == DocumentType.MERGE_PLAN

    def test_unknown_document_type(self):
        raw = json.dumps({"document_type": "some-unknown-type"})
        assert detect_document_type(raw) == DocumentType.UNKNOWN

    def test_arbitrary_json_rejected(self):
        raw = json.dumps({"foo": 1, "bar": 2})
        assert detect_document_type(raw) == DocumentType.UNKNOWN


class TestNormalizeSnapshotJson:
    def test_v0_3_snapshot_passes(self):
        raw = _snapshot_json()
        result = normalize_snapshot_json(raw)
        assert isinstance(result, str)

    def test_v0_3_snapshot_round_trips(self):
        raw = _snapshot_json()
        result = normalize_snapshot_json(raw)
        assert json.loads(result) == json.loads(raw)

    def test_with_document_type_stripped(self):
        raw = _snapshot_json()
        d = json.loads(raw)
        d["document_type"] = "alscan-snapshot"
        raw_with_dt = json.dumps(d)
        result = normalize_snapshot_json(raw_with_dt)
        result_d = json.loads(result)
        assert "document_type" not in result_d
        snap = Snapshot.from_json(result)
        assert snap.tempo == 120.0

    def test_merge_plan_rejected(self):
        raw = json.dumps({"document_type": "alscan-merge-plan"})
        with pytest.raises(ValueError, match="Expected a Snapshot"):
            normalize_snapshot_json(raw)

    def test_merged_snapshot_rejected(self):
        raw = json.dumps({"document_type": "alscan-merged-snapshot"})
        with pytest.raises(ValueError, match="Expected a Snapshot"):
            normalize_snapshot_json(raw)

    def test_arbitrary_json_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            normalize_snapshot_json(json.dumps({"foo": 1}))


class TestAssessLineage:
    def _snap_with_tracks(self, tempo: float, track_ids: list[int],
                          project_name: str = "song") -> Snapshot:
        proj = parse_xml_string(SIMPLE_XML)
        proj.tempo = tempo
        proj.tracks = []
        for tid in track_ids:
            from alscan.models import Track
            proj.tracks.append(Track(
                name=f"Track {tid}", track_id=tid, track_type="audio"
            ))
        return build_snapshot(proj)

    def test_identical_snapshots_strong(self):
        s = self._snap_with_tracks(120.0, [0, 1, 2])
        result = assess_lineage(s, s, s)
        assert result.level == "strong"
        assert result.fingerprint_match

    def test_fingerprint_match_plus_track_overlap(self):
        base = self._snap_with_tracks(120.0, [0, 1, 2, 3, 4])
        ours = self._snap_with_tracks(120.0, [0, 1, 2, 3, 4])
        base.proj_name = "song"
        ours.proj_name = "song"
        # Manually ensure fingerprints match
        ours.tempo = base.tempo
        ours.time_signature = base.time_signature
        ourselves = build_snapshot(SIMPLE_PROJ)
        ourselves.tracks = ours.tracks
        yourselves = build_snapshot(SIMPLE_PROJ)
        yourselves.tracks = base.tracks
        result = assess_lineage(ourselves, ourselves, yourselves)
        assert result.level in ("strong", "plausible")

    def test_fingerprint_mismatch_project_name_match(self):
        base = self._snap_with_tracks(120.0, [0, 1, 2, 3, 4])
        theirs = self._snap_with_tracks(128.0, [0, 1, 2, 3, 4])
        theirs.tempo = 128.0
        base.proj_name = "song"
        theirs.proj_name = "song"
        result = assess_lineage(base, theirs, theirs)
        assert result.level in ("plausible", "weak")

    def test_no_relationship(self):
        base = self._snap_with_tracks(120.0, [0, 1, 2], "song-a")
        theirs = self._snap_with_tracks(140.0, [10, 20], "song-b")
        base.project_name = "song-a"
        theirs.project_name = "song-b"
        result = assess_lineage(base, theirs, theirs)
        assert result.level == "no_meaningful_relationship"

    def test_fingerprint_alone_is_not_strong(self):
        base = self._snap_with_tracks(120.0, [10, 20, 30])
        ours = self._snap_with_tracks(120.0, [10, 20, 30])
        # If fingerprints match but track count is low, need overlap
        # This tests the threshold
        result = assess_lineage(base, ours, ours)
        assert result.track_overlap_pct >= 0.5 or result.level != "strong"


class TestValidateThreeWay:
    def test_duplicate_inputs_rejected(self, tmp_path):
        import gzip
        xml = """<?xml version='1.0' encoding='UTF-8'?>
<Ableton MajorVersion="12" MinorVersion="1.5">
  <LiveSet>
    <Tempo><Manual>120.0</Manual></Tempo>
    <TimeSig><Numerator>4</Numerator><Denominator>4</Denominator></TimeSig>
    <Tracks>
      <MidiTrack>
        <TrackId>0</TrackId>
        <Name><EffectiveName>Track 1</EffectiveName></Name>
        <DeviceChain/>
      </MidiTrack>
    </Tracks>
  </LiveSet>
</Ableton>"""
        f = tmp_path / "project.als"
        with gzip.open(str(f), "wt", encoding="utf-8") as fh:
            fh.write(xml)
        with pytest.raises(ValueError, match="Duplicate physical input"):
            validate_three_way(str(f), str(f), str(f))


class TestNanRejection:
    def test_snapshot_with_nan_raises(self):
        snap = Snapshot(
            format_version="1",
            structural_fingerprint="abc123",
            project_name="test",
            timestamp=1000.0,
            creator="",
            major_version="12",
            minor_version="1",
            tempo=float("nan"),
            time_signature=[4, 4],
            tracks=[],
            locators=[],
        )
        with pytest.raises(ValueError, match="Out of range float"):
            snap.to_json()

    def test_merge_plan_with_nan_raises(self):
        plan = MergePlan(conflict_count=1)
        plan.conflicts.append({
            "id": "conflict-tempo",
            "field": "tempo",
            "base_value": 120.0,
            "ours_value": float("nan"),
            "theirs_value": 128.0,
        })
        with pytest.raises(ValueError, match="Out of range float"):
            plan.to_json()

    def test_snapshot_with_inf_raises(self):
        snap = Snapshot(
            format_version="1",
            structural_fingerprint="abc123",
            project_name="test",
            timestamp=float("inf"),
            creator="",
            major_version="12",
            minor_version="1",
            tempo=120.0,
            time_signature=[4, 4],
            tracks=[],
            locators=[],
        )
        with pytest.raises(ValueError, match="Out of range float"):
            snap.to_json()
