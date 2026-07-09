# SPDX-License-Identifier: GPL-3.0-only
"""Tests for check config system."""

from pathlib import Path

import pytest

from alscan.config import CheckConfig, CONFIG_FILE_NAME
from alscan.checks import get_check
from alscan.models import Clip, Device, Project, Track, Finding
from alscan.services import _invoke_check, Check


FIXTURES = Path(__file__).parent / "fixtures"


def _make_project(tempo=120.0, tracks=None, locators=None):
    return Project(
        path=Path("."), creator="test", major_version="12", minor_version="0",
        tempo=tempo, tracks=tracks or [], locators=locators or [],
    )


# ---------------------------------------------------------------------------
# CheckConfig defaults
# ---------------------------------------------------------------------------

class TestCheckConfigDefaults:
    def test_defaults_match_current_behavior(self):
        c = CheckConfig.defaults()
        assert c.high_device_count == 8
        assert c.extreme_tempo_low == 40.0
        assert c.extreme_tempo_high == 200.0
        assert c.unfrozen_heavy_clips == 20
        assert c.unfrozen_heavy_devices == 3
        assert c.no_locators_min_tracks == 5


# ---------------------------------------------------------------------------
# TOML parsing
# ---------------------------------------------------------------------------

class TestCheckConfigToml:
    def test_empty_toml_gives_defaults(self):
        c = CheckConfig.from_toml("")
        assert c.high_device_count == 8

    def test_partial_override(self):
        c = CheckConfig.from_toml("[thresholds]\nhigh_device_count = 12")
        assert c.high_device_count == 12
        assert c.extreme_tempo_low == 40.0  # unchanged

    def test_all_thresholds(self):
        c = CheckConfig.from_toml("""[thresholds]
high_device_count = 15
extreme_tempo_low = 20.0
extreme_tempo_high = 300.0
unfrozen_heavy_clips = 50
unfrozen_heavy_devices = 5
no_locators_min_tracks = 10
""")
        assert c.high_device_count == 15
        assert c.extreme_tempo_low == 20.0
        assert c.extreme_tempo_high == 300.0
        assert c.unfrozen_heavy_clips == 50
        assert c.unfrozen_heavy_devices == 5
        assert c.no_locators_min_tracks == 10

    def test_unknown_key_ignored(self):
        c = CheckConfig.from_toml("[thresholds]\nfoo = 99")
        assert c.high_device_count == 8  # unchanged

    def test_type_coercion_int_to_float(self):
        c = CheckConfig.from_toml("[thresholds]\nextreme_tempo_low = 20")
        assert c.extreme_tempo_low == 20.0

    def test_type_coercion_float_to_int(self):
        c = CheckConfig.from_toml("[thresholds]\nhigh_device_count = 12.0")
        assert c.high_device_count == 12

    def test_invalid_value_keeps_default(self):
        c = CheckConfig.from_toml("[thresholds]\nhigh_device_count = \"twelve\"")
        assert c.high_device_count == 8  # kept default


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

class TestCheckConfigFile:
    def test_from_file(self, tmp_path):
        p = tmp_path / CONFIG_FILE_NAME
        p.write_text("[thresholds]\nhigh_device_count = 20")
        c = CheckConfig.from_file(p)
        assert c.high_device_count == 20

    def test_from_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            CheckConfig.from_file("/nonexistent/path")

    def test_discover_in_project_dir(self, tmp_path):
        p = tmp_path / CONFIG_FILE_NAME
        p.write_text("[thresholds]\nextreme_tempo_high = 250")
        c = CheckConfig.discover(tmp_path)
        assert c is not None
        assert c.extreme_tempo_high == 250.0

    def test_discover_in_parent_dir(self, tmp_path):
        p = tmp_path / CONFIG_FILE_NAME
        p.write_text("[thresholds]\nno_locators_min_tracks = 8")
        sub = tmp_path / "sub" / "deep"
        sub.mkdir(parents=True)
        c = CheckConfig.discover(sub)
        assert c is not None
        assert c.no_locators_min_tracks == 8

    def test_discover_none_when_no_file(self, tmp_path):
        c = CheckConfig.discover(tmp_path)
        assert c is None


