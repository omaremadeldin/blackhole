"""Integration tests for all blackhole mount modes.

Requires a Linux host with FUSE support. Each test module uses interactive
fixtures that prompt for privileged mount/unmount commands.
"""

from __future__ import annotations

import pytest

from conftest import (
    DirectoryMount,
    DirectoryOverrideMount,
    SingleFileMount,
    SingleFileOverrideMount,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Directory mode — pure blackhole
# ---------------------------------------------------------------------------


class TestDirectoryBlackhole:
    def test_read_returns_source_content(self, directory_blackhole_mount: DirectoryMount) -> None:
        m = directory_blackhole_mount
        mounted = m.mount_point / m.probe_file_name
        assert mounted.read_text(encoding="utf-8") == m.probe_source_content

    def test_readdir_lists_source_entries(self, directory_blackhole_mount: DirectoryMount) -> None:
        m = directory_blackhole_mount
        names = {p.name for p in m.mount_point.iterdir()}
        assert m.probe_file_name in names

    def test_write_is_discarded_read_unchanged(
        self, directory_blackhole_mount: DirectoryMount
    ) -> None:
        m = directory_blackhole_mount
        mounted = m.mount_point / m.probe_file_name
        mounted.write_text("discard-me", encoding="utf-8")
        assert mounted.read_text(encoding="utf-8") == m.probe_source_content

    def test_write_does_not_mutate_source_file(
        self, directory_blackhole_mount: DirectoryMount
    ) -> None:
        m = directory_blackhole_mount
        (m.mount_point / m.probe_file_name).write_text("discard-me", encoding="utf-8")
        assert (m.source_dir / m.probe_file_name).read_text(
            encoding="utf-8"
        ) == m.probe_source_content

    def test_unlink_does_not_remove_source_file(
        self, directory_blackhole_mount: DirectoryMount
    ) -> None:
        m = directory_blackhole_mount
        (m.mount_point / m.probe_file_name).unlink(missing_ok=True)
        assert (m.source_dir / m.probe_file_name).exists()

    def test_create_file_is_ephemeral_visible_in_mount(
        self, directory_blackhole_mount: DirectoryMount
    ) -> None:
        m = directory_blackhole_mount
        ephemeral = m.mount_point / "__eph_file.txt"
        ephemeral.touch()
        assert ephemeral.exists()
        assert not (m.source_dir / "__eph_file.txt").exists()

    def test_mkdir_is_ephemeral_visible_in_mount(
        self, directory_blackhole_mount: DirectoryMount
    ) -> None:
        m = directory_blackhole_mount
        ephemeral_dir = m.mount_point / "__eph_dir"
        ephemeral_dir.mkdir(exist_ok=True)
        assert ephemeral_dir.is_dir()
        assert not (m.source_dir / "__eph_dir").exists()

    def test_rmdir_removes_ephemeral_dir_without_touching_source(
        self, directory_blackhole_mount: DirectoryMount
    ) -> None:
        m = directory_blackhole_mount
        ephemeral_dir = m.mount_point / "__eph_dir_rm"
        ephemeral_dir.mkdir(exist_ok=True)
        ephemeral_dir.rmdir()
        assert not ephemeral_dir.exists()
        assert not (m.source_dir / "__eph_dir_rm").exists()


# ---------------------------------------------------------------------------
# Directory mode — override directory
# ---------------------------------------------------------------------------


class TestDirectoryOverride:
    def test_read_returns_override_content_when_override_file_exists(
        self, directory_override_mount: DirectoryOverrideMount
    ) -> None:
        m = directory_override_mount
        mounted = m.mount_point / m.probe_file_name
        assert mounted.read_text(encoding="utf-8") == m.probe_override_content

    def test_read_returns_source_content_when_no_override_file(
        self, directory_override_mount: DirectoryOverrideMount
    ) -> None:
        m = directory_override_mount
        mounted = m.mount_point / m.source_only_file_name
        assert mounted.read_text(encoding="utf-8") == m.source_only_content

    def test_write_is_discarded_override_content_unchanged(
        self, directory_override_mount: DirectoryOverrideMount
    ) -> None:
        m = directory_override_mount
        mounted = m.mount_point / m.probe_file_name
        mounted.write_text("discard", encoding="utf-8")
        assert mounted.read_text(encoding="utf-8") == m.probe_override_content

    def test_write_does_not_mutate_override_file(
        self, directory_override_mount: DirectoryOverrideMount
    ) -> None:
        m = directory_override_mount
        (m.mount_point / m.probe_file_name).write_text("discard", encoding="utf-8")
        assert (m.override_dir / m.probe_file_name).read_text(
            encoding="utf-8"
        ) == m.probe_override_content

    def test_write_does_not_mutate_source_file(
        self, directory_override_mount: DirectoryOverrideMount
    ) -> None:
        m = directory_override_mount
        (m.mount_point / m.probe_file_name).write_text("discard", encoding="utf-8")
        assert (m.source_dir / m.probe_file_name).read_text(
            encoding="utf-8"
        ) == m.probe_source_content


# ---------------------------------------------------------------------------
# Single-file mode — pure blackhole
# ---------------------------------------------------------------------------


class TestSingleFileBlackhole:
    def test_read_returns_original_content(
        self, single_file_blackhole_mount: SingleFileMount
    ) -> None:
        m = single_file_blackhole_mount
        assert m.target_file.read_text(encoding="utf-8") == m.original_content

    def test_write_is_discarded_read_unchanged(
        self, single_file_blackhole_mount: SingleFileMount
    ) -> None:
        m = single_file_blackhole_mount
        m.target_file.write_text("discard-me", encoding="utf-8")
        assert m.target_file.read_text(encoding="utf-8") == m.original_content

    def test_unlink_does_not_affect_backing_file(
        self, single_file_blackhole_mount: SingleFileMount
    ) -> None:
        m = single_file_blackhole_mount
        m.target_file.unlink(missing_ok=True)
        assert m.target_file.read_text(encoding="utf-8") == m.original_content

    def test_sibling_file_is_accessible_and_unaffected(
        self, single_file_blackhole_mount: SingleFileMount
    ) -> None:
        m = single_file_blackhole_mount
        assert m.sibling_file.read_text(encoding="utf-8") == m.sibling_content

    def test_write_to_sibling_passes_through_to_real_fs(
        self, single_file_blackhole_mount: SingleFileMount
    ) -> None:
        m = single_file_blackhole_mount
        new_content = "sibling-updated"
        m.sibling_file.write_text(new_content, encoding="utf-8")
        assert m.sibling_file.read_text(encoding="utf-8") == new_content
        m.sibling_file.write_text(m.sibling_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Single-file mode — with override
# ---------------------------------------------------------------------------


class TestSingleFileOverride:
    def test_read_returns_override_content(
        self, single_file_override_mount: SingleFileOverrideMount
    ) -> None:
        m = single_file_override_mount
        assert m.target_file.read_text(encoding="utf-8") == m.override_content

    def test_write_is_discarded_override_content_unchanged(
        self, single_file_override_mount: SingleFileOverrideMount
    ) -> None:
        m = single_file_override_mount
        m.target_file.write_text("discard-me", encoding="utf-8")
        assert m.target_file.read_text(encoding="utf-8") == m.override_content

    def test_write_does_not_mutate_override_file(
        self, single_file_override_mount: SingleFileOverrideMount
    ) -> None:
        m = single_file_override_mount
        m.target_file.write_text("discard-me", encoding="utf-8")
        assert m.override_file.read_text(encoding="utf-8") == m.override_content

    def test_unlink_does_not_remove_override_file(
        self, single_file_override_mount: SingleFileOverrideMount
    ) -> None:
        m = single_file_override_mount
        m.target_file.unlink(missing_ok=True)
        assert m.override_file.exists()
        assert m.target_file.read_text(encoding="utf-8") == m.override_content

    def test_sibling_file_is_accessible_and_unaffected(
        self, single_file_override_mount: SingleFileOverrideMount
    ) -> None:
        m = single_file_override_mount
        assert m.sibling_file.read_text(encoding="utf-8") == m.sibling_content

    def test_write_to_sibling_passes_through_to_real_fs(
        self, single_file_override_mount: SingleFileOverrideMount
    ) -> None:
        m = single_file_override_mount
        new_content = "sibling-updated-override"
        m.sibling_file.write_text(new_content, encoding="utf-8")
        assert m.sibling_file.read_text(encoding="utf-8") == new_content
        m.sibling_file.write_text(m.sibling_content, encoding="utf-8")
