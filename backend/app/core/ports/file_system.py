from typing import Protocol

from app.core.domain.project_scan import ProjectFile


class FileSystemPort(Protocol):
    def list_files(self, root_path: str) -> list[ProjectFile]:
        """Return project files discovered under a root path."""

    def path_exists(self, path: str) -> bool:
        """Return whether a path exists."""

    def is_directory(self, path: str) -> bool:
        """Return whether a path points to a directory."""

    def read_text_file(self, root_path: str, relative_path: str) -> str:
        """Read a text file under a root path."""

    def write_text_file(
        self,
        root_path: str,
        relative_path: str,
        content: str,
        overwrite: bool = False,
    ) -> bool:
        """Write a text file under a root path and return whether it replaced a file."""
