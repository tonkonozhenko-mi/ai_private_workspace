from dataclasses import dataclass

from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.core.domain.workspace_model_selection import (
    EMPTY_SELECTION_NOTE,
    PREFERENCE_ONLY_NOTE,
    UNKNOWN_CATALOG_NOTE,
    WorkspaceModelSelection,
    WorkspaceSelectedModel,
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
        model_catalog_registry: ModelCatalogRegistry | None = None,
        configuration: dict[str, str] | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.selection_repository = selection_repository
        self.model_catalog_registry = model_catalog_registry
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
        elif self.model_catalog_registry is not None:
            selection = self._with_current_catalog_notes(selection)
        return with_runtime_match_notes(selection, self.configuration)

    def _with_current_catalog_notes(
        self,
        selection: WorkspaceModelSelection,
    ) -> WorkspaceModelSelection:
        notes = [note for note in selection.notes if note != UNKNOWN_CATALOG_NOTE]
        if any(
            selected is not None and not self._is_known_model(selected)
            for selected in (selection.selected_llm, selection.selected_embedding)
        ):
            notes.append(UNKNOWN_CATALOG_NOTE)
        return WorkspaceModelSelection(
            workspace_id=selection.workspace_id,
            selected_llm=selection.selected_llm,
            selected_embedding=selection.selected_embedding,
            notes=list(dict.fromkeys(notes)),
        )

    def _is_known_model(self, selected: WorkspaceSelectedModel) -> bool:
        return any(
            model.provider.lower() == selected.provider.lower()
            and model.model_name.lower() == selected.model.lower()
            and model.model_type == selected.model_type
            for model in self.model_catalog_registry.list_models()
        )
