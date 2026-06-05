from typing import Protocol

from app.core.domain.project_scan import ProjectFile


class FileSystemPort(Protocol):
    def list_files(self, root_path: str) -> list[ProjectFile]:
        """Return project files discovered under a root path."""

    def path_exists(self, path: str) -> bool:
        """Return whether a path exists."""

    def is_directory(self, path: str) -> bool:
        """Return whether a path points to a directory."""
