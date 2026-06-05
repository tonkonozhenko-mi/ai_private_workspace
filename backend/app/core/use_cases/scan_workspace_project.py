from dataclasses import dataclass

from app.core.domain.project_scan import ProjectScanResult
from app.core.domain.skill_registry import SkillRegistry
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.scan_project import ScanProjectInput, ScanProjectUseCase


@dataclass(frozen=True)
class ScanWorkspaceProjectInput:
    workspace_id: str


class WorkspaceNotFoundError(ValueError):
    pass


class ScanWorkspaceProjectUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        file_system: FileSystemPort,
        project_scan_repository: ProjectScanRepositoryPort,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.file_system = file_system
        self.project_scan_repository = project_scan_repository
        self.skill_registry = skill_registry

    def execute(self, request: ScanWorkspaceProjectInput) -> ProjectScanResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("Workspace not found")

        scan_result = ScanProjectUseCase(
            file_system=self.file_system,
            skill_registry=self.skill_registry,
        ).execute(ScanProjectInput(project_path=workspace.project_path))

        self.project_scan_repository.save_latest_scan(
            workspace_id=request.workspace_id,
            scan_result=scan_result,
        )
        return scan_result
