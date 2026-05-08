"""Typed command specifications for CLI dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

MountMode = Literal["single-file", "directory"]


@dataclass(frozen=True, slots=True)
class MountCommandSpec:
    """Normalized mount command input for runtime execution."""

    mode: MountMode
    mount_point: Path
    source_dir: Path | None
    target_file: Path | None
    override_file: Path | None
    override_dir: Path | None
    persistent: bool
    service_name: str | None

    @classmethod
    def for_single_file(
        cls,
        target_file: Path,
        override_file: Path | None,
        persistent: bool,
        service_name: str | None,
    ) -> MountCommandSpec:
        """Create a single-file mount command specification."""
        return cls(
            mode="single-file",
            mount_point=target_file.parent,
            source_dir=None,
            target_file=target_file,
            override_file=override_file,
            override_dir=None,
            persistent=persistent,
            service_name=service_name,
        )

    @classmethod
    def for_directory(
        cls,
        mount_point: Path,
        source_dir: Path,
        override_dir: Path | None,
        persistent: bool,
        service_name: str | None,
    ) -> MountCommandSpec:
        """Create a directory mount command specification."""
        return cls(
            mode="directory",
            mount_point=mount_point,
            source_dir=source_dir,
            target_file=None,
            override_file=None,
            override_dir=override_dir,
            persistent=persistent,
            service_name=service_name,
        )


@dataclass(frozen=True, slots=True)
class RemoveServiceCommandSpec:
    """CLI input for service removal."""

    name: str


@dataclass(frozen=True, slots=True)
class InstallServiceCommandSpec:
    """CLI input for service template installation."""


CommandSpec: TypeAlias = MountCommandSpec | RemoveServiceCommandSpec | InstallServiceCommandSpec
