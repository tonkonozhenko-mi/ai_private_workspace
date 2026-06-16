from dataclasses import dataclass
from pathlib import PurePosixPath

from app.core.domain.workspace_file import WorkspaceFileWriteResult
from app.core.ports.file_system import FileSystemPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)


@dataclass(frozen=True)
class WriteWorkspaceFileInput:
    workspace_id: str
    relative_path: str
    content: str
    overwrite: bool = False


class WriteWorkspaceFileNotFoundError(ValueError):
    pass


class WriteWorkspaceFileValidationError(ValueError):
    pass


class WriteWorkspaceFileUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        file_system: FileSystemPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.file_system = file_system
        self.timeline_repository = timeline_repository

    def execute(self, request: WriteWorkspaceFileInput) -> WorkspaceFileWriteResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WriteWorkspaceFileNotFoundError("Workspace not found")

        relative_path = self._validate_relative_path(request.relative_path)
        try:
            replaced_existing = self.file_system.write_text_file(
                workspace.project_path,
                relative_path,
                request.content,
                overwrite=request.overwrite,
            )
        except (FileExistsError, OSError, ValueError) as exc:
            raise WriteWorkspaceFileValidationError(str(exc)) from exc

        result = WorkspaceFileWriteResult(
            workspace_id=workspace.id,
            relative_path=relative_path,
            bytes_written=len(request.content.encode("utf-8")),
            replaced_existing=replaced_existing,
            status="replaced" if replaced_existing else "created",
        )
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=workspace.id,
                    event_type="workspace_file_written",
                    title="Workspace file saved",
                    summary=f"{result.status.title()} {relative_path}.",
                    metadata={
                        "relative_path": relative_path,
                        "status": result.status,
                        "bytes_written": str(result.bytes_written),
                    },
                )
            )
        return result

    @staticmethod
    def _validate_relative_path(value: str) -> str:
        normalized = value.strip().replace("\\", "/")
        path = PurePosixPath(normalized)
        if not normalized or path.is_absolute() or ".." in path.parts:
            raise WriteWorkspaceFileValidationError("Use a relative path inside the workspace")
        if normalized.endswith("/") or path.name in {"", ".", ".."}:
            raise WriteWorkspaceFileValidationError("Target path must name a file")
        return path.as_posix()
