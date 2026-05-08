from __future__ import annotations

import os
from pathlib import Path

import pytest

from blackhole.config import BlackholeConfig
from blackhole.pathing import resolve_source_path

pytestmark = pytest.mark.unit


def test_resolve_source_path_maps_directory_requests(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    mount_point = tmp_path / "mount"
    mount_point.mkdir()

    config = BlackholeConfig(
        mode="directory",
        mount_point=mount_point,
        target_file=None,
        override_file=None,
        source_dir=source_dir,
        override_dir=None,
        persistent=False,
    )

    resolved = resolve_source_path("/a/b.txt", config)

    assert resolved == (source_dir / "a" / "b.txt")


def test_resolve_source_path_rejects_traversal(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    mount_point = tmp_path / "mount"
    mount_point.mkdir()

    config = BlackholeConfig(
        mode="directory",
        mount_point=mount_point,
        target_file=None,
        override_file=None,
        source_dir=source_dir,
        override_dir=None,
        persistent=False,
    )

    with pytest.raises(PermissionError):
        resolve_source_path("/../outside.txt", config)


def test_resolve_source_path_directory_uses_override_when_present(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    override_dir = tmp_path / "override"
    override_dir.mkdir()
    mount_point = tmp_path / "mount"
    mount_point.mkdir()
    (source_dir / "file.txt").write_text("original", encoding="utf-8")
    (override_dir / "file.txt").write_text("override", encoding="utf-8")

    config = BlackholeConfig(
        mode="directory",
        mount_point=mount_point,
        target_file=None,
        override_file=None,
        source_dir=source_dir,
        override_dir=override_dir,
        persistent=False,
    )

    resolved = resolve_source_path("/file.txt", config)

    assert resolved == (override_dir / "file.txt").resolve()


def test_resolve_source_path_directory_falls_back_to_source_without_override_file(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    override_dir = tmp_path / "override"
    override_dir.mkdir()
    mount_point = tmp_path / "mount"
    mount_point.mkdir()
    (source_dir / "only-in-source.txt").write_text("real", encoding="utf-8")

    config = BlackholeConfig(
        mode="directory",
        mount_point=mount_point,
        target_file=None,
        override_file=None,
        source_dir=source_dir,
        override_dir=override_dir,
        persistent=False,
    )

    resolved = resolve_source_path("/only-in-source.txt", config)

    assert resolved == (source_dir / "only-in-source.txt").resolve()


def test_resolve_source_path_single_file_target_uses_override(tmp_path: Path) -> None:
    target_file = tmp_path / "dir" / "target.txt"
    target_file.parent.mkdir()
    target_file.write_text("original", encoding="utf-8")
    override_file = tmp_path / "override.txt"
    override_file.write_text("override", encoding="utf-8")

    fd = os.open(target_file.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        config = BlackholeConfig(
            mode="single-file",
            mount_point=target_file.parent,
            target_file=target_file,
            override_file=override_file,
            source_dir=None,
            override_dir=None,
            persistent=False,
            backing_dir_fd=fd,
        )

        resolved = resolve_source_path("/target.txt", config)

        assert resolved == override_file
    finally:
        os.close(fd)


def test_resolve_source_path_single_file_target_no_override_returns_via_backing_fd(
    tmp_path: Path,
) -> None:
    target_file = tmp_path / "dir" / "target.txt"
    target_file.parent.mkdir()
    target_file.write_text("original", encoding="utf-8")

    fd = os.open(target_file.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        config = BlackholeConfig(
            mode="single-file",
            mount_point=target_file.parent,
            target_file=target_file,
            override_file=None,
            source_dir=None,
            override_dir=None,
            persistent=False,
            backing_dir_fd=fd,
        )

        resolved = resolve_source_path("/target.txt", config)

        assert resolved == Path(f"/proc/self/fd/{fd}") / "target.txt"
    finally:
        os.close(fd)
