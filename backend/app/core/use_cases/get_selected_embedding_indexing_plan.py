from dataclasses import dataclass

from app.core.domain.selected_embedding_indexing_plan import (
    SelectedEmbeddingIndexingPlan,
)
from app.core.domain.workspace_model_selection import WorkspaceSelectedModel
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.workspace_model_selection_repository import (
    WorkspaceModelSelectionRepositoryPort,
)
from app.core.ports.workspace_repository import WorkspaceRepositoryPort

VECTOR_SPACE_NOTE = (
    "Changing an embedding provider or model creates a different vector space; "
    "existing vectors cannot be safely searched with the new embedding model."
)
READ_ONLY_NOTE = (
    "This plan is advisory and does not change runtime settings, create vector "
    "collections, or reindex workspace context."
)


@dataclass(frozen=True)
class GetSelectedEmbeddingIndexingPlanInput:
    workspace_id: str


class SelectedEmbeddingIndexingPlanNotFoundError(ValueError):
    pass


class GetSelectedEmbeddingIndexingPlanUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        selection_repository: WorkspaceModelSelectionRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        configuration: dict[str, str],
    ) -> None:
        self.workspace_repository = workspace_repository
        self.selection_repository = selection_repository
        self.index_status_repository = index_status_repository
        self.configuration = dict(configuration)

    def execute(
        self,
        request: GetSelectedEmbeddingIndexingPlanInput,
    ) -> SelectedEmbeddingIndexingPlan:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise SelectedEmbeddingIndexingPlanNotFoundError("Workspace not found")

        selection = self.selection_repository.get(request.workspace_id)
        selected = selection.selected_embedding if selection is not None else None
        active_provider, active_model = self._active_embedding()
        saved_index_status = self.index_status_repository.get(request.workspace_id)
        index_status = (
            saved_index_status.status if saved_index_status is not None else "not_indexed"
        )

        if selected is None:
            return SelectedEmbeddingIndexingPlan(
                workspace_id=request.workspace_id,
                selected_provider=None,
                selected_model=None,
                active_provider=active_provider,
                active_model=active_model,
                index_status=index_status,
                can_index_now=False,
                can_search_now=False,
                requires_backend_restart=False,
                requires_reindex=False,
                requires_new_vector_collection=False,
                plan_status="not_selected",
                recommended_actions=["Select an embedding model for this workspace."],
                warnings=[],
                notes=[READ_ONLY_NOTE, VECTOR_SPACE_NOTE],
            )

        if not self._matches(selected, active_provider, active_model):
            return SelectedEmbeddingIndexingPlan(
                workspace_id=request.workspace_id,
                selected_provider=selected.provider,
                selected_model=selected.model,
                active_provider=active_provider,
                active_model=active_model,
                index_status=index_status,
                can_index_now=False,
                can_search_now=False,
                requires_backend_restart=True,
                requires_reindex=True,
                requires_new_vector_collection=True,
                plan_status="runtime_mismatch",
                recommended_actions=[
                    (
                        "Restart backend with the selected embedding provider and "
                        "model configuration."
                    ),
                    "Reindex workspace context after restart.",
                ],
                warnings=[("Selected embedding cannot be used until active runtime matches it.")],
                notes=[READ_ONLY_NOTE, VECTOR_SPACE_NOTE],
            )

        if index_status != "indexed":
            return SelectedEmbeddingIndexingPlan(
                workspace_id=request.workspace_id,
                selected_provider=selected.provider,
                selected_model=selected.model,
                active_provider=active_provider,
                active_model=active_model,
                index_status=index_status,
                can_index_now=True,
                can_search_now=False,
                requires_backend_restart=False,
                requires_reindex=True,
                requires_new_vector_collection=False,
                plan_status="needs_index",
                recommended_actions=["Index workspace context with the selected embedding model."],
                warnings=[],
                notes=[READ_ONLY_NOTE, VECTOR_SPACE_NOTE],
            )

        return SelectedEmbeddingIndexingPlan(
            workspace_id=request.workspace_id,
            selected_provider=selected.provider,
            selected_model=selected.model,
            active_provider=active_provider,
            active_model=active_model,
            index_status=index_status,
            can_index_now=True,
            can_search_now=True,
            requires_backend_restart=False,
            requires_reindex=False,
            requires_new_vector_collection=False,
            plan_status="ready",
            recommended_actions=["Ask a workspace question or search workspace context."],
            warnings=[],
            notes=[READ_ONLY_NOTE, VECTOR_SPACE_NOTE],
        )

    def _active_embedding(self) -> tuple[str, str]:
        provider = self.configuration.get("EMBEDDING_PROVIDER", "").lower()
        # Ollama and the built-in llama.cpp engine both identify the embedder by
        # the configured model name (the GGUF id matches the Ollama tag, e.g.
        # "nomic-embed-text"), so resolve them the same way.
        if provider in ("ollama", "llamacpp"):
            return provider, self.configuration.get("OLLAMA_EMBEDDING_MODEL", "")
        if provider == "fake":
            return provider, "fake-embedding"
        return provider, ""

    @staticmethod
    def _matches(
        selected: WorkspaceSelectedModel,
        active_provider: str,
        active_model: str,
    ) -> bool:
        return (
            selected.provider.lower() == active_provider.lower()
            and selected.model.lower() == active_model.lower()
        )
