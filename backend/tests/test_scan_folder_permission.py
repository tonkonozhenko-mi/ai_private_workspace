"""A folder we are not allowed to read must fail loudly, not quietly.

The worst outcome is the one we shipped: os.walk swallows the permission error, the
scan "succeeds" with a smaller file set, and the index is quietly incomplete. The
second worst is the spinner that never stops. Both are fixed here — an unreadable
root is a stage failure carrying the sentence that tells the person what to click.
"""

import pytest

from app.core.domain.folder_access import (
    FOLDER_PERMISSION_MESSAGE,
    FolderPermissionError,
    is_permission_error,
)
from app.core.domain.skill_registry import SkillRegistry
from app.core.use_cases.scan_project import (
    ProjectScanError,
    ScanProjectInput,
    ScanProjectUseCase,
)


class _DeniedFileSystem:
    """The macOS case: the folder is there, the OS will not let us read it."""

    def path_exists(self, path: str) -> bool:
        return True

    def is_directory(self, path: str) -> bool:
        return True

    def list_files(self, root_path, respect_gitignore=True, progress=None):
        raise FolderPermissionError(root_path)

    def read_text_file(self, root_path: str, relative_path: str) -> str:
        return ""


class _SlowFileSystem:
    """A healthy walk: it takes a while, but it keeps counting."""

    def path_exists(self, path: str) -> bool:
        return True

    def is_directory(self, path: str) -> bool:
        return True

    def list_files(self, root_path, respect_gitignore=True, progress=None):
        for count in (10, 200, 3000):
            if progress is not None:
                progress(count)
        return []

    def read_text_file(self, root_path: str, relative_path: str) -> str:
        return ""


def _use_case(file_system):
    return ScanProjectUseCase(file_system=file_system, skill_registry=SkillRegistry())


def test_an_unreadable_folder_fails_the_scan_with_something_actionable():
    with pytest.raises(ProjectScanError) as caught:
        _use_case(_DeniedFileSystem()).execute(
            ScanProjectInput(project_path="/Users/x/Documents/p")
        )

    message = str(caught.value)
    assert message == FOLDER_PERMISSION_MESSAGE
    # The sentence has to name the fix, not the errno.
    assert "System Settings" in message
    assert "Permission denied" not in message


def test_the_walk_reports_progress_so_slow_is_not_mistaken_for_stuck():
    """Without a heartbeat the UI cannot tell a large repository from a scan blocked
    on a permission dialog — which is precisely how ten files took seven minutes."""
    seen: list[tuple[int, int, str]] = []
    _use_case(_SlowFileSystem()).execute(
        ScanProjectInput(
            project_path="/p",
            progress_callback=lambda current, total, message: seen.append(
                (current, total, message)
            ),
        )
    )
    counts = [current for current, _, message in seen if "Enumerating" in message]
    assert counts == [10, 200, 3000]


def test_permission_errors_are_recognised_however_the_platform_spells_them():
    import errno

    assert is_permission_error(PermissionError(errno.EACCES, "denied"))
    assert is_permission_error(OSError(errno.EPERM, "not permitted"))
    assert not is_permission_error(OSError(errno.ENOENT, "missing"))
