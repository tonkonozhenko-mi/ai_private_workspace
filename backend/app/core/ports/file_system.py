from collections.abc import Callable
from typing import Protocol

from app.core.domain.project_scan import ProjectFile


class FileSystemPort(Protocol):
    def list_files(
        self,
        root_path: str,
        respect_gitignore: bool = True,
        progress: Callable[[int], None] | None = None,
    ) -> list[ProjectFile]:
        """Return project files discovered under a root path.

        When ``respect_gitignore`` is set, directories the project's .gitignore
        ignores are skipped during discovery (a performance optimization; the scan
        drops those files regardless).

        ``progress`` is called with the running file count as the walk descends, so a
        slow-but-healthy enumeration can be told apart from one that is stuck. Must
        raise ``FolderPermissionError`` when the root itself cannot be read.
        """

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
