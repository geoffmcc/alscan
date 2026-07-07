from __future__ import annotations

from pathlib import Path

from alscan.io_safety import validate_parent as _validate_parent

_EXCLUDED_DIRS = {"Backup"}


def find_als_file(path: str | Path) -> Path | None:
    raw = Path(path)
    _validate_parent(raw)
    p = raw.resolve()
    if p.suffix.lower() == ".als":
        return p if p.exists() else None
    if p.is_dir():
        als_files = list(p.glob("*.als"))
        if len(als_files) == 1:
            return als_files[0]
        if len(als_files) > 1:
            return None
    return None


def find_project_dir(path: str | Path) -> Path | None:
    raw = Path(path)
    _validate_parent(raw)
    p = raw.resolve()
    if p.suffix.lower() == ".als":
        return p.parent if p.exists() else None
    if p.is_dir():
        if list(p.glob("*.als")):
            return p
        return None
    return None


def _walk_als_files(root: Path) -> list[Path]:
    results = []
    for entry in root.iterdir():
        if entry.name.startswith(".") or entry.name in _EXCLUDED_DIRS:
            continue
        if entry.is_dir():
            # Manually recurse to avoid descending into excluded dirs
            results.extend(_walk_als_files(entry))
        elif entry.suffix.lower() == ".als":
            results.append(entry)
    return results


def find_projects(root: str | Path) -> list[Path]:
    raw = Path(root)
    _validate_parent(raw)
    root = raw.resolve()
    if not root.is_dir():
        return []
    projects = []
    for als_file in _walk_als_files(root):
        project_dir = als_file.parent
        if project_dir not in projects:
            projects.append(project_dir)
    return sorted(projects)


def is_project_folder(path: Path) -> bool:
    _validate_parent(path)
    return path.is_dir() and bool(list(path.glob("*.als")))
