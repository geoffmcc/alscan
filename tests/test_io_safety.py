"""Tests for alscan.io_safety — shared I/O safety module."""

from pathlib import Path

import pytest

from alscan.io_safety import (
    ABLETON_CONTENT_EXTENSIONS,
    capture_identity,
    verify_stable,
    are_same_file,
    check_aliases,
    validate_parent,
    safe_unlink,
    atomic_write,
    atomic_publish,
    validate_output_dest,
)


def test_ableton_extensions():
    assert ".als" in ABLETON_CONTENT_EXTENSIONS
    assert ".wav" in ABLETON_CONTENT_EXTENSIONS
    assert ".txt" not in ABLETON_CONTENT_EXTENSIONS
    assert ".html" not in ABLETON_CONTENT_EXTENSIONS


def test_capture_identity(tmp_path):
    f = tmp_path / "test.als"
    f.write_text("hello world")
    identity = capture_identity(f)
    assert identity.path == f
    assert identity.resolved == f.resolve()
    assert identity.size == 11
    assert identity.sha256 == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_verify_stable_unchanged(tmp_path):
    f = tmp_path / "test.als"
    f.write_text("content")
    identity = capture_identity(f)
    verify_stable(identity)


def test_verify_stable_changed_size(tmp_path):
    f = tmp_path / "test.als"
    f.write_text("content")
    identity = capture_identity(f)
    f.write_text("modified content")
    with pytest.raises(OSError, match="size changed"):
        verify_stable(identity)


def test_verify_stable_changed_content(tmp_path):
    f = tmp_path / "test.als"
    f.write_text("content")
    identity = capture_identity(f)
    f.write_text("content!")
    with pytest.raises(OSError, match="sha256 changed"):
        verify_stable(identity)


def test_are_same_file_same_path(tmp_path):
    f = tmp_path / "a.als"
    f.write_text("data")
    assert are_same_file(f, f)


def test_are_same_file_different(tmp_path):
    a = tmp_path / "a.als"
    b = tmp_path / "b.als"
    a.write_text("data")
    b.write_text("data")
    assert not are_same_file(a, b)


def test_are_same_file_hard_link(tmp_path):
    a = tmp_path / "a.als"
    a.write_text("data")
    b = tmp_path / "b.als"
    b.hardlink_to(a)
    assert are_same_file(a, b)


def test_check_aliases_empty():
    assert check_aliases([]) == []


def test_check_aliases_no_match(tmp_path):
    a = tmp_path / "a.als"
    b = tmp_path / "b.als"
    a.write_text("data")
    b.write_text("other")
    assert check_aliases([a, b]) == []


def test_check_aliases_hard_link(tmp_path):
    a = tmp_path / "a.als"
    a.write_text("data")
    b = tmp_path / "b.als"
    b.hardlink_to(a)
    result = check_aliases([a, b])
    assert len(result) == 1
    assert result[0][2] == "same file (device+inode)"


def test_validate_parent_no_symlink(tmp_path):
    f = tmp_path / "sub" / "test.als"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("")
    validate_parent(f)


def test_validate_parent_rejects_symlink(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("data")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(PermissionError, match="symlink"):
        validate_parent(link)


def test_safe_unlink_exists(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("data")
    safe_unlink(f)
    assert not f.exists()


def test_safe_unlink_missing(tmp_path):
    f = tmp_path / "nonexistent.txt"
    safe_unlink(f)


def test_atomic_write_creates_file(tmp_path):
    dest = tmp_path / "report.html"
    atomic_write(dest, "content")
    assert dest.read_text() == "content"
    stale = list(tmp_path.glob(".*.tmp.*"))
    assert len(stale) == 0


def test_atomic_write_creates_parent_dirs(tmp_path):
    dest = tmp_path / "sub" / "nested" / "report.html"
    atomic_write(dest, "hello")
    assert dest.read_text() == "hello"
    stale = list(tmp_path.glob("**/.*.tmp.*"))
    assert len(stale) == 0


def test_atomic_write_no_overwrite(tmp_path):
    dest = tmp_path / "report.html"
    dest.write_text("existing")
    with pytest.raises(FileExistsError):
        atomic_write(dest, "new content")
    assert dest.read_text() == "existing"
    stale = list(tmp_path.glob(".*.tmp.*"))
    assert len(stale) == 0


def test_atomic_publish_cleanup_on_error(tmp_path):
    dest = tmp_path / "report.html"
    dest.write_text("existing")
    temp = tmp_path / ".tempfile.tmp"
    temp.write_text("temp")
    with pytest.raises(FileExistsError):
        atomic_publish(temp, dest)
    assert dest.read_text() == "existing"
    assert not temp.exists()


def test_validate_output_dest_rejects_ableton_ext(tmp_path):
    src = tmp_path / "project.als"
    src.write_text("")
    with pytest.raises(ValueError, match="Ableton content"):
        validate_output_dest(tmp_path / "report.wav", [src])


def test_validate_output_dest_rejects_existing(tmp_path):
    src = tmp_path / "project.als"
    src.write_text("")
    existing = tmp_path / "report.html"
    existing.write_text("data")
    with pytest.raises(FileExistsError):
        validate_output_dest(existing, [src])


def test_validate_output_dest_rejects_backup(tmp_path):
    src = tmp_path / "project.als"
    src.write_text("")
    backup = tmp_path / "Backup" / "report.html"
    backup.parent.mkdir()
    with pytest.raises(ValueError, match="Backup"):
        validate_output_dest(backup, [src])


def test_validate_output_dest_rejects_alscan_by_default(tmp_path):
    src = tmp_path / "project.als"
    src.write_text("")
    alscan_dir = tmp_path / ".alscan" / "plan.json"
    alscan_dir.parent.mkdir()
    with pytest.raises(ValueError, match=".alscan"):
        validate_output_dest(alscan_dir, [src])


def test_validate_output_dest_allows_alscan_when_requested(tmp_path):
    src = tmp_path / "project.als"
    src.write_text("")
    alscan_dir = tmp_path / ".alscan" / "plan.json"
    alscan_dir.parent.mkdir()
    result = validate_output_dest(alscan_dir, [src], reject_alscan=False)
    assert result == alscan_dir.resolve()


def test_validate_output_dest_rejects_source_alias(tmp_path):
    src = tmp_path / "project.als"
    src.write_text("")
    with pytest.raises(ValueError, match="same file as input"):
        validate_output_dest(src, [src])
