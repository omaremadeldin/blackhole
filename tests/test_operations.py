from __future__ import annotations

from pathlib import Path

import pytest

from blackhole.config import BlackholeConfig
from blackhole.operations import BlackholeOperations

pytestmark = pytest.mark.unit


def build_directory_config(tmp_path: Path) -> BlackholeConfig:
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
    return config


def test_read_returns_source_bytes(tmp_path: Path) -> None:
    config = build_directory_config(tmp_path)
    file_path = config.source_dir / "demo.txt"
    file_path.write_bytes(b"abcdef")

    operations = BlackholeOperations(config)
    payload = operations.read("/demo.txt", size=3, offset=2, fh=0)

    assert payload == b"cde"


def test_write_returns_byte_count_without_mutation(tmp_path: Path) -> None:
    config = build_directory_config(tmp_path)
    file_path = config.source_dir / "demo.txt"
    file_path.write_text("immutable", encoding="utf-8")

    operations = BlackholeOperations(config)
    written = operations.write("/demo.txt", b"mutate", offset=0, fh=0)

    assert written == 6
    assert file_path.read_text(encoding="utf-8") == "immutable"


def test_write_on_missing_path_still_reports_success(tmp_path: Path) -> None:
    config = build_directory_config(tmp_path)
    operations = BlackholeOperations(config)

    written = operations.write("/does-not-exist.txt", b"discard", offset=0, fh=0)

    assert written == 7
    assert not (config.source_dir / "does-not-exist.txt").exists()


def test_truncate_reports_success_without_source_change(tmp_path: Path) -> None:
    config = build_directory_config(tmp_path)
    file_path = config.source_dir / "demo.txt"
    file_path.write_text("unchanged", encoding="utf-8")

    operations = BlackholeOperations(config)
    result = operations.truncate("/demo.txt", length=0)

    assert result == 0
    assert file_path.read_text(encoding="utf-8") == "unchanged"


def test_truncate_missing_path_reports_success(tmp_path: Path) -> None:
    config = build_directory_config(tmp_path)
    operations = BlackholeOperations(config)

    result = operations.truncate("/missing.txt", length=0)

    assert result == 0
    assert not (config.source_dir / "missing.txt").exists()


def test_unlink_reports_success_and_source_remains_accessible(tmp_path: Path) -> None:
    config = build_directory_config(tmp_path)
    file_path = config.source_dir / "demo.txt"
    file_path.write_text("safe", encoding="utf-8")

    operations = BlackholeOperations(config)
    result = operations.unlink("/demo.txt")

    assert result == 0
    assert file_path.read_text(encoding="utf-8") == "safe"
