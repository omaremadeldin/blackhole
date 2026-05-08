"""Application entrypoint for blackhole."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from blackhole.cli import parse_command
from blackhole.commands import InstallServiceCommandSpec, MountCommandSpec, RemoveServiceCommandSpec
from blackhole.config import build_config
from blackhole.runtime import run_filesystem
from blackhole.service import install_template, register, unregister

LOGGER = logging.getLogger("blackhole")


def configure_logging() -> None:
    """Configure deterministic structured logging output."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s event=%(message)s",
    )


def main(argv: list[str]) -> int:
    """Run blackhole."""
    configure_logging()
    command = parse_command(argv)

    # Get config home (XDG_CONFIG_HOME or ~/.config)
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")

    if isinstance(command, InstallServiceCommandSpec):
        unit_path = install_template(config_home)
        LOGGER.info("installed_service template=%s", unit_path)
        return 0

    if isinstance(command, RemoveServiceCommandSpec):
        unregister(command.name, config_home)
        LOGGER.info("unregistered_service name=%s", command.name)
        return 0

    if not isinstance(command, MountCommandSpec):
        raise ValueError(f"unsupported command type: {type(command)!r}")

    config = build_config(command)
    LOGGER.info("startup mode=%s persistent=%s", config.mode, config.persistent)

    if config.persistent:
        # Register as a systemd user service.
        service_name = command.service_name
        register(config, service_name, config_home)
        LOGGER.info("registered_service name=%s", service_name or config.mount_point)
        return 0

    # Run in foreground (non-persistent).
    return run_filesystem(config)


def entrypoint() -> None:
    """Console script entrypoint."""
    raise SystemExit(main(sys.argv[1:]))
