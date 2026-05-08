from __future__ import annotations

from pathlib import Path

import pytest

from blackhole.main import main

pytestmark = pytest.mark.unit


def test_main_returns_zero_for_valid_single_file_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("blackhole.main.run_filesystem", lambda config: 0)

    source_file = tmp_path / "source.txt"
    source_file.write_text("payload", encoding="utf-8")

    target_file = tmp_path / "mount" / "target.txt"
    target_file.parent.mkdir(parents=True)

    exit_code = main([
        "mount",
        "file",
        "--target",
        str(target_file),
        "--override-file",
        str(source_file),
    ])

    assert exit_code == 0
