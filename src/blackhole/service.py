"""Systemd user-service management for blackhole persistent mounts."""

from __future__ import annotations

import subprocess
from pathlib import Path

from blackhole.config import BlackholeConfig

# Embedded systemd service unit template (no external file needed at runtime).
_BLACKHOLE_SERVICE_TEMPLATE = """\
[Unit]
Description=blackhole FUSE overlay — %i

[Service]
Type=simple
EnvironmentFile=%h/.config/blackhole/%i.env
ExecStart=/usr/bin/blackhole mount dir --mount-point ${MOUNT_POINT} --source-dir ${SOURCE_DIR} ${BLACKHOLE_EXTRA_ARGS}
ExecStop=/usr/bin/fusermount3 -u ${MOUNT_POINT}
Restart=on-failure
RestartSec=2s
KillMode=mixed

[Install]
WantedBy=default.target
"""


def install_template(config_home: Path) -> Path:
    """Write the embedded blackhole@.service template to ~/.config/systemd/user/.

    Args:
        config_home: Path to XDG_CONFIG_HOME (typically ~/.config)

    Returns:
        Path to the installed unit file

    Raises:
        OSError: If unable to write the file
    """
    unit_dir = config_home / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)

    unit_path = unit_dir / "blackhole@.service"
    unit_path.write_text(_BLACKHOLE_SERVICE_TEMPLATE, encoding="utf-8")

    return unit_path


def derive_instance_name(mount_point: Path) -> str:
    """Derive a stable instance name from a mount path.

    Example: Path("/home/user/mnt/foo") -> "home-user-mnt-foo"

    Args:
        mount_point: The absolute mount path

    Returns:
        A valid systemd instance name (slug)
    """
    # Resolve to absolute path and convert to string, strip leading/trailing slashes.
    path_str = str(mount_point.resolve()).strip("/")
    # Replace "/" with "-" to form the slug.
    return path_str.replace("/", "-")


def register(
    config: BlackholeConfig,
    name: str | None,
    config_home: Path,
) -> None:
    """Register a mount as a systemd user service.

    Writes an env file to ~/.config/blackhole/<name>.env, then enables and starts
    the corresponding blackhole@<name>.service instance.

    Args:
        config: The parsed mount configuration (with paths resolved)
        name: Instance name for the service. If None, derived from mount_point.
        config_home: Path to XDG_CONFIG_HOME (typically ~/.config)

    Raises:
        ValueError: If config.mount_point is None or name derivation fails
        OSError: If unable to write env file
        subprocess.CalledProcessError: If systemctl commands fail
    """
    if config.mode == "single-file" and config.mount_point is None:
        raise ValueError("single-file mode requires mount_point")
    if config.mode == "directory" and config.mount_point is None:
        raise ValueError("directory mode requires mount_point")

    # Derive instance name if not provided.
    instance_name = name or derive_instance_name(config.mount_point)

    # Write env file.
    env_dir = config_home / "blackhole"
    env_dir.mkdir(parents=True, exist_ok=True)
    env_file = env_dir / f"{instance_name}.env"

    lines = [
        f"MOUNT_POINT={config.mount_point}",
        f"SOURCE_DIR={config.source_dir}",
    ]

    # Append override if present (single-file or directory mode).
    if config.mode == "single-file" and config.override_file:
        lines.append(f"BLACKHOLE_EXTRA_ARGS=--override-file {config.override_file}")
    elif config.mode == "directory" and config.override_dir:
        lines.append(f"BLACKHOLE_EXTRA_ARGS=--override-dir {config.override_dir}")
    else:
        lines.append("BLACKHOLE_EXTRA_ARGS=")

    env_content = "\n".join(lines) + "\n"
    env_file.write_text(env_content, encoding="utf-8")

    # Enable and start the service.
    subprocess.run(
        ["systemctl", "--user", "enable", f"blackhole@{instance_name}.service"],
        check=True,
    )
    subprocess.run(
        ["systemctl", "--user", "start", f"blackhole@{instance_name}.service"],
        check=True,
    )


def unregister(name: str, config_home: Path) -> None:
    """Unregister a systemd user service mount.

    Stops and disables the blackhole@<name>.service instance, deletes the env file,
    and reloads the user daemon.

    Args:
        name: Instance name of the service
        config_home: Path to XDG_CONFIG_HOME (typically ~/.config)

    Raises:
        subprocess.CalledProcessError: If systemctl commands fail
        OSError: If unable to delete env file
    """
    # Stop and disable the service.
    subprocess.run(
        ["systemctl", "--user", "stop", f"blackhole@{name}.service"],
        check=False,  # Tolerate if service doesn't exist.
    )
    subprocess.run(
        ["systemctl", "--user", "disable", f"blackhole@{name}.service"],
        check=False,  # Tolerate if service doesn't exist.
    )

    # Delete the env file if it exists.
    env_file = config_home / "blackhole" / f"{name}.env"
    if env_file.exists():
        env_file.unlink()

    # Reload the user daemon.
    subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        check=True,
    )
