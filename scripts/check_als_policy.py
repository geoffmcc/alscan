#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Repository .als file enforcement check.

Ensures that:
1. Only approved synthetic .als fixtures in tests/fixtures/ are tracked.
2. No real Ableton-authored .als files are committed, staged, or present
   in the working tree outside intentionally ignored local-validation dirs.
3. Every tracked .als fixture has a documented synthetic classification.

Run via: python scripts/check_als_policy.py

Exit codes:
  0 — no violations
  1 — policy violation found
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APPROVED_ALS_DIR = "tests/fixtures"
REQUIRED_CLASSIFICATION_FILE = "docs/fixture-inventory.md"


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    return result.stdout.strip()


def check_tracked_als() -> list[str]:
    """Return violations for tracked .als files outside approved dirs."""
    violations = []
    output = run_git(["ls-files", "*.als"])
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        approved = line.startswith(APPROVED_ALS_DIR + "/") or line == APPROVED_ALS_DIR
        if not approved:
            violations.append(
                f"TRACKED .als outside approved directory: {line}"
            )
    return violations


def check_staged_als() -> list[str]:
    """Return violations for staged .als files outside approved dirs."""
    violations = []
    output = run_git(["diff", "--cached", "--name-only", "--", "*.als"])
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        approved = line.startswith(APPROVED_ALS_DIR + "/") or line == APPROVED_ALS_DIR
        if not approved:
            violations.append(
                f"STAGED .als outside approved directory: {line}"
            )
    return violations


def check_untracked_als() -> list[str]:
    """Return violations for untracked .als in working tree."""
    violations = []
    for als_path in REPO_ROOT.rglob("*.als"):
        rel = als_path.relative_to(REPO_ROOT)
        rel_str = str(rel).replace("\\", "/")

        # Skip build/dist caches and .git
        if any(part.startswith(".") and part != "." for part in rel.parts):
            continue
        if "build" in rel.parts or "dist" in rel.parts or "__pycache__" in rel.parts:
            continue

        # Check if git ignores it
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(rel)],
            capture_output=True, cwd=str(REPO_ROOT),
        )
        if result.returncode == 0:
            continue  # gitignored — intentional (local validation)

        # Check if tracked
        tracked = run_git(["ls-files", "--", str(rel)])
        if tracked:
            continue  # already caught by check_tracked_als

        violations.append(
            f"UNTRACKED .als in working tree (not gitignored): {rel_str}"
        )
    return violations


def check_classification_exists() -> list[str]:
    """Return violations if fixture inventory docs are missing."""
    violations = []
    inv_path = REPO_ROOT / REQUIRED_CLASSIFICATION_FILE
    if not inv_path.exists():
        violations.append(
            f"Fixture classification document missing: {REQUIRED_CLASSIFICATION_FILE}"
        )
        return violations
    content = inv_path.read_text(encoding="utf-8")
    tracked = run_git(["ls-files", "*.als"]).splitlines()
    for line in tracked:
        line = line.strip()
        if not line:
            continue
        base = Path(line).name
        if base not in content:
            violations.append(
                f"Tracked .als '{line}' not classified in {REQUIRED_CLASSIFICATION_FILE}"
            )
    return violations


def main() -> int:
    all_violations = []
    all_violations.extend(check_tracked_als())
    all_violations.extend(check_staged_als())
    all_violations.extend(check_untracked_als())
    all_violations.extend(check_classification_exists())

    if all_violations:
        print("ALSCAN .als POLICY VIOLATIONS:")
        for v in all_violations:
            print(f"  {v}")
        print()
        print("Policy: Only synthetic .als fixtures in tests/fixtures/ may be tracked.")
        print("Real Ableton-authored .als files must never be committed to GitHub.")
        print("Local validation files should go in local-validation/ or validation/ directories.")
        return 1

    print("ALScan .als policy: OK — no violations detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
