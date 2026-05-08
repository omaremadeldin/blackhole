from __future__ import annotations

from pathlib import Path

import pytest

from blackhole.cli import parse_command
from blackhole.commands import InstallServiceCommandSpec, MountCommandSpec, RemoveServiceCommandSpec

pytestmark = pytest.mark.unit


def test_mount_file_parses_with_override_and_persistent() -> None:
    command = parse_command([
        "mount",
        "file",
        "--target",
        "/tmp/target.txt",
        "--override-file",
        "/tmp/source.txt",
        "--persistent",
        "--service-name",
        "my-mount",
    ])

    assert isinstance(command, MountCommandSpec)
    assert command.mode == "single-file"
    assert command.target_file == Path("/tmp/target.txt").resolve(strict=False)
    assert command.override_file == Path("/tmp/source.txt").resolve(strict=False)
    assert command.mount_point == Path("/tmp").resolve(strict=False)
    assert command.persistent is True
    assert command.service_name == "my-mount"


def test_mount_dir_parses_with_override() -> None:
    command = parse_command([
        "mount",
        "dir",
        "--mount-point",
        "/mnt/blackhole",
        "--source-dir",
        "/srv/source",
        "--override-dir",
        "/srv/override",
    ])

    assert isinstance(command, MountCommandSpec)
    assert command.mode == "directory"
    assert command.mount_point == Path("/mnt/blackhole").resolve(strict=False)
    assert command.source_dir == Path("/srv/source").resolve(strict=False)
    assert command.override_dir == Path("/srv/override").resolve(strict=False)
    assert command.persistent is False
    assert command.service_name is None


def test_mount_requires_mode_subcommand() -> None:
    with pytest.raises(SystemExit):
        parse_command(["mount"])


def test_service_name_requires_persistent() -> None:
    with pytest.raises(SystemExit):
        parse_command([
            "mount",
            "dir",
            "--mount-point",
            "/mnt/blackhole",
            "--source-dir",
            "/srv/source",
            "--service-name",
            "custom",
        ])


def test_remove_subcommand_parses() -> None:
    command = parse_command(["unmount", "test-instance"])

    assert isinstance(command, RemoveServiceCommandSpec)
    assert command.name == "test-instance"


def test_install_service_subcommand_parses() -> None:
    command = parse_command(["install-service"])

    assert isinstance(command, InstallServiceCommandSpec)


def test_legacy_mount_flags_are_rejected() -> None:
    with pytest.raises(SystemExit):
        parse_command(["mount", "--file", "/tmp/target.txt"])

    with pytest.raises(SystemExit):
        parse_command([
            "mount",
            "--mount",
            "/mnt/blackhole",
            "--source",
            "/srv/source",
        ])