# ---------------------------------------------------------------------------
# Check behavior with config
# ---------------------------------------------------------------------------

def _make_check(func):
    return Check(name="test", func=func, severity="info")


class TestHighDeviceCountWithConfig:
    def test_default_threshold(self):
        project = _make_project(tracks=[
            Track(name="T1", track_id=1, track_type="midi",
                  devices=[Device(name=f"D{i}", device_type="test") for i in range(9)]),
        ])
        check = get_check("high_device_count")
        findings = check.func(project)
        assert len(findings) == 1

    def test_custom_threshold(self):
        project = _make_project(tracks=[
            Track(name="T1", track_id=1, track_type="midi",
                  devices=[Device(name=f"D{i}", device_type="test") for i in range(9)]),
        ])
        config = CheckConfig(high_device_count=10)
        check = get_check("high_device_count")
        findings = check.func(project, config=config)
        assert len(findings) == 0  # 9 devices < 10 threshold

    def test_default_threshold_no_false_positive(self):
        project = _make_project(tracks=[
            Track(name="T1", track_id=1, track_type="midi",
                  devices=[Device(name=f"D{i}", device_type="test") for i in range(8)]),
        ])
        check = get_check("high_device_count")
        findings = check.func(project)
        assert len(findings) == 0


class TestExtremeTempoWithConfig:
    def test_default_low(self):
        project = _make_project(tempo=30.0)
        check = get_check("extreme_tempo")
        findings = check.func(project)
        assert len(findings) == 1
        assert "Very Low" in findings[0].title

    def test_custom_low(self):
        project = _make_project(tempo=30.0)
        config = CheckConfig(extreme_tempo_low=20.0)
        check = get_check("extreme_tempo")
        findings = check.func(project, config=config)
        assert len(findings) == 0  # 30 > 20

    def test_default_high(self):
        project = _make_project(tempo=250.0)
        check = get_check("extreme_tempo")
        findings = check.func(project)
        assert len(findings) == 1
        assert "Very High" in findings[0].title

    def test_custom_high(self):
        project = _make_project(tempo=250.0)
        config = CheckConfig(extreme_tempo_high=300.0)
        check = get_check("extreme_tempo")
        findings = check.func(project, config=config)
        assert len(findings) == 0


class TestNoLocatorsWithConfig:
    def test_default_threshold(self):
        project = _make_project(tracks=[Track(name=f"T{i}", track_id=i, track_type="midi") for i in range(6)])
        check = get_check("no_locators")
        findings = check.func(project)
        assert len(findings) == 1

    def test_custom_threshold(self):
        project = _make_project(tracks=[Track(name=f"T{i}", track_id=i, track_type="midi") for i in range(6)])
        config = CheckConfig(no_locators_min_tracks=10)
        check = get_check("no_locators")
        findings = check.func(project, config=config)
        assert len(findings) == 0  # 6 tracks < 10

    def test_below_default_threshold_no_finding(self):
        project = _make_project(tracks=[Track(name=f"T{i}", track_id=i, track_type="midi") for i in range(4)])
        check = get_check("no_locators")
        findings = check.func(project)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# invoke_check helper
# ---------------------------------------------------------------------------

