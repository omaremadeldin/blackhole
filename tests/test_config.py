from __future__ import annotations

import pytest

from blackhole.commands import MountCommandSpec
from blackhole.config import BlackholeConfig, build_config

pytestmark = pytest.mark.unit


def test_blackhole_config_validate_single_file_requires_existing_override(
    tmp_path,
) -> None:
    target_file = tmp_path / "mount" / "target.txt"
    target_file.parent.mkdir(parents=True)

    config = BlackholeConfig(
        mode="single-file",
        mount_point=target_file.parent,
        target_file=target_file,
        override_file=tmp_path / "missing.txt",
        source_dir=None,
        override_dir=None,
        persistent=False,
    )

    with pytest.raises(ValueError):
        config.validate()


def test_build_config_normalizes_absolute_paths(tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    mount_point = tmp_path / "mount"
    mount_point.mkdir()

    command = MountCommandSpec.for_directory(
        mount_point=mount_point,
        source_dir=source_dir,
        override_dir=None,
        persistent=True,
        service_name=None,
    )

    config = build_config(command)

    assert config.mount_point == mount_point.resolve()
    assert config.source_dir == source_dir.resolve()
    assert config.persistent is True


def test_build_config_single_file_normalizes_and_validates(tmp_path) -> None:
    source_file = tmp_path / "source.txt"
    source_file.write_text("payload", encoding="utf-8")
    target_file = tmp_path / "mount" / "target.txt"
    target_file.parent.mkdir(parents=True)

    command = MountCommandSpec.for_single_file(
        target_file=target_file,
        override_file=source_file,
        persistent=False,
        service_name=None,
    )

    config = build_config(command)

    assert config.target_file == target_file.resolve()
    assert config.override_file == source_file.resolve()
    assert config.mount_point == target_file.parent.resolve()
