"""Stat conversion helpers for FUSE responses."""

from __future__ import annotations

import os


def stat_to_fuse_dict(st: os.stat_result) -> dict[str, int | float]:
    """Convert os.stat_result to keys expected by fusepy."""
    return {
        "st_atime": st.st_atime,
        "st_ctime": st.st_ctime,
        "st_gid": st.st_gid,
        "st_mode": st.st_mode,
        "st_mtime": st.st_mtime,
        "st_nlink": st.st_nlink,
        "st_size": st.st_size,
        "st_uid": st.st_uid,
    }
