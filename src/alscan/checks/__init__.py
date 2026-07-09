# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from alscan.models import Finding  # noqa: F401 — re-exported for check modules

Severity = Literal["error", "warning", "info", "suggestion"]


@dataclass
class Check:
    name: str
    func: Callable
    severity: Severity = "warning"
    description: str = ""


_checks: dict[str, Check] = {}


def register(
    name: str, severity: Severity = "warning", description: str = ""
) -> Callable:
    def wrapper(func: Callable) -> Callable:
        _checks[name] = Check(
            name=name, func=func, severity=severity, description=description
        )
        return func
    return wrapper


def get_check(name: str) -> Check | None:
    return _checks.get(name)


def list_checks() -> list[Check]:
    return list(_checks.values())


# Import check modules so their @register decorators fire
from alscan.checks import samples, plugins, performance, project_hygiene, duplicates, misc  # noqa: F401, E402
