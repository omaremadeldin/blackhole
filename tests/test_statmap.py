from __future__ import annotations

from pathlib import Path

import pytest

from blackhole.statmap import stat_to_fuse_dict

pytestmark = pytest.mark.unit


def test_stat_to_fuse_dict_contains_required_keys(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("x", encoding="utf-8")

    mapped = stat_to_fuse_dict(sample.stat())

    assert set(mapped) == {
        "st_atime",
        "st_ctime",
        "st_gid",
        "st_mode",
        "st_mtime",
        "st_nlink",
        "st_size",
        "st_uid",
    }
