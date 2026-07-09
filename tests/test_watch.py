# SPDX-License-Identifier: GPL-3.0-only
"""Tests for watch mode."""

import time
from pathlib import Path

import pytest

from alscan.watch import (
    ProjectWatch,
    _discover_projects,
    _file_stable,
    _finding_key,
    watch_directory,
)
from alscan.models import Finding


class TestFileStable:
    def test_stable_file(self, tmp_path):
        f = tmp_path / "test.als"
        f.write_text("hello")
        assert _file_stable(f, len("hello"))

    def test_file_growing(self, tmp_path):
        f = tmp_path / "test.als"
        f.write_text("hello")
        import threading
        result = [True]

        def grow():
            import time
            time.sleep(0.3)
            f.write_text("hello world")
            result[0] = False

        t = threading.Thread(target=grow, daemon=True)
        t.start()
        stable = _file_stable(f, len("hello"))
        t.join()
        assert not stable or result[0]


class TestFindingKey:
    def test_key_uniqueness(self):
        f1 = Finding(severity="error", check_name="missing_samples",
                    title="Missing Sample", message="a", location="Track: T1")
        f2 = Finding(severity="error", check_name="missing_samples",
                    title="Missing Sample", message="a", location="Track: T1")
        assert _finding_key(f1) == _finding_key(f2)

    def test_key_different_check(self):
        f1 = Finding(severity="error", check_name="a", title="T", message="m",
                    location="L")
        f2 = Finding(severity="error", check_name="b", title="T", message="m",
                    location="L")
        assert _finding_key(f1) != _finding_key(f2)


class TestDiscoverProjects:
    def test_empty_dir(self, tmp_path):
        projects = _discover_projects(tmp_path)
        assert len(projects) == 0

    def test_single_project(self, tmp_path):
        proj = tmp_path / "My Song"
        proj.mkdir()
        (proj / "My Song.als").write_text("test")
        projects = _discover_projects(tmp_path)
        assert len(projects) == 1
        assert "My Song" in projects

    def test_multiple_projects(self, tmp_path):
        for name in ["Song A", "Song B"]:
            proj = tmp_path / name
            proj.mkdir()
            (proj / f"{name}.als").write_text("test")
        projects = _discover_projects(tmp_path)
        assert len(projects) == 2

    def test_skips_multiple_als_in_project(self, tmp_path):
        proj = tmp_path / "Weird Project"
        proj.mkdir()
        (proj / "song1.als").write_text("test")
        (proj / "song2.als").write_text("test")
        projects = _discover_projects(tmp_path)
        assert len(projects) == 0


class TestProjectWatch:
    def test_default_fields(self):
        pw = ProjectWatch(als_path=Path("/tmp/test.als"))
        assert pw.last_mtime == 0.0
        assert pw.debounce_until == 0.0
        assert pw.last_findings == set()
        assert pw.last_scan_time == 0.0


class TestCliWatch:
    def test_help_shows_watch(self):
        from click.testing import CliRunner
        from alscan.cli import cli
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "watch" in result.output

    def test_watch_requires_directory(self):
        from click.testing import CliRunner
        from alscan.cli import cli
        result = CliRunner().invoke(cli, ["watch", "/nonexistent/path"])
        assert result.exit_code == 1
        assert "not a directory" in result.output.lower()

    def test_watch_help(self):
        from click.testing import CliRunner
        from alscan.cli import cli
        result = CliRunner().invoke(cli, ["watch", "--help"])
        assert result.exit_code == 0
        assert "Watch" in result.output
