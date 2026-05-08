"""Configuration model for blackhole."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from blackhole.commands import MountCommandSpec

ConfigMode = Literal["single-file", "directory"]


@dataclass(slots=True)
class BlackholeConfig:
    """Runtime configuration for blackhole."""

    mode: ConfigMode
    mount_point: Path | None
    target_file: Path | None
    override_file: Path | None
    source_dir: Path | None
    override_dir: Path | None
    persistent: bool  # When True, register as systemd user service instead of running foreground.
    backing_dir_fd: int | None = field(default=None)

    def validate(self) -> None:
        """Validate config invariants."""
        if self.mode == "single-file":
            if self.target_file is None:
                raise ValueError("single-file mode requires target_file")
            if self.source_dir is not None or self.override_dir is not None:
                raise ValueError("single-file mode must not set source_dir or override_dir")
            if self.override_file is not None:
                if not self.override_file.exists() or not self.override_file.is_file():
                    raise ValueError("override_file must exist and be a file")
            if self.target_file.parent.exists() is False:
                raise ValueError("target_file parent directory must exist")
            return

        if self.mode == "directory":
            if self.mount_point is None or self.source_dir is None:
                raise ValueError("directory mode requires mount_point and source_dir")
            if self.target_file is not None or self.override_file is not None:
                raise ValueError("directory mode must not set target_file or override_file")
            if not self.mount_point.exists() or not self.mount_point.is_dir():
                raise ValueError("mount_point must exist and be a directory")
            if not self.source_dir.exists() or not self.source_dir.is_dir():
                raise ValueError("source_dir must exist and be a directory")
            if self.override_dir is not None:
                if not self.override_dir.exists() or not self.override_dir.is_dir():
                    raise ValueError("override_dir must exist and be a directory")
            return

        raise ValueError(f"unsupported mode: {self.mode}")


def build_config(command: MountCommandSpec) -> BlackholeConfig:
    """Build and validate a normalized runtime configuration."""

    if command.mode == "single-file":
        if command.target_file is None:
            raise ValueError("single-file command requires target_file")
        config = BlackholeConfig(
            mode="single-file",
            mount_point=command.mount_point,
            target_file=command.target_file,
            override_file=command.override_file,
            source_dir=None,
            override_dir=None,
            persistent=command.persistent,
        )
        config.validate()
        return config

    if command.mode == "directory":
        if command.source_dir is None:
            raise ValueError("directory command requires source_dir")
        config = BlackholeConfig(
            mode="directory",
            mount_point=command.mount_point,
            target_file=None,
            override_file=None,
            source_dir=command.source_dir,
            override_dir=command.override_dir,
            persistent=command.persistent,
        )
        config.validate()
        return config

    raise ValueError(f"unsupported mode: {command.mode}")
