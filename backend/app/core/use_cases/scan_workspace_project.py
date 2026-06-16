from collections.abc import Callable
from dataclasses import dataclass

from app.core.domain.project_scan import ProjectScanResult
from app.core.domain.skill_registry import SkillRegistry
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)
from app.core.use_cases.scan_project import ScanProjectInput, ScanProjectUseCase


@dataclass(frozen=True)
class ScanWorkspaceProjectInput:
    workspace_id: str
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()
    file_rules_profile: str | None = None
    cancellation_check: Callable[[], bool] | None = None
    progress_callback: Callable[[int, int, str], None] | None = None


class WorkspaceNotFoundError(ValueError):
    pass


class ScanWorkspaceProjectUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        file_system: FileSystemPort,
        project_scan_repository: ProjectScanRepositoryPort,
        skill_registry: SkillRegistry | None = None,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.file_system = file_system
        self.project_scan_repository = project_scan_repository
        self.skill_registry = skill_registry
        self.timeline_repository = timeline_repository

    def execute(self, request: ScanWorkspaceProjectInput) -> ProjectScanResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("Workspace not found")

        scan_result = ScanProjectUseCase(
            file_system=self.file_system,
            skill_registry=self.skill_registry,
        ).execute(
            ScanProjectInput(
                project_path=workspace.project_path,
                include_patterns=request.include_patterns,
                exclude_patterns=request.exclude_patterns,
                cancellation_check=request.cancellation_check,
                progress_callback=request.progress_callback,
            )
        )

        self.project_scan_repository.save_latest_scan(
            workspace_id=request.workspace_id,
            scan_result=scan_result,
        )
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=request.workspace_id,
                    event_type="project_scanned",
                    title="Project scanned",
                    summary=(
                        f"Scanned {scan_result.scanned_files} files and detected "
                        f"{len(scan_result.detected_skills)} skills."
                    ),
                    metadata={
                        "total_files": str(scan_result.total_files),
                        "detected_skills_count": str(len(scan_result.detected_skills)),
                        "include_rules_count": str(len(request.include_patterns)),
                        "exclude_rules_count": str(len(request.exclude_patterns)),
                        "include_patterns": _join_patterns(request.include_patterns) or "All files",
                        "exclude_patterns": _join_patterns(request.exclude_patterns)
                        or "No exclusions",
                        "file_rules_profile": request.file_rules_profile or "none",
                    },
                )
            )
        return scan_result


def _join_patterns(patterns: tuple[str, ...]) -> str:
    return " · ".join(pattern for pattern in patterns if pattern.strip())
