from dataclasses import dataclass

from app.core.domain.guided_model_setup import (
    GuidedModelSetupGuide,
    GuidedModelSetupSection,
    to_guided_model_option,
)
from app.core.domain.model_catalog import LocalModelDefinition
from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class GetGuidedModelSetupInput:
    workspace_id: str


class GuidedModelSetupNotFoundError(ValueError):
    pass


class GetGuidedModelSetupUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        model_catalog_registry: ModelCatalogRegistry,
        total_ram_gb: float | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.model_catalog_registry = model_catalog_registry
        self.total_ram_gb = total_ram_gb

    def execute(self, request: GetGuidedModelSetupInput) -> GuidedModelSetupGuide:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise GuidedModelSetupNotFoundError("Workspace not found")

        models = self.model_catalog_registry.list_models()
        llm_models = [model for model in models if model.model_type == "llm"]
        embedding_models = [model for model in models if model.model_type == "embedding"]

        return GuidedModelSetupGuide(
            workspace_id=workspace.id,
            title="Guided local model setup",
            summary=(
                "Choose one local AI answer model and one local search context model. "
                "These are saved as workspace preferences only."
            ),
            llm=GuidedModelSetupSection(
                model_type="llm",
                title="AI answer model",
                purpose=(
                    "Used when you ask questions, generate reports, summarize code, "
                    "or draft documentation from retrieved workspace context."
                ),
                recommendation_summary=(
                    "Recommended modern default: qwen3:4b — a compact, current model that is "
                    "strong at code and reasoning. qwen2.5-coder is a solid code-focused "
                    "alternative; llama3.2 is a lighter, older fallback."
                ),
                custom_model_hint=(
                    "Custom Ollama names are allowed, for example qwen3:4b, qwen2.5-coder:7b or "
                    "llama3.1:8b. The app saves the model locally and can prepare or run a narrowly "
                    "validated Ollama download when the trusted desktop worker is enabled."
                ),
                options=self._rank_options(
                    llm_models,
                    preferred_ids=[
                        "ollama-qwen3-4b",
                        "ollama-qwen2.5-coder",
                        "ollama-llama3.2",
                    ],
                ),
            ),
            embedding=GuidedModelSetupSection(
                model_type="embedding",
                title="Search context model",
                purpose=(
                    "Used during indexing to convert project chunks into vectors, then used again "
                    "to find relevant local context for RAG answers."
                ),
                recommendation_summary=(
                    "Recommended default: nomic-embed-text for local workspace indexing. "
                    "Changing this later normally requires rebuilding the search context."
                ),
                custom_model_hint=(
                    "Custom embedding model names are allowed, but the backend and vector dimensions "
                    "must match before rebuilding the index."
                ),
                options=self._rank_options(
                    embedding_models,
                    preferred_ids=["ollama-nomic-embed-text"],
                ),
            ),
            packaging_notes=[
                "The same guide can be shown during first launch after desktop packaging.",
                "Defaults are local-first and can be preselected without running shell commands.",
                "Custom Ollama tags are saved to the local user catalog and refreshed from installed-model metadata.",
            ],
            safety_notes=[
                "Saving a choice alone does not install a model, rebuild context, or restart the backend. The separate model download runs only after the user explicitly chooses it in a trusted desktop runtime.",
                "The frontend only records explicit user choices through backend APIs.",
                "Embedding changes are preference-only until the user explicitly rebuilds the local index.",
            ],
        )

    def _rank_options(
        self,
        models: list[LocalModelDefinition],
        *,
        preferred_ids: list[str],
    ):
        # Hide internal fake/testing providers from the user-facing picker. They
        # remain available as deterministic defaults for tests and for booting the
        # app before a real local model is installed, but a person choosing an AI
        # should only ever see real, usable models.
        models = [model for model in models if model.provider != "fake"]
        preferred = {model_id: index for index, model_id in enumerate(preferred_ids)}
        ranked = sorted(
            models,
            key=lambda model: (
                0 if model.id in preferred else 1,
                preferred.get(model.id, 999),
                model.provider,
                model.display_name,
            ),
        )
        return [
            to_guided_model_option(
                model,
                recommendation_label=self._recommendation_label(model, preferred),
                recommended=model.id in preferred,
                total_ram_gb=self.total_ram_gb,
            )
            for model in ranked
        ]

    def _recommendation_label(
        self,
        model: LocalModelDefinition,
        preferred: dict[str, int],
    ) -> str:
        if model.id in preferred:
            return "Recommended default" if preferred[model.id] == 0 else "Good fallback"
        if model.provider == "fake":
            return "Testing only"
        return "Available option"
