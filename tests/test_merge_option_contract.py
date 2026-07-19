# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for merge option contract, input role labels, and guided merge parsing.

Phase 1 remediation: verifies that:
- --allow-plausible controls actual track matching
- Input role labels are correct in all validation loops
- Guided merge argument parsing handles options correctly
"""

from __future__ import annotations

import json
import gzip
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from alscan.cli import cli
from alscan.merge.analysis import build_merge_plan, _match_branch, _classify_branch_match
from alscan.merge.inputs import validate_three_way, ThreeWayInput
from alscan.merge.plan import MergePlan

from tests.three_way.fixtures import (
    snapshot, track, device,
    mutate, with_tempo, with_track_field,
    reset_ids, two_track_project, three_track_project,
)


RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plan_for(base, ours, theirs, allow_plausible=False):
    """Build a MergePlan from three Snapshots without file I/O."""
    lineage = SimpleNamespace(
        level="strong",
        fingerprint_match=True,
        track_overlap_pct=1.0,
        project_name_match=True,
        warnings=[],
    )
    inputs = ThreeWayInput(
        mode="snapshot",
        base_snapshot=base,
        ours_snapshot=ours,
        theirs_snapshot=theirs,
        base_identity=SimpleNamespace(sha256="b" * 40, size=100, path=Path("base.json")),
        ours_identity=SimpleNamespace(sha256="o" * 40, size=100, path=Path("ours.json")),
        theirs_identity=SimpleNamespace(sha256="t" * 40, size=100, path=Path("theirs.json")),
        lineage=lineage,
        allow_plausible=allow_plausible,
    )
    return build_merge_plan(inputs)


def _write_als(tmp_path, name, xml):
    path = tmp_path / name
    path.write_bytes(gzip.compress(xml.encode("utf-8")))
    return path


# ---------------------------------------------------------------------------
# Exact vs plausible matching
# ---------------------------------------------------------------------------


class TestExactVsPlausibleMatching:
    def test_identical_track_ids_match_by_default(self):
        """Tracks with the same ID should match even without plausible matching."""
        reset_ids()
        base = two_track_project("exact-default")
        ours = with_tempo(base, 128.0)
        theirs = base

        plan = _plan_for(base, ours, theirs, allow_plausible=False)
        ours_matches = [m for m in plan.identity_matches if m.ours_track_id is not None]
        assert len(ours_matches) == 2
        for m in ours_matches:
            assert m.ours_track_id == m.base_track_id

    def test_different_track_ids_no_match_by_default(self):
        """Tracks with different IDs should NOT match without allow_plausible."""
        reset_ids()
        base = snapshot(
            name="diff-id-base",
            tracks=[
                track(name="Kick", track_id=10, track_type="audio", color_index=1, group_id=5),
            ],
        )
        ours = snapshot(
            name="diff-id-ours",
            tracks=[
                track(name="Kick", track_id=20, track_type="audio", color_index=1, group_id=5),
            ],
        )
        theirs = base

        plan = _plan_for(base, ours, theirs, allow_plausible=False)
        # Ours track id=20 has no exact match in base
        ours_match = [m for m in plan.identity_matches if m.track_id == 10]
        assert len(ours_match) == 1
        assert ours_match[0].ours_track_id is None

    def test_different_track_ids_match_with_plausible(self):
        """Tracks with different IDs should match when allow_plausible=True."""
        reset_ids()
        base = snapshot(
            name="diff-id-base",
            tracks=[
                track(name="Kick", track_id=10, track_type="audio", color_index=1,
                      group_id=5, devices=[
                          device(name="Compressor", device_type="audio_effect"),
                      ]),
            ],
        )
        ours = snapshot(
            name="diff-id-ours",
            tracks=[
                track(name="Kick", track_id=20, track_type="audio", color_index=1,
                      group_id=5, devices=[
                          device(name="Compressor", device_type="audio_effect"),
                      ]),
            ],
        )
        theirs = base

        plan = _plan_for(base, ours, theirs, allow_plausible=True)
        ours_match = [m for m in plan.identity_matches if m.track_id == 10]
        assert len(ours_match) == 1
        assert ours_match[0].ours_track_id == 20
        assert ours_match[0].classification == "plausible"

    def test_exact_matching_preferred_over_plausible(self):
        """When exact match exists, it should be preferred over plausible candidates."""
        reset_ids()
        base = snapshot(
            name="exact-pref",
            tracks=[
                track(name="Kick", track_id=1, track_type="audio", color_index=1),
            ],
        )
        ours = snapshot(
            name="exact-pref-ours",
            tracks=[
                track(name="Kick", track_id=1, track_type="audio", color_index=1),
                track(name="Kick Copy", track_id=2, track_type="audio", color_index=1),
            ],
        )
        theirs = base

        plan = _plan_for(base, ours, theirs, allow_plausible=True)
        base_match = [m for m in plan.identity_matches if m.track_id == 1]
        assert len(base_match) == 1
        assert base_match[0].ours_track_id == 1
        assert base_match[0].classification == "exact"

    def test_plausible_does_not_collapse_ambiguous_candidates(self):
        """When two plausible candidates exist, classification should be ambiguous."""
        reset_ids()
        base = snapshot(
            name="ambiguous",
            tracks=[
                track(name="Kick", track_id=1, track_type="audio", color_index=1),
            ],
        )
        ours = snapshot(
            name="ambiguous-ours",
            tracks=[
                track(name="Kick", track_id=10, track_type="audio", color_index=1),
                track(name="Kick", track_id=11, track_type="audio", color_index=1),
            ],
        )
        theirs = base

        plan = _plan_for(base, ours, theirs, allow_plausible=True)
        base_match = [m for m in plan.identity_matches if m.track_id == 1]
        assert len(base_match) == 1
        assert base_match[0].classification == "ambiguous"

    def test_ours_and_theirs_independently_honor_plausible(self):
        """Ours and theirs matching should independently use the plausible setting."""
        reset_ids()
        base = snapshot(
            name="independent",
            tracks=[
                track(name="Kick", track_id=1, track_type="audio", color_index=1),
                track(name="Snare", track_id=2, track_type="audio", color_index=2),
            ],
        )
        # Ours has different IDs but matches by evidence
        ours = snapshot(
            name="independent-ours",
            tracks=[
                track(name="Kick", track_id=10, track_type="audio", color_index=1),
                track(name="Snare", track_id=11, track_type="audio", color_index=2),
            ],
        )
        # Theirs has exact same IDs
        theirs = snapshot(
            name="independent-theirs",
            tracks=[
                track(name="Kick", track_id=1, track_type="audio", color_index=1),
                track(name="Snare", track_id=2, track_type="audio", color_index=2),
            ],
        )

        plan = _plan_for(base, ours, theirs, allow_plausible=True)
        # Base track 1 should have both ours and theirs matched
        m1 = [m for m in plan.identity_matches if m.track_id == 1][0]
        assert m1.ours_track_id == 10
        assert m1.theirs_track_id == 1

    def test_without_plausible_theirs_still_exact(self):
        """Without allow_plausible, theirs tracks should still match by exact ID."""
        reset_ids()
        base = two_track_project("no-plausible")
        ours = snapshot(
            name="no-plausible-ours",
            tracks=[
                track(name="Kick", track_id=10, track_type="audio"),
            ],
        )
        theirs = base

        plan = _plan_for(base, ours, theirs, allow_plausible=False)
        m1 = [m for m in plan.identity_matches if m.track_id == 1][0]
        # Ours doesn't match (different ID, no plausible)
        assert m1.ours_track_id is None
        # Theirs matches exactly
        assert m1.theirs_track_id == 1

    def test_cli_services_analysis_agree_on_plausible(self, tmp_path):
        """CLI, services, and lower-level analysis should agree on plausible setting."""
        reset_ids()
        base = snapshot(
            name="agreement",
            tracks=[
                track(name="Kick", track_id=1, track_type="audio", color_index=1,
                      group_id=5, devices=[
                          device(name="Compressor", device_type="audio_effect"),
                      ]),
            ],
        )
        ours = snapshot(
            name="agreement-ours",
            tracks=[
                track(name="Kick", track_id=2, track_type="audio", color_index=1,
                      group_id=5, devices=[
                          device(name="Compressor", device_type="audio_effect"),
                      ]),
            ],
        )
        theirs = base

        # Lower-level analysis
        plan = _plan_for(base, ours, theirs, allow_plausible=True)
        m1 = [m for m in plan.identity_matches if m.track_id == 1][0]
        assert m1.ours_track_id == 2

        # Services level
        from alscan.services import create_merge_plan
        bf = tmp_path / "agg_base.json"
        of = tmp_path / "agg_ours.json"
        tf = tmp_path / "agg_theirs.json"
        bf.write_text(base.to_json(), encoding="utf-8")
        of.write_text(ours.to_json(), encoding="utf-8")
        tf.write_text(theirs.to_json(), encoding="utf-8")
        svc_plan = create_merge_plan(str(bf), str(of), str(tf), allow_unrelated=True, allow_plausible=True)
        svc_match = [m for m in svc_plan.identity_matches if m.track_id == 1][0]
        assert svc_match.ours_track_id == 2


# ---------------------------------------------------------------------------
# Input role labeling
# ---------------------------------------------------------------------------


class TestInputLabeling:
    def test_invalid_base_snapshot_label(self, tmp_path):
        """Invalid base input should report 'base' in the error."""
        base_json = tmp_path / "base.json"
        base_json.write_text(json.dumps({"document_type": "alscan-merge-plan"}))
        ours_json = tmp_path / "ours.json"
        ours_json.write_text(simple_snapshot_json())
        theirs_json = tmp_path / "theirs.json"
        theirs_json.write_text(simple_snapshot_json())

        with pytest.raises(ValueError, match="base input"):
            validate_three_way(str(base_json), str(ours_json), str(theirs_json))

    def test_invalid_ours_snapshot_label(self, tmp_path):
        """Invalid ours input should report 'ours' in the error."""
        base_json = tmp_path / "base.json"
        base_json.write_text(simple_snapshot_json())
        ours_json = tmp_path / "ours.json"
        ours_json.write_text(json.dumps({"document_type": "alscan-merge-plan"}))
        theirs_json = tmp_path / "theirs.json"
        theirs_json.write_text(simple_snapshot_json())

        with pytest.raises(ValueError, match="ours input"):
            validate_three_way(str(base_json), str(ours_json), str(theirs_json))

    def test_invalid_theirs_snapshot_label(self, tmp_path):
        """Invalid theirs input should report 'theirs' in the error."""
        base_json = tmp_path / "base.json"
        base_json.write_text(simple_snapshot_json())
        ours_json = tmp_path / "ours.json"
        ours_json.write_text(simple_snapshot_json())
        theirs_json = tmp_path / "theirs.json"
        theirs_json.write_text(json.dumps({"document_type": "alscan-merge-plan"}))

        with pytest.raises(ValueError, match="theirs input"):
            validate_three_way(str(base_json), str(ours_json), str(theirs_json))

    def test_invalid_base_als_label(self, tmp_path):
        """Invalid base .als input should report 'base' in the error."""
        base = tmp_path / "base.als"
        base.write_bytes(gzip.compress(b"not xml"))
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)

        with pytest.raises((ValueError, Exception)):
            validate_three_way(str(base), str(ours), str(theirs))


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
    <Tracks>
      <AudioTrack Id="0">
        <Name><EffectiveName Value="Kick"/></Name>
        <ColorIndex Value="1"/>
        <DeviceChain><Devices/><MainSequencer><ClipSlotList/></MainSequencer></DeviceChain>
      </AudioTrack>
    </Tracks>
  </LiveSet>
</Ableton>"""