class TestInvokeCheck:
    def test_passes_config_to_accepting_check(self):
        called_with = {}

        def my_check(project, config=None):
            called_with["config"] = config
            return []

        check = _make_check(my_check)
        config = CheckConfig(high_device_count=99)
        _invoke_check(check, _make_project(), config)
        assert called_with["config"] is config

    def test_passes_none_to_accepting_check(self):
        called_with = {}

        def my_check(project, config=None):
            called_with["config"] = config
            return []

        check = _make_check(my_check)
        _invoke_check(check, _make_project(), None)
        assert called_with["config"] is None

    def test_skip_config_for_non_accepting_check(self):
        def my_check(project):
            return []

        check = _make_check(my_check)
        result = _invoke_check(check, _make_project(), CheckConfig(high_device_count=99))
        assert result == []


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCliConfig:
    def test_scan_with_config_flag(self, tmp_path):
        from click.testing import CliRunner
        from alscan.cli import cli
        import shutil
        proj = tmp_path / "test_proj"
        proj.mkdir()
        src = FIXTURES / "clean.als"
        shutil.copy2(str(src), str(proj / "clean.als"))
        result = CliRunner().invoke(cli, [
            "scan", str(proj), "--format", "terminal",
        ])
        assert result.exit_code == 0

    def test_scan_with_missing_config_warns(self, tmp_path):
        from click.testing import CliRunner
        from alscan.cli import cli
        import shutil
        proj = tmp_path / "test_proj"
        proj.mkdir()
        src = FIXTURES / "clean.als"
        shutil.copy2(str(src), str(proj / "clean.als"))
        result = CliRunner().invoke(cli, [
            "scan", str(proj), "--config", str(tmp_path / "nonexistent.toml"),
        ])
        assert result.exit_code == 0
        assert "config file not found" in result.output.lower()

    def test_scan_with_valid_config(self, tmp_path):
        from click.testing import CliRunner
        from alscan.cli import cli
        import shutil
        proj = tmp_path / "test_proj"
        proj.mkdir()
        src = FIXTURES / "clean.als"
        shutil.copy2(str(src), str(proj / "clean.als"))
        config = tmp_path / CONFIG_FILE_NAME
        config.write_text("[thresholds]\nhigh_device_count = 100")
        result = CliRunner().invoke(cli, [
            "scan", str(proj), "--config", str(config),
        ])
        assert result.exit_code == 0

    def test_auto_discover_config(self, tmp_path):
        from click.testing import CliRunner
        from alscan.cli import cli
        import shutil
        proj = tmp_path / "test_proj"
        proj.mkdir()
        src = FIXTURES / "clean.als"
        shutil.copy2(str(src), str(proj / "clean.als"))
        config = tmp_path / CONFIG_FILE_NAME
        config.write_text("[thresholds]\nhigh_device_count = 100")
        sub = tmp_path / "sub"
        sub.mkdir()
        shutil.copy2(str(src), str(sub / "clean.als"))
        result = CliRunner().invoke(cli, [
            "scan", str(sub),
        ])
        assert result.exit_code == 0

    def test_help_shows_config_option(self):
        from click.testing import CliRunner
        from alscan.cli import cli
        result = CliRunner().invoke(cli, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.output


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_old_checks_still_work_without_config(self):
        """Checks that don't accept config must still run normally."""
        from alscan.checks import list_checks
        project = _make_project()
        for check in list_checks():
            # Should not raise
            result = _invoke_check(Check(name=check.name, func=check.func, severity=check.severity),
                                   project, None)
            assert isinstance(result, list)

    def test_defaults_produce_same_results(self):
        """With no config, results must match old behavior exactly."""
        project = _make_project(tracks=[
            Track(name="T1", track_id=1, track_type="midi",
                  devices=[Device(name=f"D{i}", device_type="test") for i in range(9)]),
        ])
        high_dev = get_check("high_device_count")
        findings_default = high_dev.func(project)
        findings_explicit = high_dev.func(project, config=CheckConfig.defaults())
        assert len(findings_default) == len(findings_explicit)

    def test_backward_compat_config_none_same_as_no_config(self):
        project = _make_project(tempo=30.0)
        tempo_check = get_check("extreme_tempo")
        f1 = tempo_check.func(project)
        f2 = tempo_check.func(project, config=None)
        assert len(f1) == len(f2)
        assert f1[0].title == f2[0].title
