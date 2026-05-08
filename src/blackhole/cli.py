"""CLI command parsing for blackhole."""

from __future__ import annotations

import argparse
from pathlib import Path

from blackhole.commands import (
    CommandSpec,
    InstallServiceCommandSpec,
    MountCommandSpec,
    RemoveServiceCommandSpec,
)


def _resolve_path(value: str) -> Path:
    """Resolve a CLI path argument to an absolute path without strict existence."""
    return Path(value).resolve(strict=False)


def _add_persistent_options(parser: argparse.ArgumentParser) -> None:
    """Add shared persistent-service options to mount mode parsers."""
    parser.add_argument(
        "--persistent",
        action="store_true",
        help="Register as a systemd user service instead of running in foreground",
    )
    parser.add_argument(
        "--service-name",
        default=None,
        help="Custom instance name for systemd service (requires --persistent)",
    )


def _validate_persistent_args(
    parser: argparse.ArgumentParser,
    *,
    persistent: bool,
    service_name: str | None,
) -> None:
    """Validate persistent-service option shape for mount commands."""
    if service_name and not persistent:
        parser.error("--service-name requires --persistent")


def parse_command(argv: list[str]) -> CommandSpec:
    """Parse CLI arguments into a typed command specification."""
    parser = argparse.ArgumentParser(prog="blackhole")
    subparsers = parser.add_subparsers(dest="command", required=True, help="command to run")

    mount_parser = subparsers.add_parser("mount", help="Mount a blackhole FUSE filesystem")
    mount_subparsers = mount_parser.add_subparsers(
        dest="mount_mode",
        required=True,
        help="mount mode to run",
    )

    file_parser = mount_subparsers.add_parser(
        "file",
        help="Single-file mode",
    )
    file_parser.add_argument("--target", required=True, help="Target file to mount")
    file_parser.add_argument(
        "--override-file",
        default=None,
        help="Optional file that overrides reads from --target",
    )
    _add_persistent_options(file_parser)

    directory_parser = mount_subparsers.add_parser(
        "dir",
        help="Directory mode",
    )
    directory_parser.add_argument("--mount-point", required=True, help="FUSE mount directory")
    directory_parser.add_argument("--source-dir", required=True, help="Read source directory")
    directory_parser.add_argument(
        "--override-dir",
        default=None,
        help="Optional directory that overrides source entries by relative path",
    )
    _add_persistent_options(directory_parser)

    remove_parser = subparsers.add_parser(
        "unmount",
        help="Remove a registered systemd user service",
    )
    remove_parser.add_argument("name", help="Instance name of the service to unmount")

    subparsers.add_parser(
        "install-service",
        help="Install the blackhole@.service template to ~/.config/systemd/user/",
    )

    args = parser.parse_args(argv)

    if args.command == "mount" and args.mount_mode == "file":
        _validate_persistent_args(
            parser,
            persistent=bool(args.persistent),
            service_name=args.service_name,
        )
        return MountCommandSpec.for_single_file(
            target_file=_resolve_path(args.target),
            override_file=_resolve_path(args.override_file) if args.override_file else None,
            persistent=bool(args.persistent),
            service_name=args.service_name,
        )

    if args.command == "mount" and args.mount_mode == "dir":
        _validate_persistent_args(
            parser,
            persistent=bool(args.persistent),
            service_name=args.service_name,
        )
        return MountCommandSpec.for_directory(
            mount_point=_resolve_path(args.mount_point),
            source_dir=_resolve_path(args.source_dir),
            override_dir=_resolve_path(args.override_dir) if args.override_dir else None,
            persistent=bool(args.persistent),
            service_name=args.service_name,
        )

    if args.command == "unmount":
        return RemoveServiceCommandSpec(name=args.name)

    if args.command == "install-service":
        return InstallServiceCommandSpec()

    raise ValueError(f"unsupported command: {args.command}")
