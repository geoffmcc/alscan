# SPDX-License-Identifier: GPL-3.0-only
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("alscan")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
