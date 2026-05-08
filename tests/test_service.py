"""Tests for blackhole.service module."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from blackhole.config import BlackholeConfig

pytestmark = pytest.mark.unit
from blackhole.service import (
    derive_instance_name,
    install_template,
    register,
    unregister,
)


def test_install_template_creates_directory_and_file(tmp_path: Path) -> None:
    """install_template creates ~/.config/systemd/user/ and writes the template."""
    config_home = tmp_path / "config"
    result = install_template(config_home)

    expected_path = config_home / "systemd" / "user" / "blackhole@.service"
    assert result == expected_path
    assert result.exists()
    assert "Description=blackhole" in result.read_text()
    assert "%h/.config/blackhole/%i.env" in result.read_text()


def test_install_template_overwrites_existing(tmp_path: Path) -> None:
    """install_template overwrites an existing template file."""
    config_home = tmp_path / "config"
    unit_dir = config_home / "systemd" / "user"
    unit_dir.mkdir(parents=True)

    unit_file = unit_dir / "blackhole@.service"
    unit_file.write_text("old content")

    result = install_template(config_home)

    assert result.read_text() != "old content"
    assert "Description=blackhole" in result.read_text()


def test_derive_instance_name_basic() -> None:
    """derive_instance_name produces expected slug."""
    result = derive_instance_name(Path("/mnt/blackhole/foo"))
    assert result == "mnt-blackhole-foo"


def test_derive_instance_name_home_directory() -> None:
    """derive_instance_name handles home directory paths."""
    result = derive_instance_name(Path("/home/user/mnt/foo"))
    assert result == "home-user-mnt-foo"


def test_derive_instance_name_trailing_slash() -> None:
    """derive_instance_name strips trailing slashes."""
    result = derive_instance_name(Path("/mnt/foo/"))
    assert result == "mnt-foo"


def test_register_directory_mode_no_override(tmp_path: Path) -> None:
    """register writes env file and calls systemctl for directory mode."""
    config_home = tmp_path / "config"
    source_dir = tmp_path / "source"
    mount_point = tmp_path / "mount"
    source_dir.mkdir()
    mount_point.mkdir()

    config = BlackholeConfig(
        mode="directory",
        mount_point=mount_point,
        target_file=None,
        override_file=None,
        source_dir=source_dir,
        override_dir=None,
        persistent=True,
    )

    with mock.patch("blackhole.service.subprocess.run") as mock_run:
        register(config, "test-mount", config_home)

    # Check env file was written.
    env_file = config_home / "blackhole" / "test-mount.env"
    assert env_file.exists()
    env_content = env_file.read_text()
    assert f"MOUNT_POINT={mount_point}" in env_content
    assert f"SOURCE_DIR={source_dir}" in env_content
    assert "BLACKHOLE_EXTRA_ARGS=" in env_content

    # Check systemctl calls.
    assert mock_run.call_count == 2
    enable_call = mock_run.call_args_list[0]
    assert enable_call[0][0] == [
        "systemctl",
        "--user",
        "enable",
        "blackhole@test-mount.service",
    ]
    start_call = mock_run.call_args_list[1]
    assert start_call[0][0] == [
        "systemctl",
        "--user",
        "start",
        "blackhole@test-mount.service",
    ]


def test_register_directory_mode_with_override(tmp_path: Path) -> None:
    """register includes override-dir argument in BLACKHOLE_EXTRA_ARGS."""
    config_home = tmp_path / "config"
    source_dir = tmp_path / "source"
    override_dir = tmp_path / "override"
    mount_point = tmp_path / "mount"
    source_dir.mkdir()
    override_dir.mkdir()
    mount_point.mkdir()

    config = BlackholeConfig(
        mode="directory",
        mount_point=mount_point,
        target_file=None,
        override_file=None,
        source_dir=source_dir,
        override_dir=override_dir,
        persistent=True,
    )

    with mock.patch("blackhole.service.subprocess.run"):
        register(config, "test-mount", config_home)

    env_file = config_home / "blackhole" / "test-mount.env"
    env_content = env_file.read_text()
    assert f"BLACKHOLE_EXTRA_ARGS=--override-dir {override_dir}" in env_content


def test_register_single_file_mode_with_override(tmp_path: Path) -> None:
    """register handles single-file mode with override."""
    config_home = tmp_path / "config"
    mount_dir = tmp_path / "mount"
    target_file = mount_dir / "target.txt"
    override_file = tmp_path / "override.txt"
    mount_dir.mkdir()
    target_file.write_text("original")
    override_file.write_text("override")

    config = BlackholeConfig(
        mode="single-file",
        mount_point=mount_dir,
        target_file=target_file,
        override_file=override_file,
        source_dir=None,
        override_dir=None,
        persistent=True,
    )

    with mock.patch("blackhole.service.subprocess.run"):
        register(config, "test-file", config_home)

    env_file = config_home / "blackhole" / "test-file.env"
    env_content = env_file.read_text()
    assert f"BLACKHOLE_EXTRA_ARGS=--override-file {override_file}" in env_content


def test_register_derives_instance_name_when_none(tmp_path: Path) -> None:
    """register derives instance name from mount_point when name is None."""
    config_home = tmp_path / "config"
    mount_point = tmp_path / "mnt" / "foo"
    source_dir = tmp_path / "source"
    mount_point.mkdir(parents=True)
    source_dir.mkdir()

    config = BlackholeConfig(
        mode="directory",
        mount_point=mount_point,
        target_file=None,
        override_file=None,
        source_dir=source_dir,
        override_dir=None,
        persistent=True,
    )

    with mock.patch("blackhole.service.subprocess.run"):
        register(config, None, config_home)

    # Should derive a name from the mount path.
    env_files = list((config_home / "blackhole").glob("*.env"))
    assert len(env_files) == 1


def test_register_fails_without_mount_point_directory_mode(tmp_path: Path) -> None:
    """register raises ValueError if directory mode lacks mount_point."""
    config_home = tmp_path / "config"
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    config = BlackholeConfig(
        mode="directory",
        mount_point=None,
        target_file=None,
        override_file=None,
        source_dir=source_dir,
        override_dir=None,
        persistent=True,
    )

    with pytest.raises(ValueError, match="mount_point"):
        register(config, "test", config_home)


def test_unregister_stops_and_disables_service(tmp_path: Path) -> None:
    """unregister calls systemctl stop/disable and removes env file."""
    config_home = tmp_path / "config"
    env_file = config_home / "blackhole" / "test-mount.env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("dummy")

    with mock.patch("blackhole.service.subprocess.run") as mock_run:
        unregister("test-mount", config_home)

    # Check env file was deleted.
    assert not env_file.exists()

    # Check systemctl calls: stop, disable, daemon-reload
    assert mock_run.call_count == 3
    stop_call = mock_run.call_args_list[0]
    assert stop_call[0][0] == [
        "systemctl",
        "--user",
        "stop",
        "blackhole@test-mount.service",
    ]
    disable_call = mock_run.call_args_list[1]
    assert disable_call[0][0] == [
        "systemctl",
        "--user",
        "disable",
        "blackhole@test-mount.service",
    ]
    reload_call = mock_run.call_args_list[2]
    assert reload_call[0][0] == ["systemctl", "--user", "daemon-reload"]


def test_unregister_tolerates_missing_service(tmp_path: Path) -> None:
    """unregister succeeds even if service is not installed."""
    config_home = tmp_path / "config"

    with mock.patch("blackhole.service.subprocess.run") as mock_run:
        unregister("nonexistent", config_home)

    # Should still call daemon-reload.
    daemon_reload_calls = [call for call in mock_run.call_args_list if "daemon-reload" in str(call)]
    assert len(daemon_reload_calls) == 1


def test_unregister_tolerates_missing_env_file(tmp_path: Path) -> None:
    """unregister succeeds if env file is already gone."""
    config_home = tmp_path / "config"
    config_home.mkdir()

    with mock.patch("blackhole.service.subprocess.run"):
        unregister("test", config_home)

    # Should not raise.
