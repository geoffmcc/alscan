# SPDX-License-Identifier: GPL-3.0-only
"""Tests for sample search and candidate suggestions."""

from pathlib import Path

import pytest

from alscan.search import SearchCandidate, search_sample, known_sample_dirs


# ---------------------------------------------------------------------------
# SearchCandidate
# ---------------------------------------------------------------------------

class TestSearchCandidate:
    def test_label(self):
        c = SearchCandidate(path="/tmp/kick.wav", confidence="exact",
                           match_type="filename_and_hash")
        assert c.label == "kick.wav"

    def test_confidence_order(self):
        candidates = [
            SearchCandidate(path="/a/weak.wav", confidence="weak", match_type="filename"),
            SearchCandidate(path="/b/exact.wav", confidence="exact", match_type="filename_and_hash"),
            SearchCandidate(path="/c/name.wav", confidence="name", match_type="filename"),
        ]
        from alscan.search import _rank_candidates
        ranked = _rank_candidates(candidates)
        assert ranked[0].confidence == "exact"
        assert ranked[1].confidence == "name"
        assert ranked[2].confidence == "weak"


# ---------------------------------------------------------------------------
# search_sample
# ---------------------------------------------------------------------------

class TestSearchSample:
    def test_exact_filename_match(self, tmp_path):
        d = tmp_path / "samples"
        d.mkdir()
        (d / "kick.wav").write_text("audio")
        results = search_sample("kick.wav", [str(d)])
        assert len(results) == 1
        assert results[0].confidence == "name"
        assert results[0].match_type == "filename"

    def test_exact_filename_and_size_match(self, tmp_path):
        d = tmp_path / "samples"
        d.mkdir()
        f = d / "kick.wav"
        f.write_bytes(b"\x00" * 1024)
        results = search_sample("kick.wav", [str(d)], file_size=1024)
        assert len(results) == 1
        assert results[0].confidence == "size"
        assert results[0].match_type == "filename_and_size"

    def test_exact_filename_and_hash_match(self, tmp_path):
        d = tmp_path / "samples"
        d.mkdir()
        f = d / "kick.wav"
        data = b"sample data"
        f.write_bytes(data)
        import hashlib
        h = hashlib.sha256(data).hexdigest()
        results = search_sample("kick.wav", [str(d)], sha256=h)
        assert len(results) >= 1
        exact = [c for c in results if c.confidence == "exact"]
        assert len(exact) == 1

    def test_no_match(self, tmp_path):
        d = tmp_path / "samples"
        d.mkdir()
        (d / "snare.wav").write_text("audio")
        results = search_sample("kick.wav", [str(d)])
        assert len(results) == 0

    def test_case_insensitive(self, tmp_path):
        d = tmp_path / "samples"
        d.mkdir()
        (d / "KICK.WAV").write_text("audio")
        results = search_sample("kick.wav", [str(d)])
        assert len(results) >= 1

    def test_candidate_limit(self, tmp_path):
        d = tmp_path / "samples"
        d.mkdir()
        for i in range(20):
            (d / f"kick_{i}.wav").write_text("audio")
        results = search_sample("kick_", [str(d)], candidate_limit=3)
        assert len(results) <= 3

    def test_nonexistent_directory_skipped(self, tmp_path):
        results = search_sample("kick.wav", [str(tmp_path / "nonexistent")])
        assert len(results) == 0

    def test_subdirectory_recursive(self, tmp_path):
        d = tmp_path / "samples"
        d.mkdir()
        sub = d / "drums"
        sub.mkdir()
        (sub / "kick.wav").write_text("audio")
        results = search_sample("kick.wav", [str(d)])
        assert len(results) == 1

    def test_size_mismatch_no_size_match(self, tmp_path):
        d = tmp_path / "samples"
        d.mkdir()
        f = d / "kick.wav"
        f.write_bytes(b"\x00" * 2048)
        results = search_sample("kick.wav", [str(d)], file_size=1024)
        assert len(results) == 1
        assert results[0].confidence == "name"  # size did not match

    def test_candidate_limit_exact_first(self, tmp_path):
        d = tmp_path / "samples"
        d.mkdir()
        (d / "kick.wav").write_text("audio")
        (d / "kick_backup.wav").write_text("audio")
        results = search_sample("kick.wav", [str(d)], candidate_limit=1)
        assert len(results) == 1
        assert results[0].label == "kick.wav"


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCliSearchPaths:
    def test_help_shows_search_options(self):
        from click.testing import CliRunner
        from alscan.cli import cli
        result = CliRunner().invoke(cli, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--search-paths" in result.output
        assert "--no-default-paths" in result.output

    def test_scan_with_search_paths(self, tmp_path):
        from click.testing import CliRunner
        from alscan.cli import cli
        import shutil
        proj = tmp_path / "test_proj"
        proj.mkdir()
        src = Path(__file__).parent / "fixtures" / "clean.als"
        shutil.copy2(str(src), str(proj / "clean.als"))
        result = CliRunner().invoke(cli, [
            "scan", str(proj), "--search-paths", "/nonexistent/path",
        ])
        assert result.exit_code == 0

    def test_scan_with_no_default_paths(self, tmp_path):
        from click.testing import CliRunner
        from alscan.cli import cli
        import shutil
        proj = tmp_path / "test_proj"
        proj.mkdir()
        src = Path(__file__).parent / "fixtures" / "clean.als"
        shutil.copy2(str(src), str(proj / "clean.als"))
        result = CliRunner().invoke(cli, [
            "scan", str(proj), "--no-default-paths",
        ])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# known_sample_dirs
# ---------------------------------------------------------------------------

class TestKnownSampleDirs:
    def test_returns_list(self):
        dirs = known_sample_dirs()
        assert isinstance(dirs, list)
        for d in dirs:
            assert d.is_dir()


# ---------------------------------------------------------------------------
# Finding model with candidates
# ---------------------------------------------------------------------------

class TestFindingCandidates:
    def test_finding_default_no_candidates(self):
        from alscan.models import Finding
        f = Finding(severity="info", check_name="test", title="T", message="M")
        assert f.candidates == []

    def test_finding_with_candidates(self):
        from alscan.models import Finding
        f = Finding(
            severity="error", check_name="missing_samples",
            title="Missing Sample", message="not found",
            candidates=[{"path": "/tmp/kick.wav", "confidence": "name"}],
        )
        assert len(f.candidates) == 1
        assert f.candidates[0]["confidence"] == "name"

    def test_finding_dict_includes_candidates(self):
        from alscan.models import Finding
        f = Finding(
            severity="error", check_name="missing_samples",
            title="Missing", message="msg",
            candidates=[{"path": "/tmp/x.wav", "confidence": "exact"}],
        )
        d = f.dict()
        assert "candidates" in d
        assert len(d["candidates"]) == 1

    def test_finding_dict_excludes_empty_candidates(self):
        from alscan.models import Finding
        f = Finding(severity="info", check_name="test", title="T", message="M")
        d = f.dict()
        assert "candidates" not in d


# ---------------------------------------------------------------------------
# missing_samples with search
# ---------------------------------------------------------------------------

class TestMissingSamplesWithSearch:
    def test_search_hooks_into_check(self, tmp_path):
        from alscan.models import Project, Track, Clip, SampleRef
        from alscan.checks.samples import check_missing_samples
        d = tmp_path / "samples"
        d.mkdir()
        (d / "kick.wav").write_text("audio")

        ref = SampleRef(name="kick.wav", path=str(tmp_path / "missing" / "kick.wav"),
                       original_file_size=0)
        clip = Clip(name="Clip", clip_type="audio", sample_ref=ref)
        track = Track(name="Audio", track_id=1, track_type="audio", clips=[clip])
        proj = Project(path=tmp_path, creator="test", tracks=[track])

        findings = check_missing_samples(proj, search_paths=[str(d)])
        assert len(findings) == 1
        assert findings[0].check_name == "missing_samples"
        assert len(findings[0].candidates) == 1
        assert findings[0].candidates[0]["confidence"] == "name"

    def test_no_search_paths_no_candidates(self, tmp_path):
        from alscan.models import Project, Track, Clip, SampleRef
        from alscan.checks.samples import check_missing_samples

        ref = SampleRef(name="kick.wav", path=str(tmp_path / "missing" / "kick.wav"))
        clip = Clip(name="Clip", clip_type="audio", sample_ref=ref)
        track = Track(name="Audio", track_id=1, track_type="audio", clips=[clip])
        proj = Project(path=tmp_path, creator="test", tracks=[track])

        findings = check_missing_samples(proj)
        assert len(findings) == 1
        assert len(findings[0].candidates) == 0
