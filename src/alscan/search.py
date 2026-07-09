# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from alscan.plugindirs import known_plugin_dirs  # noqa: F401 — re-exported


@dataclass
class SearchCandidate:
    path: str
    confidence: str  # "exact", "size", "name", "weak"
    match_type: str  # "filename", "filename_and_size", "filename_and_hash"
    file_size: int = 0
    sha256: str = ""

    @property
    def label(self) -> str:
        return str(Path(self.path).name)


def known_sample_dirs() -> list[Path]:
    dirs: list[Path] = []
    if sys.platform == "win32":
        docs = os.environ.get("USERPROFILE", "")
        if docs:
            docs_path = Path(docs) / "Documents"
            dirs.append(docs_path / "Ableton" / "User Library" / "Samples")
            dirs.append(docs_path / "Ableton" / "Factory Packs")
    elif sys.platform == "darwin":
        home = Path.home()
        dirs.append(home / "Music" / "Ableton" / "User Library" / "Samples")
        dirs.append(home / "Music" / "Ableton" / "Factory Packs")
    return [d for d in dirs if d.is_dir()]


def search_sample(
    name: str,
    search_paths: list[str | Path],
    file_size: int = 0,
    sha256: str = "",
    candidate_limit: int = 10,
    progress_cb=None,
    cancelled_cb=None,
) -> list[SearchCandidate]:
    candidates: list[SearchCandidate] = []
    name_lower = name.lower()
    seen: set[str] = set()
    patterns = [name_lower, name, name_lower + ".*", name + ".*",
                "*" + name_lower + "*", "*" + name + "*"]
    if name.upper() != name_lower and name.upper() != name:
        patterns.append(name.upper())
        patterns.append(name.upper() + ".*")
        patterns.append("*" + name.upper() + "*")
    for base_path in search_paths:
        base = Path(base_path)
        if not base.is_dir():
            continue
        for pattern in patterns:
            try:
                for match in base.rglob(pattern):
                    if cancelled_cb and cancelled_cb():
                        return _rank_candidates(candidates)[:candidate_limit]
                    mp = str(match.resolve())
                    if mp in seen:
                        continue
                    seen.add(mp)
                    if not match.is_file():
                        continue
                    _score_candidate(candidates, match, name, file_size, sha256)
            except (OSError, PermissionError):
                continue

    return _rank_candidates(candidates)[:candidate_limit]


def _score_candidate(
    candidates: list[SearchCandidate],
    match_path: Path,
    name: str,
    file_size: int,
    sha256: str,
) -> None:
    exact_name = match_path.name.lower() == name.lower()
    size_match = False
    hash_match = False

    if file_size > 0:
        try:
            size_match = match_path.stat().st_size == file_size
        except OSError:
            pass

    if sha256:
        import hashlib
        try:
            data = match_path.read_bytes()
            h = hashlib.sha256(data).hexdigest()
            hash_match = h == sha256
        except OSError:
            pass

    if hash_match:
        confidence = "exact"
        match_type = "filename_and_hash"
    elif exact_name and size_match:
        confidence = "size"
        match_type = "filename_and_size"
    elif exact_name:
        confidence = "name"
        match_type = "filename"
    else:
        confidence = "weak"
        match_type = "filename"

    candidates.append(SearchCandidate(
        path=str(match_path),
        confidence=confidence,
        match_type=match_type,
        file_size=match_path.stat().st_size if not size_match else file_size,
    ))


def _rank_candidates(candidates: list[SearchCandidate]) -> list[SearchCandidate]:
    order = {"exact": 0, "size": 1, "name": 2, "weak": 3}
    return sorted(candidates, key=lambda c: (order.get(c.confidence, 99), c.path))
