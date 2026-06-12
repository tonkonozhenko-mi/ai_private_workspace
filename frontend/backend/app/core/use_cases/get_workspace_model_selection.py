from dataclasses import dataclass

from app.core.domain.workspace_model_selection import (
    EMPTY_SELECTION_NOTE,
    PREFERENCE_ONLY_NOTE,
    WorkspaceModelSelection,
    with_runtime_match_notes,
)
from app.core.ports.workspace_model_selection_repository import (
    WorkspaceModelSelectionRepositoryPort,
)
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class GetWorkspaceModelSelectionInput:
    workspace_id: str


class WorkspaceModelSelectionNotFoundError(ValueError):
    pass


class GetWorkspaceModelSelectionUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        selection_repository: WorkspaceModelSelectionRepositoryPort,
        configuration: dict[str, str] | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.selection_repository = selection_repository
        self.configuration = dict(configuration or {})

    def execute(
        self,
        request: GetWorkspaceModelSelectionInput,
    ) -> WorkspaceModelSelection:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise WorkspaceModelSelectionNotFoundError("Workspace not found")

        selection = self.selection_repository.get(request.workspace_id)
        if selection is None:
            selection = WorkspaceModelSelection(
                workspace_id=request.workspace_id,
                selected_llm=None,
                selected_embedding=None,
                notes=[EMPTY_SELECTION_NOTE, PREFERENCE_ONLY_NOTE],
            )
        return with_runtime_match_notes(selection, self.configuration)
