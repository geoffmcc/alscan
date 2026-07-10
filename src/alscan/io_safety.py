# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

ABLETON_CONTENT_EXTENSIONS = {".als", ".wav", ".aiff", ".aif", ".asd", ".adg", ".amxd", ".alp"}


@dataclass
class SourceIdentity:
    path: Path
    resolved: Path
    size: int
    mtime: float
    sha256: str
    device: int
    inode: int


def capture_identity(path: str | Path) -> SourceIdentity:
    p = Path(path)
    resolved = p.resolve()
    st = resolved.stat()
    sha256 = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return SourceIdentity(
        path=p,
        resolved=resolved,
        size=st.st_size,
        mtime=st.st_mtime,
        sha256=sha256,
        device=st.st_dev,
        inode=st.st_ino,
    )


def verify_stable(before: SourceIdentity) -> None:
    after = capture_identity(before.path)
    mismatches = []
    if after.size != before.size:
        mismatches.append(f"size changed: {before.size} -> {after.size}")
    if after.sha256 != before.sha256:
        mismatches.append(f"sha256 changed: {before.sha256[:12]}... -> {after.sha256[:12]}...")
    if after.mtime != before.mtime:
        mismatches.append(f"mtime changed: {before.mtime} -> {after.mtime}")
    if mismatches:
        raise OSError(
            f"Source file changed during operation: {before.path}\n"
            + "\n".join(f"  {m}" for m in mismatches)
        )


def are_same_file(a: Path, b: Path) -> bool:
    a_r = a.resolve()
    b_r = b.resolve()
    if a_r == b_r:
        return True
    try:
        if os.path.samefile(str(a_r), str(b_r)):
            return True
    except OSError:
        pass
    try:
        sa, sb = a_r.stat(), b_r.stat()
        if sa.st_dev == sb.st_dev and sa.st_ino == sb.st_ino and sa.st_ino != 0:
            return True
    except OSError:
        pass
    return False


def check_aliases(paths: list[Path]) -> list[tuple[Path, Path, str]]:
    result = []
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            reason = None
            a, b = paths[i], paths[j]
            if a.resolve() == b.resolve():
                reason = "resolved path equality"
            elif are_same_file(a, b):
                reason = "same file (device+inode)"
            if reason:
                result.append((a, b, reason))
    return result


def validate_parent(p: Path) -> None:
    parts = p.absolute().parts
    for i in range(1, len(parts)):
        check = Path(*parts[: i + 1])
        if check.is_symlink() or check.is_junction():
            raise PermissionError(
                f"Path component is a symlink or junction; refusing to follow: {check}"
            )


def safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def atomic_publish(temp_path: Path, dest: Path) -> None:
    try:
        dest_s = str(dest)
        if dest.is_symlink():
            raise OSError(
                f"Refusing to publish to a symlink destination: {dest}"
            )
        if hasattr(dest, "is_junction") and dest.is_junction():
            raise OSError(
                f"Refusing to publish to a junction destination: {dest}"
            )
    except OSError:
        raise
    try:
        os.link(str(temp_path), str(dest))
    except FileExistsError:
        raise
    except OSError:
        import shutil
        shutil.copy2(str(temp_path), str(dest))
    finally:
        safe_unlink(temp_path)


def atomic_write(dest: Path, content: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        dir=str(dest.parent),
        prefix=f".{dest.name}.tmp.",
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        atomic_publish(tmp_path, dest)
    except BaseException:
        safe_unlink(tmp_path)
        raise


def validate_output_dest(
    dest: Path,
    sources: list[Path],
    reject_ableton_exts: bool = True,
    reject_backup: bool = True,
    reject_alscan: bool = True,
) -> Path:
    validate_parent(dest)
    dest = dest.resolve()
    for src in sources:
        if are_same_file(dest, src):
            raise ValueError(
                f"Output destination is the same file as input: {dest}"
            )
    if reject_ableton_exts and dest.suffix.lower() in ABLETON_CONTENT_EXTENSIONS:
        raise ValueError(
            f"Refusing to write with a '{dest.suffix}' extension "
            f"(reserved for Ableton content)"
        )
    for parent in dest.parents:
        base = parent.name
        if reject_backup and base == "Backup":
            raise ValueError(f"Refusing to write inside the 'Backup' directory")
        if reject_alscan and base == ".alscan":
            raise ValueError(f"Refusing to write inside the '.alscan' directory")
    if dest.exists():
        raise FileExistsError(
            f"Output file already exists: {dest}\n"
            f"  Delete it manually or use a different output path."
        )
    return dest
