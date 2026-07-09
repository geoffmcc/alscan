# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import os
import sys
from pathlib import Path


def known_plugin_dirs() -> list[Path]:
    if sys.platform == "win32":
        return _windows_plugin_dirs()
    elif sys.platform == "darwin":
        return _macos_plugin_dirs()
    return _linux_plugin_dirs()


def known_vst2_dirs() -> list[Path]:
    if sys.platform == "win32":
        return _windows_vst2_dirs()
    elif sys.platform == "darwin":
        return _macos_vst2_dirs()
    return []


def known_vst3_dirs() -> list[Path]:
    if sys.platform == "win32":
        return _windows_vst3_dirs()
    elif sys.platform == "darwin":
        return _macos_vst3_dirs()
    return _linux_vst3_dirs()


def known_au_dirs() -> list[Path]:
    if sys.platform == "darwin":
        return _macos_au_dirs()
    return []


# -- Windows -----------------------------------------------------------------

def _windows_plugin_dirs() -> list[Path]:
    pf = os.environ.get("ProgramFiles", "C:\\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    common = os.environ.get("CommonProgramFiles", "C:\\Program Files\\Common Files")
    return [
        Path(common) / "VST3",
        Path(pf) / "Steinberg" / "VST3",
        Path(pf86) / "Steinberg" / "VST3",
        Path(pf) / "VSTPlugins",
        Path(pf86) / "VSTPlugins",
    ]


def _windows_vst2_dirs() -> list[Path]:
    pf = os.environ.get("ProgramFiles", "C:\\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    return [
        Path(pf) / "Steinberg" / "VSTPlugins",
        Path(pf86) / "Steinberg" / "VSTPlugins",
        Path(pf) / "VSTPlugins",
        Path(pf86) / "VSTPlugins",
    ]


def _windows_vst3_dirs() -> list[Path]:
    return _windows_plugin_dirs()


# -- macOS -------------------------------------------------------------------

def _macos_plugin_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / "Library" / "Audio" / "Plug-Ins" / "VST3",
        home / "Library" / "Audio" / "Plug-Ins" / "VST",
        home / "Library" / "Audio" / "Plug-Ins" / "Components",
        Path("/Library/Audio/Plug-Ins/VST3"),
        Path("/Library/Audio/Plug-Ins/VST"),
        Path("/Library/Audio/Plug-Ins/Components"),
    ]


def _macos_vst2_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / "Library" / "Audio" / "Plug-Ins" / "VST",
        Path("/Library/Audio/Plug-Ins/VST"),
    ]


def _macos_vst3_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / "Library" / "Audio" / "Plug-Ins" / "VST3",
        Path("/Library/Audio/Plug-Ins/VST3"),
    ]


def _macos_au_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / "Library" / "Audio" / "Plug-Ins" / "Components",
        Path("/Library/Audio/Plug-Ins/Components"),
    ]


# -- Linux -------------------------------------------------------------------

def _linux_plugin_dirs() -> list[Path]:
    return _linux_vst3_dirs()


def _linux_vst3_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / ".vst3",
        Path("/usr/lib/vst3"),
        Path("/usr/local/lib/vst3"),
    ]
