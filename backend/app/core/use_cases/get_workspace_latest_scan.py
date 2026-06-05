from dataclasses import dataclass

from app.core.domain.project_scan import ProjectScanResult
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort


@dataclass(frozen=True)
class GetWorkspaceLatestScanInput:
    workspace_id: str


class GetWorkspaceLatestScanUseCase:
    def __init__(self, project_scan_repository: ProjectScanRepositoryPort) -> None:
        self.project_scan_repository = project_scan_repository

    def execute(self, request: GetWorkspaceLatestScanInput) -> ProjectScanResult | None:
        return self.project_scan_repository.get_latest_scan(request.workspace_id)
