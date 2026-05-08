"""In-memory synthetic state for blackhole directory operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath


@dataclass(slots=True)
class EphemeralState:
    """Tracks synthetic files and directories that never persist to disk."""

    created_files: set[str] = field(default_factory=set)
    created_dirs: set[str] = field(default_factory=set)
    deleted_paths: set[str] = field(default_factory=set)

    def normalize(self, path: str) -> str:
        normalized = str(PurePosixPath(path if path.startswith("/") else f"/{path}"))
        return normalized

    def mark_created_file(self, path: str) -> None:
        normalized = self.normalize(path)
        self.created_files.add(normalized)
        self.deleted_paths.discard(normalized)

    def mark_created_dir(self, path: str) -> None:
        normalized = self.normalize(path)
        self.created_dirs.add(normalized)
        self.deleted_paths.discard(normalized)

    def mark_deleted(self, path: str) -> None:
        normalized = self.normalize(path)
        self.deleted_paths.add(normalized)
        self.created_files.discard(normalized)
        self.created_dirs.discard(normalized)

    def is_deleted(self, path: str) -> bool:
        return self.normalize(path) in self.deleted_paths

    def is_synthetic_file(self, path: str) -> bool:
        return self.normalize(path) in self.created_files

    def is_synthetic_dir(self, path: str) -> bool:
        return self.normalize(path) in self.created_dirs

    def synthetic_children(self, directory_path: str) -> set[str]:
        directory = PurePosixPath(self.normalize(directory_path))
        names: set[str] = set()

        for candidate in self.created_files | self.created_dirs:
            candidate_path = PurePosixPath(candidate)
            if candidate_path.parent == directory:
                names.add(candidate_path.name)

        return names
