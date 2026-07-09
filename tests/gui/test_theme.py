# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from alscan.gui.theme import ThemeMode, apply_theme, theme_mode_from_string
from alscan.gui.theme import DARK_STYLESHEET, LIGHT_STYLESHEET


class TestThemeMode:
    def test_values(self):
        assert ThemeMode.SYSTEM.value == "system"
        assert ThemeMode.LIGHT.value == "light"
        assert ThemeMode.DARK.value == "dark"


class TestThemeModeFromString:
    def test_system(self):
        assert theme_mode_from_string("system") == ThemeMode.SYSTEM

    def test_light(self):
        assert theme_mode_from_string("light") == ThemeMode.LIGHT

    def test_dark(self):
        assert theme_mode_from_string("dark") == ThemeMode.DARK

    def test_invalid_fallback(self):
        assert theme_mode_from_string("unknown") == ThemeMode.SYSTEM


class TestApplyTheme:
    def test_dark_applies_stylesheet(self, qapp):
        apply_theme(qapp, ThemeMode.DARK)
        ss = qapp.styleSheet()
        assert len(ss) > 0
        assert "1e1e2e" in ss

    def test_light_applies_stylesheet(self, qapp):
        apply_theme(qapp, ThemeMode.LIGHT)
        ss = qapp.styleSheet()
        assert len(ss) > 0
        assert "eff1f5" in ss

    def test_stylesheets_are_valid_strings(self):
        assert isinstance(DARK_STYLESHEET, str)
        assert isinstance(LIGHT_STYLESHEET, str)
        assert len(DARK_STYLESHEET) > 500
        assert len(LIGHT_STYLESHEET) > 500
