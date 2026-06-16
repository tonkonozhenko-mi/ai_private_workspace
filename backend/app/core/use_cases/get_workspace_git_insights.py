from dataclasses import dataclass

from app.core.domain.git_insights import GitInsights
from app.core.ports.git_history import GitHistoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class GetWorkspaceGitInsightsInput:
    workspace_id: str


class WorkspaceGitInsightsNotFoundError(ValueError):
    pass


class GetWorkspaceGitInsightsUseCase:
    """Read-only git history snapshot for a workspace's project directory."""

    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        git_history: GitHistoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.git_history = git_history

    def execute(self, request: GetWorkspaceGitInsightsInput) -> GitInsights:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WorkspaceGitInsightsNotFoundError("Workspace not found")
        return self.git_history.read_insights(workspace.project_path)
