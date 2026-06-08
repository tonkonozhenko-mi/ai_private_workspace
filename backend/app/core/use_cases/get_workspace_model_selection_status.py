from dataclasses import dataclass

from app.core.domain.workspace_model_selection import WorkspaceSelectedModel
from app.core.domain.workspace_model_selection_status import (
    SelectedModelRuntimeStatus,
    WorkspaceModelSelectionStatus,
)
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.workspace_model_selection_repository import (
    WorkspaceModelSelectionRepositoryPort,
)
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


STATUS_NOTES = [
    "Model selection status is advisory and does not change active runtime settings.",
    "Installed model availability is not checked by this endpoint.",
]


@dataclass(frozen=True)
class GetWorkspaceModelSelectionStatusInput:
    workspace_id: str


class WorkspaceModelSelectionStatusNotFoundError(ValueError):
    pass


class GetWorkspaceModelSelectionStatusUseCase:
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
        request: GetWorkspaceModelSelectionStatusInput,
    ) -> WorkspaceModelSelectionStatus:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise WorkspaceModelSelectionStatusNotFoundError("Workspace not found")

        selection = self.selection_repository.get(request.workspace_id)
        selected_llm = selection.selected_llm if selection is not None else None
        selected_embedding = (
            selection.selected_embedding if selection is not None else None
        )
        index_status = self.index_status_repository.get(request.workspace_id)
        is_indexed = index_status is not None and index_status.status == "indexed"

        llm_status = self._llm_status(selected_llm)
        embedding_status = self._embedding_status(
            selected_embedding,
            is_indexed=is_indexed,
        )
        return WorkspaceModelSelectionStatus(
            workspace_id=request.workspace_id,
            llm_status=llm_status,
            embedding_status=embedding_status,
            overall_status=self._overall_status(llm_status, embedding_status),
            recommended_actions=self._recommended_actions(
                llm_status,
                embedding_status,
            ),
            notes=[
                *STATUS_NOTES,
                f"Workspace index status: {index_status.status if index_status else 'not_indexed'}.",
            ],
        )

    def _llm_status(
        self,
        selected: WorkspaceSelectedModel | None,
    ) -> SelectedModelRuntimeStatus:
        active_provider, active_model = self._active_model("llm")
        if selected is None:
            return self._not_selected("llm", active_provider, active_model)
        matches = self._matches(selected, active_provider, active_model)
        if matches:
            return SelectedModelRuntimeStatus(
                model_type="llm",
                selected_provider=selected.provider,
                selected_model=selected.model,
                active_provider=active_provider,
                active_model=active_model,
                matches_active_runtime=True,
                requires_backend_restart=False,
                requires_reindex=False,
                status="ready",
                message="Selected LLM matches active runtime configuration.",
            )
        return SelectedModelRuntimeStatus(
            model_type="llm",
            selected_provider=selected.provider,
            selected_model=selected.model,
            active_provider=active_provider,
            active_model=active_model,
            matches_active_runtime=False,
            requires_backend_restart=True,
            requires_reindex=False,
            status="runtime_mismatch",
            message="Selected LLM does not match active runtime configuration.",
        )

    def _embedding_status(
        self,
        selected: WorkspaceSelectedModel | None,
        *,
        is_indexed: bool,
    ) -> SelectedModelRuntimeStatus:
        active_provider, active_model = self._active_model("embedding")
        if selected is None:
            return self._not_selected("embedding", active_provider, active_model)
        matches = self._matches(selected, active_provider, active_model)
        if not matches:
            return SelectedModelRuntimeStatus(
                model_type="embedding",
                selected_provider=selected.provider,
                selected_model=selected.model,
                active_provider=active_provider,
                active_model=active_model,
                matches_active_runtime=False,
                requires_backend_restart=True,
                requires_reindex=True,
                status="runtime_mismatch",
                message=(
                    "Selected embedding model does not match active runtime "
                    "configuration and requires reindexing after restart."
                ),
            )
        if not is_indexed:
            return SelectedModelRuntimeStatus(
                model_type="embedding",
                selected_provider=selected.provider,
                selected_model=selected.model,
                active_provider=active_provider,
                active_model=active_model,
                matches_active_runtime=True,
                requires_backend_restart=False,
                requires_reindex=True,
                status="requires_reindex",
                message=(
                    "Selected embedding model matches active runtime, but workspace "
                    "context must be indexed."
                ),
            )
        return SelectedModelRuntimeStatus(
            model_type="embedding",
            selected_provider=selected.provider,
            selected_model=selected.model,
            active_provider=active_provider,
            active_model=active_model,
            matches_active_runtime=True,
            requires_backend_restart=False,
            requires_reindex=False,
            status="ready",
            message=(
                "Selected embedding model matches active runtime and workspace "
                "context is indexed."
            ),
        )

    def _active_model(self, model_type: str) -> tuple[str, str]:
        if model_type == "llm":
            provider = self.configuration.get("LLM_PROVIDER", "").lower()
            ollama_model = self.configuration.get("OLLAMA_LLM_MODEL", "")
            fake_model = "fake-llm"
        else:
            provider = self.configuration.get("EMBEDDING_PROVIDER", "").lower()
            ollama_model = self.configuration.get("OLLAMA_EMBEDDING_MODEL", "")
            fake_model = "fake-embedding"

        if provider == "ollama":
            return provider, ollama_model
        if provider == "fake":
            return provider, fake_model
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

    @staticmethod
    def _not_selected(
        model_type: str,
        active_provider: str,
        active_model: str,
    ) -> SelectedModelRuntimeStatus:
        label = "LLM" if model_type == "llm" else "embedding model"
        return SelectedModelRuntimeStatus(
            model_type=model_type,
            selected_provider=None,
            selected_model=None,
            active_provider=active_provider,
            active_model=active_model,
            matches_active_runtime=False,
            requires_backend_restart=False,
            requires_reindex=False,
            status="not_selected",
            message=f"No workspace {label} selection has been saved.",
        )

    @staticmethod
    def _overall_status(
        llm_status: SelectedModelRuntimeStatus,
        embedding_status: SelectedModelRuntimeStatus,
    ) -> str:
        if llm_status.status == "not_selected" and embedding_status.status == "not_selected":
            return "not_configured"
        if embedding_status.requires_reindex:
            return "requires_reindex"
        if (
            llm_status.status == "runtime_mismatch"
            or embedding_status.status == "runtime_mismatch"
        ):
            return "runtime_mismatch"
        return "ready"

    @staticmethod
    def _recommended_actions(
        llm_status: SelectedModelRuntimeStatus,
        embedding_status: SelectedModelRuntimeStatus,
    ) -> list[str]:
        actions: list[str] = []
        if llm_status.status == "not_selected":
            actions.append("Select an LLM for this workspace.")
        elif llm_status.requires_backend_restart:
            actions.append(
                "Restart backend with the selected LLM provider and model configuration."
            )

        if embedding_status.status == "not_selected":
            actions.append("Select an embedding model for this workspace.")
        elif embedding_status.requires_backend_restart:
            actions.append(
                "Restart backend with the selected embedding provider and model configuration."
            )
        if embedding_status.requires_reindex:
            actions.append("Reindex workspace context with the selected embedding model.")

        if (
            llm_status.status == "ready"
            and embedding_status.status == "ready"
        ):
            actions.append("Ask a workspace question.")
        return actions