def simple_snapshot_json():
    from alscan.parser import parse_xml_string
    from alscan.versioner import build_snapshot
    proj = parse_xml_string(SIMPLE_XML)
    return build_snapshot(proj).to_json()


# ---------------------------------------------------------------------------
# Guided merge parsing
# ---------------------------------------------------------------------------


class TestGuidedMergeParsing:
    def test_guide_basic_three_args(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge", "guide", "--allow-unrelated",
            str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 0, result.output

    def test_guide_with_output_flag(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        out = tmp_path / "result.json"
        result = RUNNER.invoke(cli, [
            "merge", "guide", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 0, result.output

    def test_guide_output_flag_before_positionals(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        out = tmp_path / "result.json"
        result = RUNNER.invoke(cli, [
            "merge", "guide", "--allow-unrelated",
            "--output", str(out),
            str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 0, result.output

    def test_guide_with_allow_plausible(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge", "guide", "--allow-unrelated",
            "--allow-plausible",
            str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 0, result.output

    def test_guide_with_allow_unrelated(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge", "guide",
            "--allow-unrelated",
            str(base), str(ours), str(theirs),
        ])
        assert result.exit_code == 0, result.output

    def test_guide_output_no_value_fails(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge", "guide", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output",
        ])
        assert result.exit_code != 0

    def test_guide_too_few_positional_args(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge", "guide", "--allow-unrelated",
            str(base), str(ours),
        ])
        assert result.exit_code == 1

    def test_guide_too_many_positional_args(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        extra = _write_als(tmp_path, "extra.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge", "guide", "--allow-unrelated",
            str(base), str(ours), str(theirs), str(extra),
        ])
        assert result.exit_code == 1

    def test_guide_unknown_option_fails(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge", "guide", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--bogus-flag",
        ])
        assert result.exit_code == 1

    def test_guide_output_not_treated_as_snapshot(self, tmp_path):
        """Output filename should not be confused with a snapshot input."""
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge", "guide", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--output", "result.json",
        ])
        assert result.exit_code == 0, result.output

    def test_plan_manifest_with_allow_plausible(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        out = tmp_path / "manifest.json"
        result = RUNNER.invoke(cli, [
            "merge", "plan", "--allow-unrelated",
            "--allow-plausible",
            str(base), str(ours), str(theirs),
            "--output", str(out),
        ])
        assert result.exit_code == 0, result.output
        assert out.exists()
        d = json.loads(out.read_text(encoding="utf-8"))
        assert d["document_type"] == "alscan-merge-manifest"

    def test_plan_manifest_unknown_option_fails(self, tmp_path):
        base = _write_als(tmp_path, "base.als", SIMPLE_XML)
        ours = _write_als(tmp_path, "ours.als", SIMPLE_XML)
        theirs = _write_als(tmp_path, "theirs.als", SIMPLE_XML)
        result = RUNNER.invoke(cli, [
            "merge", "plan", "--allow-unrelated",
            str(base), str(ours), str(theirs),
            "--bogus-flag",
        ])
        assert result.exit_code == 1
