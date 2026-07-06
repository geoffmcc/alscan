from __future__ import annotations

from pathlib import Path


def find_als_file(path: str | Path) -> Path | None:
    p = Path(path).resolve()
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
    p = Path(path).resolve()
    if p.suffix.lower() == ".als":
        return p.parent if p.exists() else None
    if p.is_dir():
        if list(p.glob("*.als")):
            return p
        return None
    return None


def find_projects(root: str | Path) -> list[Path]:
    root = Path(root).resolve()
    if not root.is_dir():
        return []
    projects = []
    for als_file in root.rglob("*.als"):
        project_dir = als_file.parent
        if project_dir not in projects:
            projects.append(project_dir)
    return sorted(projects)


def is_project_folder(path: Path) -> bool:
    return path.is_dir() and bool(list(path.glob("*.als")))
