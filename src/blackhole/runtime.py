"""Runtime mounting bootstrap for blackhole."""

from __future__ import annotations

import logging
import os
import stat

from fuse import FUSE

from blackhole.config import BlackholeConfig
from blackhole.operations import BlackholeOperations

LOGGER = logging.getLogger("blackhole.runtime")


def _apply_source_permissions(config: BlackholeConfig) -> None:
    """Mirror the source directory's ownership and mode onto the mount point."""
    if config.source_dir is None or config.mount_point is None:
        return
    src_stat = config.source_dir.stat()
    os.chown(config.mount_point, src_stat.st_uid, src_stat.st_gid)
    os.chmod(config.mount_point, stat.S_IMODE(src_stat.st_mode))
    LOGGER.info(
        "mount_permissions uid=%d gid=%d mode=%o",
        src_stat.st_uid,
        src_stat.st_gid,
        stat.S_IMODE(src_stat.st_mode),
    )


def run_filesystem(config: BlackholeConfig) -> int:
    """Run the FUSE filesystem with deterministic mount options."""
    if config.mount_point is None:
        raise ValueError("mount_point must be configured")

    if config.mode == "directory":
        _apply_source_permissions(config)

    if config.mode == "single-file":
        # Open the backing directory before FUSE mounts over it so sibling
        # files remain accessible via /proc/self/fd/<fd> during the mount.
        config.backing_dir_fd = os.open(config.mount_point, os.O_RDONLY | os.O_DIRECTORY)
        LOGGER.info("backing_dir_fd=%d path=%s", config.backing_dir_fd, config.mount_point)

    LOGGER.info("mount_start mount_point=%s", config.mount_point)
    try:
        FUSE(
            BlackholeOperations(config),
            str(config.mount_point),
            foreground=True,
            allow_other=False,
            nonempty=config.mode == "single-file",
        )
    finally:
        if config.backing_dir_fd is not None:
            os.close(config.backing_dir_fd)
            config.backing_dir_fd = None

    LOGGER.info("mount_stop mount_point=%s", config.mount_point)
    return 0
