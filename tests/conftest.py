"""Shared pytest fixtures, including the interactive FUSE mount helper."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import time
import types
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest


def _install_fuse_stub() -> None:
    """Install a minimal in-process stub for fusepy imports in unit tests."""

    fuse_stub = types.ModuleType("fuse")

    class FuseOSError(OSError):
        def __init__(self, errnum: int) -> None:
            super().__init__(errnum, os.strerror(errnum))
            self.errno = errnum

    class Operations:
        pass

    class FUSE:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("FUSE runtime is not available in mocked unit-test mode")

    fuse_stub.FuseOSError = FuseOSError
    fuse_stub.Operations = Operations
    fuse_stub.FUSE = FUSE
    sys.modules["fuse"] = fuse_stub


def _ensure_fuse_importable() -> None:
    """Ensure importing `fuse` does not fail during unit-test collection."""
    if os.environ.get("BLACKHOLE_MOCK_FUSE") != "1":
        return
    try:
        __import__("fuse")
    except Exception:  # noqa: BLE001
        _install_fuse_stub()


_ensure_fuse_importable()


def _unattended() -> bool:
    return os.environ.get("RUN_FUSE_INTEGRATION_INTERACTIVE") != "1"


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DirectoryMount:
    mount_point: Path
    source_dir: Path
    probe_file_name: str
    probe_source_content: str
    process: subprocess.Popen | None = None


@dataclass(frozen=True)
class DirectoryOverrideMount:
    mount_point: Path
    source_dir: Path
    override_dir: Path
    probe_file_name: str
    probe_source_content: str
    probe_override_content: str
    source_only_file_name: str
    source_only_content: str
    process: subprocess.Popen | None = None


@dataclass(frozen=True)
class SingleFileMount:
    mount_point: Path
    target_file: Path
    original_content: str
    sibling_file: Path
    sibling_content: str
    process: subprocess.Popen | None = None


@dataclass(frozen=True)
class SingleFileOverrideMount:
    mount_point: Path
    target_file: Path
    override_file: Path
    override_content: str
    sibling_file: Path
    sibling_content: str
    process: subprocess.Popen | None = None


# ---------------------------------------------------------------------------
# Interactive helpers
# ---------------------------------------------------------------------------


def _tty_input(prompt: str) -> str:
    """Read a line from /dev/tty so it works even under pytest stdin capture."""
    with open("/dev/tty", "r") as tty:
        sys.stdout.write(prompt)
        sys.stdout.flush()
        return tty.readline().rstrip("\n")


def _prompt_user(lines: list[str]) -> None:
    for line in lines:
        sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _is_mounted(path: Path) -> bool:
    result = subprocess.run(
        ["findmnt", "--noheadings", "--output", "TARGET", str(path)],
        capture_output=True,
        text=True,
    )
    return str(path) in result.stdout


def _assert_mounted(path: Path) -> None:
    if not _is_mounted(path):
        pytest.fail(
            f"Expected FUSE mount at {path} but findmnt reports nothing there. "
            "Did you run the command shown above?"
        )


def _assert_unmounted(path: Path) -> None:
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if not _is_mounted(path):
            return
        time.sleep(0.1)
    pytest.fail(f"Expected {path} to be unmounted but it is still listed in findmnt.")


def _wait_for_mount(path: Path, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _is_mounted(path):
            return
        time.sleep(0.1)
    pytest.fail(f"FUSE mount at {path} did not become active within {timeout}s.")


def _ask_mount(command: str, mount_point: Path) -> subprocess.Popen | None:
    """Start the mount process (or ask user to run it if interactive)."""
    if _unattended():
        proc = subprocess.Popen(shlex.split(command))
        _wait_for_mount(mount_point)
        _assert_mounted(mount_point)
        return proc

    _prompt_user([
        "",
        "=" * 70,
        "  MANUAL MOUNT REQUIRED",
        "  Run the following command in another terminal:",
        "",
        f"    {command}",
        "",
        "  Then press Enter here to continue.",
        "=" * 70,
    ])
    _tty_input("")
    _wait_for_mount(mount_point)
    _assert_mounted(mount_point)
    return None


def _ask_unmount(mount_point: Path, process: subprocess.Popen | None = None) -> None:
    """Stop the mount (either by killing process or asking user to unmount)."""
    if process is not None:
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        _assert_unmounted(mount_point)
        return

    if _unattended():
        subprocess.run(["fusermount3", "-u", str(mount_point)], check=True)
        _assert_unmounted(mount_point)
        return

    _prompt_user([
        "",
        "=" * 70,
        "  MANUAL UNMOUNT REQUIRED",
        f"    fusermount3 -u {mount_point}",
        "",
        "  Then press Enter here to continue.",
        "=" * 70,
    ])
    _tty_input("")
    _assert_unmounted(mount_point)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def directory_blackhole_mount(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[DirectoryMount, None, None]:
    root = tmp_path_factory.mktemp("dir_bh")
    source_dir = root / "source"
    source_dir.mkdir()
    mount_point = root / "mount"
    mount_point.mkdir()

    probe_name = "probe.txt"
    probe_content = "original-content-dir-blackhole"
    (source_dir / probe_name).write_text(probe_content, encoding="utf-8")

    blackhole = shutil.which("blackhole") or "blackhole"
    proc = _ask_mount(
        f"{blackhole} mount dir --mount-point {mount_point} --source-dir {source_dir}",
        mount_point,
    )

    yield DirectoryMount(
        mount_point=mount_point,
        source_dir=source_dir,
        probe_file_name=probe_name,
        probe_source_content=probe_content,
        process=proc,
    )

    _ask_unmount(mount_point, proc)


@pytest.fixture(scope="module")
def directory_override_mount(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[DirectoryOverrideMount, None, None]:
    root = tmp_path_factory.mktemp("dir_ov")
    source_dir = root / "source"
    source_dir.mkdir()
    override_dir = root / "override"
    override_dir.mkdir()
    mount_point = root / "mount"
    mount_point.mkdir()

    probe_name = "probe.txt"
    source_only_name = "source-only.txt"
    probe_source_content = "source-content"
    probe_override_content = "override-content"
    source_only_content = "source-only-content"

    (source_dir / probe_name).write_text(probe_source_content, encoding="utf-8")
    (override_dir / probe_name).write_text(probe_override_content, encoding="utf-8")
    (source_dir / source_only_name).write_text(source_only_content, encoding="utf-8")

    blackhole = shutil.which("blackhole") or "blackhole"
    proc = _ask_mount(
        (
            f"{blackhole} mount dir --mount-point {mount_point} "
            f"--source-dir {source_dir} --override-dir {override_dir}"
        ),
        mount_point,
    )

    yield DirectoryOverrideMount(
        mount_point=mount_point,
        source_dir=source_dir,
        override_dir=override_dir,
        probe_file_name=probe_name,
        probe_source_content=probe_source_content,
        probe_override_content=probe_override_content,
        source_only_file_name=source_only_name,
        source_only_content=source_only_content,
        process=proc,
    )

    _ask_unmount(mount_point, proc)


@pytest.fixture(scope="module")
def single_file_blackhole_mount(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[SingleFileMount, None, None]:
    root = tmp_path_factory.mktemp("sf_bh")
    mount_dir = root / "mount"
    mount_dir.mkdir()

    target_file = mount_dir / "target.txt"
    original_content = "original-target-content"
    target_file.write_text(original_content, encoding="utf-8")

    sibling_file = mount_dir / "sibling.txt"
    sibling_content = "sibling-content"
    sibling_file.write_text(sibling_content, encoding="utf-8")

    blackhole = shutil.which("blackhole") or "blackhole"
    proc = _ask_mount(
        f"{blackhole} mount file --target {target_file}",
        mount_dir,
    )

    yield SingleFileMount(
        mount_point=mount_dir,
        target_file=target_file,
        original_content=original_content,
        sibling_file=sibling_file,
        sibling_content=sibling_content,
        process=proc,
    )

    _ask_unmount(mount_dir, proc)


@pytest.fixture(scope="module")
def single_file_override_mount(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[SingleFileOverrideMount, None, None]:
    root = tmp_path_factory.mktemp("sf_ov")
    mount_dir = root / "mount"
    mount_dir.mkdir()
    override_file = root / "override.txt"

    target_file = mount_dir / "target.txt"
    target_file.write_text("real-content-should-not-be-seen", encoding="utf-8")
    override_content = "override-content-shown-instead"
    override_file.write_text(override_content, encoding="utf-8")

    sibling_file = mount_dir / "sibling.txt"
    sibling_content = "sibling-untouched"
    sibling_file.write_text(sibling_content, encoding="utf-8")

    blackhole = shutil.which("blackhole") or "blackhole"
    proc = _ask_mount(
        f"{blackhole} mount file --target {target_file} --override-file {override_file}",
        mount_dir,
    )

    yield SingleFileOverrideMount(
        mount_point=mount_dir,
        target_file=target_file,
        override_file=override_file,
        override_content=override_content,
        sibling_file=sibling_file,
        sibling_content=sibling_content,
        process=proc,
    )

    _ask_unmount(mount_dir, proc)
