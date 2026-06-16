from dataclasses import dataclass

from app.core.domain.project_scan import ProjectFile
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.scan_project import ScanProjectInput, ScanProjectUseCase


@dataclass(frozen=True)
class GetWorkspaceScanChangesInput:
    workspace_id: str
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanChanges:
    has_baseline: bool
    changed: bool
    added_count: int
    removed_count: int
    modified_count: int
    current_file_count: int
    previous_file_count: int


class WorkspaceScanChangesWorkspaceNotFoundError(ValueError):
    pass


class GetWorkspaceScanChangesUseCase:
    """Read-only detection of on-disk changes since the last saved scan.

    This use case never re-scans for persistence, never indexes, and never
    mutates any stored state. It walks the project directory live using the
    exact same walk + file-selection rules the scan uses (via
    ``ScanProjectUseCase``, whose ``execute`` does not persist) and diffs the
    resulting file set against the stored latest scan.
    """

    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system

    def execute(self, request: GetWorkspaceScanChangesInput) -> ScanChanges:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WorkspaceScanChangesWorkspaceNotFoundError("Workspace not found")

        stored_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if stored_scan is None:
            return ScanChanges(
                has_baseline=False,
                changed=False,
                added_count=0,
                removed_count=0,
                modified_count=0,
                current_file_count=0,
                previous_file_count=0,
            )

        current_scan = ScanProjectUseCase(file_system=self.file_system).execute(
            ScanProjectInput(
                project_path=workspace.project_path,
                include_patterns=request.include_patterns,
                exclude_patterns=request.exclude_patterns,
            )
        )

        current_files = self._index_files(current_scan.files)
        previous_files = self._index_files(stored_scan.files)

        current_paths = set(current_files)
        previous_paths = set(previous_files)

        added_count = len(current_paths - previous_paths)
        removed_count = len(previous_paths - current_paths)

        modified_count = 0
        for path in current_paths & previous_paths:
            current_size, current_mtime = current_files[path]
            previous_size, previous_mtime = previous_files[path]
            if current_size != previous_size or (
                current_mtime is not None
                and previous_mtime is not None
                and current_mtime != previous_mtime
            ):
                modified_count += 1

        total_changes = added_count + removed_count + modified_count
        return ScanChanges(
            has_baseline=True,
            changed=total_changes > 0,
            added_count=added_count,
            removed_count=removed_count,
            modified_count=modified_count,
            current_file_count=len(current_paths),
            previous_file_count=len(previous_paths),
        )

    @staticmethod
    def _index_files(
        files: list[ProjectFile],
    ) -> dict[str, tuple[int, float | None]]:
        return {
            project_file.path: (project_file.size_bytes, project_file.modified_at)
            for project_file in files
        }
