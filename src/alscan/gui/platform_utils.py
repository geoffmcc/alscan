# SPDX-License-Identifier: GPL-3.0-only
"""Cross-platform utilities for the ALScan GUI."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

_log = logging.getLogger(__name__)


def open_folder(path: Path | str) -> None:
    """Open a folder or reveal a file in the system file manager.

    On macOS: uses 'open'
    On Windows: uses os.startfile
    On Linux: uses xdg-open

    Raises FileNotFoundError if the path does not exist.
    Launch failures are logged but not raised.
    """
    folder = str(Path(path).resolve())

    if os.name == "nt":
        os.startfile(folder)
        return

    if os.uname().sysname == "Darwin":
        cmd = ["open", folder]
    else:
        cmd = ["xdg-open", folder]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=10)
    except subprocess.SubprocessError as e:
        _log.warning("Failed to open folder %s: %s", folder, e)
