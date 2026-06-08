from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.core.domain.workspace_model_selection import (
    EMBEDDING_CHANGE_NOTE,
    PREFERENCE_ONLY_NOTE,
    UNKNOWN_CATALOG_NOTE,
    WorkspaceModelSelection,
    WorkspaceSelectedModel,
    with_runtime_match_notes,
)
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_model_selection_repository import (
    WorkspaceModelSelectionRepositoryPort,
)
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)


ALLOWED_MODEL_TYPES = {"llm", "embedding"}


@dataclass(frozen=True)
class UpdateWorkspaceModelSelectionInput:
    workspace_id: str
    provider: str
    model: str
    model_type: str
    selected_reason: str | None = None


class UpdateWorkspaceModelSelectionNotFoundError(ValueError):
    pass


class UpdateWorkspaceModelSelectionValidationError(ValueError):
    pass


class UpdateWorkspaceModelSelectionUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        selection_repository: WorkspaceModelSelectionRepositoryPort,
        model_catalog_registry: ModelCatalogRegistry,
        timeline_repository: TimelineRepositoryPort | None = None,
        configuration: dict[str, str] | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.selection_repository = selection_repository
        self.model_catalog_registry = model_catalog_registry
        self.timeline_repository = timeline_repository
        self.configuration = dict(configuration or {})

    def execute(
        self,
        request: UpdateWorkspaceModelSelectionInput,
    ) -> WorkspaceModelSelection:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise UpdateWorkspaceModelSelectionNotFoundError("Workspace not found")

        provider = request.provider.strip().lower()
        model = request.model.strip()
        model_type = request.model_type.strip().lower()
        if not provider or not model:
            raise UpdateWorkspaceModelSelectionValidationError(
                "Provider and model are required"
            )
        if model_type not in ALLOWED_MODEL_TYPES:
            raise UpdateWorkspaceModelSelectionValidationError(
                f"Unknown model type: {request.model_type}"
            )

        selected_reason = (
            request.selected_reason.strip()
            if request.selected_reason is not None
            else None
        )
        if selected_reason == "":
            selected_reason = None
        selected_model = WorkspaceSelectedModel(
            provider=provider,
            model=model,
            model_type=model_type,
            selected_at=datetime.now(UTC).isoformat(),
            selected_reason=selected_reason,
        )
        current = self.selection_repository.get(request.workspace_id)
        selected_llm = current.selected_llm if current is not None else None
        selected_embedding = (
            current.selected_embedding if current is not None else None
        )
        embedding_changed = False
        if model_type == "llm":
            selected_llm = selected_model
        else:
            embedding_changed = (
                selected_embedding is not None
                and (
                    selected_embedding.provider != provider
                    or selected_embedding.model != model
                )
            )
            selected_embedding = selected_model

        notes = [PREFERENCE_ONLY_NOTE]
        if self._has_unknown_selection(selected_llm, selected_embedding):
            notes.append(UNKNOWN_CATALOG_NOTE)
        if embedding_changed or (
            current is not None and EMBEDDING_CHANGE_NOTE in current.notes
        ):
            notes.append(EMBEDDING_CHANGE_NOTE)

        saved = self.selection_repository.save(
            WorkspaceModelSelection(
                workspace_id=request.workspace_id,
                selected_llm=selected_llm,
                selected_embedding=selected_embedding,
                notes=notes,
            )
        )
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=request.workspace_id,
                    event_type="workspace_model_selected",
                    title="Workspace model selected",
                    summary=f"Selected {provider}/{model} for {model_type}.",
                    metadata={
                        "provider": provider,
                        "model": model,
                        "model_type": model_type,
                    },
                )
            )
        return with_runtime_match_notes(saved, self.configuration)

    def _has_unknown_selection(
        self,
        selected_llm: WorkspaceSelectedModel | None,
        selected_embedding: WorkspaceSelectedModel | None,
    ) -> bool:
        return any(
            selected is not None and not self._is_known_model(selected)
            for selected in (selected_llm, selected_embedding)
        )

    def _is_known_model(self, selected: WorkspaceSelectedModel) -> bool:
        return any(
            model.provider.lower() == selected.provider.lower()
            and model.model_name.lower() == selected.model.lower()
            and model.model_type == selected.model_type
            for model in self.model_catalog_registry.list_models()
        )
