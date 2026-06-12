from dataclasses import dataclass

from app.core.domain.indexing_rules import IndexingRulesProfile, default_indexing_rules
from app.core.ports.indexing_rules_repository import IndexingRulesRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class GetWorkspaceIndexingRulesInput:
    workspace_id: str


class GetWorkspaceIndexingRulesNotFoundError(ValueError):
    pass


class GetWorkspaceIndexingRulesUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        indexing_rules_repository: IndexingRulesRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.indexing_rules_repository = indexing_rules_repository

    def execute(self, request: GetWorkspaceIndexingRulesInput) -> IndexingRulesProfile:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise GetWorkspaceIndexingRulesNotFoundError("Workspace not found")
        return self.indexing_rules_repository.get(request.workspace_id) or default_indexing_rules(
            request.workspace_id
        )
