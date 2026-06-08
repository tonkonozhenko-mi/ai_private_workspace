from dataclasses import dataclass

from app.core.domain.local_ai_activation_guide import (
    LocalAIActivationGuide,
    LocalAIActivationStep,
)
from app.core.domain.workspace_model_selection import WorkspaceSelectedModel
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.workspace_model_selection_repository import (
    WorkspaceModelSelectionRepositoryPort,
)
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class GetLocalAIActivationGuideInput:
    workspace_id: str


class LocalAIActivationGuideNotFoundError(ValueError):
    pass


class GetLocalAIActivationGuideUseCase:
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
        request: GetLocalAIActivationGuideInput,
    ) -> LocalAIActivationGuide:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise LocalAIActivationGuideNotFoundError("Workspace not found")

        selection = self.selection_repository.get(request.workspace_id)
        selected_llm = selection.selected_llm if selection is not None else None
        selected_embedding = (
            selection.selected_embedding if selection is not None else None
        )
        active_llm_provider, active_llm_model = self._active_model("llm")
        active_embedding_provider, active_embedding_model = self._active_model(
            "embedding"
        )
        active_vector_store = self.configuration.get("VECTOR_STORE", "").lower()
        selected_vector_store = self._selected_vector_store(selected_embedding)
        saved_index_status = self.index_status_repository.get(request.workspace_id)
        index_status = (
            saved_index_status.status
            if saved_index_status is not None
            else "not_indexed"
        )

        llm_matches = self._matches(
            selected_llm,
            active_llm_provider,
            active_llm_model,
        )
        embedding_matches = self._matches(
            selected_embedding,
            active_embedding_provider,
            active_embedding_model,
        )
        vector_store_matches = (
            selected_vector_store is not None
            and selected_vector_store == active_vector_store
        )
        steps = self._steps(
            workspace_id=request.workspace_id,
            selected_llm=selected_llm,
            selected_embedding=selected_embedding,
            selected_vector_store=selected_vector_store,
            active_vector_store=active_vector_store,
            llm_matches=llm_matches,
            embedding_matches=embedding_matches,
            vector_store_matches=vector_store_matches,
            index_status=index_status,
        )

        if selected_llm is None or selected_embedding is None:
            overall_status = "blocked"
        elif (
            llm_matches
            and embedding_matches
            and vector_store_matches
            and index_status == "indexed"
        ):
            overall_status = "ready"
        else:
            overall_status = "needs_setup"

        return LocalAIActivationGuide(
            workspace_id=request.workspace_id,
            overall_status=overall_status,
            selected_llm=self._identity(selected_llm),
            selected_embedding=self._identity(selected_embedding),
            active_llm=f"{active_llm_provider}/{active_llm_model}",
            active_embedding=f"{active_embedding_provider}/{active_embedding_model}",
            selected_vector_store=selected_vector_store,
            active_vector_store=active_vector_store,
            steps=steps,
            notes=[
                "Activation steps are instructions only and are never executed.",
                "Ollama model installation and runtime reachability are not verified.",
                (
                    "Changing the embedding provider or model creates a different "
                    "vector space and requires reindexing."
                ),
            ],
        )

    def _steps(
        self,
        *,
        workspace_id: str,
        selected_llm: WorkspaceSelectedModel | None,
        selected_embedding: WorkspaceSelectedModel | None,
        selected_vector_store: str | None,
        active_vector_store: str,
        llm_matches: bool,
        embedding_matches: bool,
        vector_store_matches: bool,
        index_status: str,
    ) -> list[LocalAIActivationStep]:
        steps = [
            self._selection_step("llm", selected_llm),
            self._selection_step("embedding", selected_embedding),
        ]

        if self._uses_ollama(selected_llm, selected_embedding):
            steps.append(
                LocalAIActivationStep(
                    id="start_ollama",
                    title="Start Ollama",
                    description="Start the local Ollama service if it is not running.",
                    command="ollama serve",
                    status="optional",
                    reason="Ollama reachability is not verified by this guide.",
                    category="ollama",
                )
            )
        if selected_llm is not None and selected_llm.provider.lower() == "ollama":
            steps.append(self._pull_model_step("llm", selected_llm.model))
        if (
            selected_embedding is not None
            and selected_embedding.provider.lower() == "ollama"
        ):
            steps.append(self._pull_model_step("embedding", selected_embedding.model))

        if selected_vector_store == "qdrant":
            qdrant_commands = [
                "podman start qdrant",
                (
                    "podman run -d --name qdrant -p 6333:6333 "
                    "-v qdrant_data:/qdrant/storage "
                    "docker.io/qdrant/qdrant:latest"
                ),
            ]
            steps.append(
                LocalAIActivationStep(
                    id="start_podman_machine",
                    title="Start Podman machine",
                    description=(
                        "Start the Podman machine if the container runtime is not "
                        "already running."
                    ),
                    command="podman machine start",
                    status="optional",
                    reason=(
                        "Podman machine may need to be running before starting Qdrant."
                    ),
                    category="container_runtime",
                )
            )
            steps.append(
                LocalAIActivationStep(
                    id="start_qdrant",
                    title="Start Qdrant",
                    description=(
                        "Use the first command if the container already exists. "
                        "Use the second command only if it does not exist yet."
                    ),
                    command=qdrant_commands[0],
                    commands=qdrant_commands,
                    status="optional" if active_vector_store == "qdrant" else "needed",
                    reason=(
                        "Start existing Qdrant container, or create it if it does "
                        "not exist."
                    ),
                    category="qdrant",
                )
            )

        selections_complete = selected_llm is not None and selected_embedding is not None
        runtime_matches = llm_matches and embedding_matches and vector_store_matches
        steps.append(
            LocalAIActivationStep(
                id="restart_backend",
                title="Restart backend with selected local AI runtime",
                description=(
                    "Start the backend using the selected model providers, models, "
                    "and vector store."
                ),
                command=(
                    self._backend_restart_command(
                        selected_llm,
                        selected_embedding,
                        selected_vector_store,
                    )
                    if selections_complete
                    else None
                ),
                status=(
                    "blocked"
                    if not selections_complete
                    else "done" if runtime_matches else "needed"
                ),
                reason=(
                    "Select both an LLM and embedding model first."
                    if not selections_complete
                    else (
                        "Active runtime matches the selected local AI configuration."
                        if runtime_matches
                        else "Restart is required to activate the selected configuration."
                    )
                ),
                category="backend",
            )
        )

        reindex_needed = selected_embedding is not None and (
            not embedding_matches
            or not vector_store_matches
            or index_status != "indexed"
        )
        steps.append(
            LocalAIActivationStep(
                id="reindex_workspace",
                title="Reindex workspace context",
                description="Build workspace vectors using the active selected embedding.",
                command=(
                    f"curl -X POST http://127.0.0.1:8000/workspaces/"
                    f"{workspace_id}/index"
                    if selected_embedding is not None
                    else None
                ),
                status=(
                    "blocked"
                    if selected_embedding is None
                    else "needed" if reindex_needed else "done"
                ),
                reason=(
                    "Select an embedding model first."
                    if selected_embedding is None
                    else (
                        "Workspace must be reindexed with the selected embedding space."
                        if reindex_needed
                        else "Workspace index is ready for the selected embedding."
                    )
                ),
                category="indexing",
            )
        )
        steps.append(self._ask_selected_step(workspace_id, selected_llm))
        return steps

    @staticmethod
    def _selection_step(
        model_type: str,
        selected: WorkspaceSelectedModel | None,
    ) -> LocalAIActivationStep:
        label = "LLM" if model_type == "llm" else "embedding model"
        return LocalAIActivationStep(
            id=f"select_{model_type}",
            title=f"Select workspace {label}",
            description=f"Choose the workspace {label} to activate.",
            command=None,
            status="done" if selected is not None else "blocked",
            reason=(
                f"Selected {label}: {selected.provider}/{selected.model}."
                if selected is not None
                else f"No workspace {label} is selected."
            ),
            category="selection",
        )

    @staticmethod
    def _pull_model_step(model_type: str, model: str) -> LocalAIActivationStep:
        label = "LLM" if model_type == "llm" else "embedding model"
        return LocalAIActivationStep(
            id=f"pull_ollama_{model_type}_model",
            title=f"Pull selected Ollama {label}",
            description=f"Install the selected local Ollama {label}.",
            command=f"ollama pull {model}",
            status="optional",
            reason="Installed Ollama models are not verified by this guide.",
            category="ollama",
        )

    @staticmethod
    def _ask_selected_step(
        workspace_id: str,
        selected_llm: WorkspaceSelectedModel | None,
    ) -> LocalAIActivationStep:
        supported = (
            selected_llm is not None
            and selected_llm.provider.lower() in {"fake", "ollama"}
        )
        return LocalAIActivationStep(
            id="ask_with_selected_llm",
            title="Ask using selected LLM",
            description="Ask a workspace question using the persisted selected LLM.",
            command=(
                "curl -X POST "
                f"http://127.0.0.1:8000/workspaces/{workspace_id}/ask-selected "
                "-H 'Content-Type: application/json' "
                "-d '{\"question\":\"What should I review first?\",\"limit\":5}'"
                if supported
                else None
            ),
            status="optional" if supported else "blocked",
            reason=(
                "The selected LLM can be used through a per-request override."
                if supported
                else "Select a supported fake or Ollama LLM first."
            ),
            category="rag",
        )

    def _backend_restart_command(
        self,
        selected_llm: WorkspaceSelectedModel | None,
        selected_embedding: WorkspaceSelectedModel | None,
        selected_vector_store: str | None,
    ) -> str:
        if (
            selected_llm is None
            or selected_embedding is None
            or selected_vector_store is None
        ):
            return ""
        environment = [
            f"VECTOR_STORE={selected_vector_store}",
            f"EMBEDDING_PROVIDER={selected_embedding.provider.lower()}",
            f"LLM_PROVIDER={selected_llm.provider.lower()}",
        ]
        if selected_embedding.provider.lower() == "ollama":
            environment.append(f"OLLAMA_EMBEDDING_MODEL={selected_embedding.model}")
        if selected_llm.provider.lower() == "ollama":
            environment.append(f"OLLAMA_LLM_MODEL={selected_llm.model}")
        if selected_vector_store == "qdrant":
            environment.append(
                f"QDRANT_URL={self.configuration.get('QDRANT_URL', 'http://localhost:6333')}"
            )
        if self._uses_ollama(selected_llm, selected_embedding):
            environment.append(
                "OLLAMA_BASE_URL="
                f"{self.configuration.get('OLLAMA_BASE_URL', 'http://localhost:11434')}"
            )
        return f"{' '.join(environment)} uvicorn app.main:app --reload"

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

    def _selected_vector_store(
        self,
        selected_embedding: WorkspaceSelectedModel | None,
    ) -> str | None:
        if selected_embedding is None:
            return None
        if selected_embedding.provider.lower() == "ollama":
            return "qdrant"
        return self.configuration.get("VECTOR_STORE", "").lower()

    @staticmethod
    def _matches(
        selected: WorkspaceSelectedModel | None,
        active_provider: str,
        active_model: str,
    ) -> bool:
        return bool(
            selected is not None
            and selected.provider.lower() == active_provider.lower()
            and selected.model.lower() == active_model.lower()
        )

    @staticmethod
    def _uses_ollama(
        selected_llm: WorkspaceSelectedModel | None,
        selected_embedding: WorkspaceSelectedModel | None,
    ) -> bool:
        return any(
            selected is not None and selected.provider.lower() == "ollama"
            for selected in (selected_llm, selected_embedding)
        )

    @staticmethod
    def _identity(selected: WorkspaceSelectedModel | None) -> str | None:
        return (
            f"{selected.provider}/{selected.model}"
            if selected is not None
            else None
        )
