"""FUSE operations implementing immutable reads and discard writes."""

from __future__ import annotations

import errno
import logging
import os
import stat
from pathlib import Path

from fuse import FuseOSError, Operations

from blackhole.config import BlackholeConfig
from blackhole.ephemeral_state import EphemeralState
from blackhole.pathing import _normalized_request_relative_path, resolve_source_path
from blackhole.statmap import stat_to_fuse_dict


LOGGER = logging.getLogger("blackhole.operations")


class BlackholeOperations(Operations):
    """Filesystem operation adapter with blackhole write semantics."""

    def __init__(self, config: BlackholeConfig) -> None:
        self.config = config
        self.state = EphemeralState()

    def _is_passthrough(self, path: str) -> bool:
        """Return True if this path should pass through to the real filesystem.

        Only applies in single-file mode for paths that are NOT the target file.
        In directory mode every path is blackholed.
        """
        if self.config.mode != "single-file" or self.config.target_file is None:
            return False
        parts = _normalized_request_relative_path(path).parts
        is_target = bool(parts) and parts[0] == self.config.target_file.name and len(parts) == 1
        return not is_target

    def _map_exception(self, error: Exception) -> FuseOSError:
        if isinstance(error, FileNotFoundError):
            return FuseOSError(errno.ENOENT)
        if isinstance(error, PermissionError):
            return FuseOSError(errno.EACCES)
        if isinstance(error, IsADirectoryError):
            return FuseOSError(errno.EISDIR)
        if isinstance(error, NotADirectoryError):
            return FuseOSError(errno.ENOTDIR)
        LOGGER.exception("operation_failed", exc_info=error)
        return FuseOSError(errno.EIO)

    def _resolve(self, path: str) -> Path:
        try:
            return resolve_source_path(path, self.config)
        except Exception as error:  # noqa: BLE001
            raise self._map_exception(error) from error

    def _stat_synthetic(self, path: str) -> dict[str, int | float] | None:
        if self.state.is_synthetic_file(path):
            return {
                "st_mode": stat.S_IFREG | 0o644,
                "st_nlink": 1,
                "st_size": 0,
                "st_ctime": 0.0,
                "st_mtime": 0.0,
                "st_atime": 0.0,
                "st_uid": 0,
                "st_gid": 0,
            }
        if self.state.is_synthetic_dir(path):
            return {
                "st_mode": stat.S_IFDIR | 0o755,
                "st_nlink": 2,
                "st_size": 0,
                "st_ctime": 0.0,
                "st_mtime": 0.0,
                "st_atime": 0.0,
                "st_uid": 0,
                "st_gid": 0,
            }
        return None

    def getattr(self, path: str, fh: int | None = None) -> dict[str, int | float]:
        _ = fh
        if self.state.is_deleted(path):
            raise FuseOSError(errno.ENOENT)

        synthetic = self._stat_synthetic(path)
        if synthetic is not None:
            return synthetic

        source_path = self._resolve(path)
        if not source_path.exists():
            raise FuseOSError(errno.ENOENT)
        return stat_to_fuse_dict(source_path.stat())

    def getxattr(self, path: str, name: str, position: int = 0) -> bytes:
        _ = position
        source_path = self._resolve(path)
        try:
            return os.getxattr(source_path, name)  # type: ignore[attr-defined]
        except OSError as error:
            raise FuseOSError(error.errno) from error

    def listxattr(self, path: str) -> list[str]:
        source_path = self._resolve(path)
        try:
            return os.listxattr(source_path)  # type: ignore[attr-defined]
        except OSError as error:
            raise FuseOSError(error.errno) from error

    def readdir(self, path: str, fh: int) -> list[str]:
        _ = fh
        if self.state.is_deleted(path):
            raise FuseOSError(errno.ENOENT)

        source_path = self._resolve(path)
        if not source_path.exists() or not source_path.is_dir():
            raise FuseOSError(errno.ENOTDIR)

        entries = {".", ".."}
        entries.update(entry.name for entry in source_path.iterdir())
        entries.update(self.state.synthetic_children(path))

        for deleted_path in self.state.deleted_paths:
            deleted_name = Path(deleted_path).name
            entries.discard(deleted_name)

        return sorted(entries)

    def open(self, path: str, flags: int) -> int:
        _ = flags
        _ = self.getattr(path)
        return 0

    def read(self, path: str, size: int, offset: int, fh: int) -> bytes:
        _ = fh
        source_path = self._resolve(path)
        if source_path.is_dir():
            raise FuseOSError(errno.EISDIR)
        try:
            with source_path.open("rb") as file_obj:
                file_obj.seek(offset)
                return file_obj.read(size)
        except Exception as error:  # noqa: BLE001
            raise self._map_exception(error) from error

    def write(self, path: str, data: bytes, offset: int, fh: int) -> int:
        _ = fh
        if self._is_passthrough(path):
            source_path = self._resolve(path)
            try:
                with source_path.open("r+b") as file_obj:
                    file_obj.seek(offset)
                    file_obj.write(data)
                return len(data)
            except Exception as error:  # noqa: BLE001
                raise self._map_exception(error) from error
        LOGGER.info("discard_write path=%s bytes=%d", path, len(data))
        return len(data)

    def truncate(self, path: str, length: int, fh: int | None = None) -> int:
        _ = fh
        if self._is_passthrough(path):
            source_path = self._resolve(path)
            try:
                with source_path.open("r+b") as file_obj:
                    file_obj.truncate(length)
                return 0
            except Exception as error:  # noqa: BLE001
                raise self._map_exception(error) from error
        LOGGER.info("discard_truncate path=%s length=%d", path, length)
        return 0

    def create(self, path: str, mode: int, fi: int | None = None) -> int:
        _ = (mode, fi)
        self.state.mark_created_file(path)
        return 0

    def unlink(self, path: str) -> int:
        if self._is_passthrough(path):
            source_path = self._resolve(path)
            try:
                source_path.unlink()
                return 0
            except Exception as error:  # noqa: BLE001
                raise self._map_exception(error) from error
        # Blackholed path: ephemeral delete in directory mode; pure no-op for
        # the target file in single-file mode (file must stay readable).
        if self.config.mode == "directory":
            self.state.mark_deleted(path)
        return 0

    def mkdir(self, path: str, mode: int) -> int:
        _ = mode
        self.state.mark_created_dir(path)
        return 0

    def rmdir(self, path: str) -> int:
        self.state.mark_deleted(path)
        return 0

    def chmod(self, path: str, mode: int) -> int:
        _ = (path, mode)
        return 0

    def chown(self, path: str, uid: int, gid: int) -> int:
        _ = (path, uid, gid)
        return 0

    def flush(self, path: str, fh: int) -> int:
        _ = (path, fh)
        return 0

    def fsync(self, path: str, fdatasync: int, fh: int) -> int:
        _ = (path, fdatasync, fh)
        return 0
