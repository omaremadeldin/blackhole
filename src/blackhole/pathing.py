"""Path resolution helpers for source mapping."""

from __future__ import annotations

import errno
from pathlib import Path, PurePosixPath

from blackhole.config import BlackholeConfig


def _normalized_request_relative_path(request_path: str) -> PurePosixPath:
    sanitized = request_path if request_path.startswith("/") else f"/{request_path}"
    normalized = PurePosixPath(sanitized)
    return PurePosixPath(str(normalized).lstrip("/"))


def _traversal_check(candidate: Path, root: Path) -> None:
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise PermissionError(errno.EACCES, "path traversal outside source root") from error


def resolve_source_path(request_path: str, config: BlackholeConfig) -> Path:
    """Resolve a FUSE request path to the backing immutable source path."""
    request_rel = _normalized_request_relative_path(request_path)

    if config.mode == "single-file":
        if config.target_file is None:
            raise ValueError("single-file mode requires target_file")
        if config.backing_dir_fd is None:
            raise ValueError("backing_dir_fd not set for single-file mode")
        # All paths go through the pre-opened backing fd so no path ever
        # re-enters the FUSE mount (which would deadlock the single-threaded daemon).
        backing = Path(f"/proc/self/fd/{config.backing_dir_fd}")
        parts = request_rel.parts
        if not parts:
            return backing
        if parts[0] == config.target_file.name and len(parts) == 1:
            return (
                config.override_file
                if config.override_file is not None
                else backing / config.target_file.name
            )
        return backing / request_rel

    if config.source_dir is None:
        raise ValueError("directory mode requires source_dir")

    source_root = config.source_dir.resolve(strict=True)
    candidate = (source_root / request_rel).resolve(strict=False)
    _traversal_check(candidate, source_root)

    if config.override_dir is not None:
        override_root = config.override_dir.resolve(strict=True)
        override_candidate = (override_root / request_rel).resolve(strict=False)
        _traversal_check(override_candidate, override_root)
        if override_candidate.exists():
            return override_candidate

    return candidate
