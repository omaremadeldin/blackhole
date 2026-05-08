from __future__ import annotations

from pathlib import Path

import pytest

from blackhole.config import BlackholeConfig
from blackhole.ephemeral_state import EphemeralState
from blackhole.operations import BlackholeOperations

pytestmark = pytest.mark.unit


def test_ephemeral_state_tracks_created_and_deleted_paths() -> None:
    state = EphemeralState()

    state.mark_created_file("/new.txt")
    state.mark_created_dir("/subdir")
    assert state.is_synthetic_file("/new.txt") is True
    assert state.is_synthetic_dir("/subdir") is True

    state.mark_deleted("/new.txt")
    assert state.is_deleted("/new.txt") is True
    assert state.is_synthetic_file("/new.txt") is False


def test_operations_create_and_mkdir_are_synthetic_only(tmp_path: Path) -> None:
    mount_point = tmp_path / "mount"
    source_dir = tmp_path / "source"
    mount_point.mkdir()
    source_dir.mkdir()

    config = BlackholeConfig(
        mode="directory",
        mount_point=mount_point,
        target_file=None,
        override_file=None,
        source_dir=source_dir,
        override_dir=None,
        persistent=False,
    )
    config.validate()

    operations = BlackholeOperations(config)
    create_result = operations.create("/new.txt", mode=0o644)
    mkdir_result = operations.mkdir("/new-dir", mode=0o755)

    assert create_result == 0
    assert mkdir_result == 0
    assert operations.state.is_synthetic_file("/new.txt") is True
    assert operations.state.is_synthetic_dir("/new-dir") is True
    assert not (source_dir / "new.txt").exists()
    assert not (source_dir / "new-dir").exists()
