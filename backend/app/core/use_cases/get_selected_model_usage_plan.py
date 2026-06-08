from dataclasses import dataclass

from app.core.domain.selected_model_usage_plan import (
    SelectedModelUsageCapability,
    SelectedModelUsagePlan,
)
from app.core.domain.workspace_model_selection import WorkspaceSelectedModel
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.llm_provider_factory import LLMProviderFactoryPort
from app.core.ports.workspace_model_selection_repository import (
    WorkspaceModelSelectionRepositoryPort,
)
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class GetSelectedModelUsagePlanInput:
    workspace_id: str


class SelectedModelUsagePlanNotFoundError(ValueError):
    pass


class GetSelectedModelUsagePlanUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        selection_repository: WorkspaceModelSelectionRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        llm_provider_factory: LLMProviderFactoryPort,
        configuration: dict[str, str],
    ) -> None:
        self.workspace_repository = workspace_repository
        self.selection_repository = selection_repository
        self.index_status_repository = index_status_repository
        self.llm_provider_factory = llm_provider_factory
        self.configuration = dict(configuration)

    def execute(
        self,
        request: GetSelectedModelUsagePlanInput,
    ) -> SelectedModelUsagePlan:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise SelectedModelUsagePlanNotFoundError("Workspace not found")

        selection = self.selection_repository.get(request.workspace_id)
        selected_llm = selection.selected_llm if selection is not None else None
        selected_embedding = (
            selection.selected_embedding if selection is not None else None
        )
        active_llm_provider, active_llm_model = self._active_model("llm")
        active_embedding_provider, active_embedding_model = self._active_model(
            "embedding"
        )
        saved_index_status = self.index_status_repository.get(request.workspace_id)
        index_status = (
            saved_index_status.status
            if saved_index_status is not None
            else "not_indexed"
        )

        llm_capability = self._llm_capability(selected_llm)
        embedding_index_capability = self._embedding_index_capability(
            selected_embedding,
            active_embedding_provider,
            active_embedding_model,
        )
        embedding_search_capability = self._embedding_search_capability(
            selected_embedding,
            active_embedding_provider,
            active_embedding_model,
            index_status,
        )
        can_use_fully = (
            llm_capability.available
            and embedding_search_capability.available
            and index_status == "indexed"
        )

        return SelectedModelUsagePlan(
            workspace_id=request.workspace_id,
            can_ask_with_selected_llm=llm_capability.available,
            can_index_with_selected_embedding=embedding_index_capability.available,
            can_search_with_selected_embedding=embedding_search_capability.available,
            can_use_selected_models_fully=can_use_fully,
            selected_llm_provider=selected_llm.provider if selected_llm else None,
            selected_llm_model=selected_llm.model if selected_llm else None,
            selected_embedding_provider=(
                selected_embedding.provider if selected_embedding else None
            ),
            selected_embedding_model=(
                selected_embedding.model if selected_embedding else None
            ),
            active_llm_provider=active_llm_provider,
            active_llm_model=active_llm_model,
            active_embedding_provider=active_embedding_provider,
            active_embedding_model=active_embedding_model,
            index_status=index_status,
            capabilities=[
                llm_capability,
                embedding_index_capability,
                embedding_search_capability,
            ],
            recommended_actions=self._recommended_actions(
                selected_llm=selected_llm,
                selected_embedding=selected_embedding,
                llm_capability=llm_capability,
                active_embedding_provider=active_embedding_provider,
                active_embedding_model=active_embedding_model,
                index_status=index_status,
                can_search_with_selected_embedding=(
                    embedding_search_capability.available
                ),
            ),
            notes=[
                (
                    "Selected LLMs can be used per request only when their provider "
                    "is supported by the LLM provider factory."
                ),
                (
                    "Selected embedding models cannot be applied per request; "
                    "indexing and search use the active embedding configuration."
                ),
                "This plan is advisory and does not change runtime settings or reindex.",
            ],
        )

    def _llm_capability(
        self,
        selected: WorkspaceSelectedModel | None,
    ) -> SelectedModelUsageCapability:
        if selected is None:
            return SelectedModelUsageCapability(
                id="ask_with_selected_llm",
                available=False,
                status="not_selected",
                reason="No workspace LLM selection has been saved.",
            )
        if not self.llm_provider_factory.supports(selected.provider):
            return SelectedModelUsageCapability(
                id="ask_with_selected_llm",
                available=False,
                status="blocked",
                reason=(
                    f"The selected LLM provider '{selected.provider}' is not "
                    "supported by the current LLM provider factory."
                ),
            )
        return SelectedModelUsageCapability(
            id="ask_with_selected_llm",
            available=True,
            status="ready",
            reason=(
                "/ask can use the selected LLM through a per-request provider "
                "and model override without restarting the backend."
            ),
        )

    @staticmethod
    def _embedding_index_capability(
        selected: WorkspaceSelectedModel | None,
        active_provider: str,
        active_model: str,
    ) -> SelectedModelUsageCapability:
        if selected is None:
            return SelectedModelUsageCapability(
                id="index_with_selected_embedding",
                available=False,
                status="not_selected",
                reason="No workspace embedding model selection has been saved.",
            )
        if not GetSelectedModelUsagePlanUseCase._matches(
            selected,
            active_provider,
            active_model,
        ):
            return SelectedModelUsageCapability(
                id="index_with_selected_embedding",
                available=False,
                status="needs_action",
                reason=(
                    "The selected embedding model does not match the active "
                    "embedding configuration."
                ),
            )
        return SelectedModelUsageCapability(
            id="index_with_selected_embedding",
            available=True,
            status="ready",
            reason="Indexing can use the selected active embedding model.",
        )

    @staticmethod
    def _embedding_search_capability(
        selected: WorkspaceSelectedModel | None,
        active_provider: str,
        active_model: str,
        index_status: str,
    ) -> SelectedModelUsageCapability:
        if selected is None:
            return SelectedModelUsageCapability(
                id="search_with_selected_embedding",
                available=False,
                status="not_selected",
                reason="No workspace embedding model selection has been saved.",
            )
        if not GetSelectedModelUsagePlanUseCase._matches(
            selected,
            active_provider,
            active_model,
        ):
            return SelectedModelUsageCapability(
                id="search_with_selected_embedding",
                available=False,
                status="needs_action",
                reason=(
                    "Search cannot use the selected embedding space until the "
                    "active configuration is changed and the workspace is reindexed."
                ),
            )
        if index_status != "indexed":
            return SelectedModelUsageCapability(
                id="search_with_selected_embedding",
                available=False,
                status="needs_action",
                reason=(
                    "The selected embedding model is active, but workspace context "
                    "is not indexed."
                ),
            )
        return SelectedModelUsageCapability(
            id="search_with_selected_embedding",
            available=True,
            status="ready",
            reason="Search can use the indexed selected embedding space.",
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

    def _recommended_actions(
        self,
        *,
        selected_llm: WorkspaceSelectedModel | None,
        selected_embedding: WorkspaceSelectedModel | None,
        llm_capability: SelectedModelUsageCapability,
        active_embedding_provider: str,
        active_embedding_model: str,
        index_status: str,
        can_search_with_selected_embedding: bool,
    ) -> list[str]:
        actions: list[str] = []

        if selected_llm is None:
            actions.append("Select an LLM for this workspace.")
        if selected_embedding is None:
            actions.append("Select an embedding model for this workspace.")

        if selected_llm is not None and not llm_capability.available:
            actions.append(
                f"Configure a compatible LLM provider adapter for "
                f"{selected_llm.provider}/{selected_llm.model}."
            )

        embedding_matches = (
            selected_embedding is not None
            and self._matches(
                selected_embedding,
                active_embedding_provider,
                active_embedding_model,
            )
        )
        if selected_embedding is not None and not embedding_matches:
            actions.append(
                "Restart backend with the selected embedding provider and model "
                "configuration."
            )
        if selected_embedding is not None and (
            not embedding_matches or index_status != "indexed"
        ):
            actions.append("Reindex workspace context with the selected embedding model.")

        if llm_capability.available and can_search_with_selected_embedding:
            actions.append(
                "Ask a workspace question using the selected LLM per-request override."
            )
        return actions
