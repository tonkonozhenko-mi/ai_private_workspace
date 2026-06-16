from threading import RLock

from app.core.domain.model_catalog import (
    LocalModelDefinition,
    ModelCatalogReloadResult,
    ModelCatalogResult,
    ModelCatalogWarning,
)
from app.core.ports.model_catalog_loader import ModelCatalogLoaderPort


class ModelCatalogRegistry:
    def __init__(
        self,
        models: list[LocalModelDefinition] | None = None,
        user_models: list[LocalModelDefinition] | None = None,
        warnings: list[ModelCatalogWarning] | None = None,
        loader: ModelCatalogLoaderPort | None = None,
    ) -> None:
        self.builtin_models = list(DEFAULT_LOCAL_MODELS if models is None else models)
        self.user_models: list[LocalModelDefinition] = []
        self.warnings: list[ModelCatalogWarning] = []
        self.loader = loader
        self._lock = RLock()
        self._replace_user_catalog(
            ModelCatalogResult(
                models=list(user_models or []),
                warnings=list(warnings or []),
            )
        )

    def list_models(self) -> list[LocalModelDefinition]:
        with self._lock:
            return [*self.builtin_models, *self.user_models]

    def get_result(self) -> ModelCatalogResult:
        with self._lock:
            return ModelCatalogResult(
                models=self.list_models(),
                warnings=list(self.warnings),
            )

    def reload(self) -> ModelCatalogReloadResult:
        loaded = (
            self.loader.load()
            if self.loader is not None
            else ModelCatalogResult(models=[], warnings=[])
        )
        with self._lock:
            self._replace_user_catalog(loaded)
            return ModelCatalogReloadResult(
                models_count=len(self.list_models()),
                user_models_count=len(self.user_models),
                warnings_count=len(self.warnings),
                warnings=list(self.warnings),
            )

    def register_user_model(self, model: LocalModelDefinition) -> LocalModelDefinition:
        with self._lock:
            for known in self.list_models():
                if self._same_model(known, model):
                    return known

            self.user_models.append(model)
            self._save_user_models()
            return model

    def upsert_user_model(self, model: LocalModelDefinition) -> LocalModelDefinition:
        """Persist refreshed metadata without allowing built-ins to be overridden."""
        with self._lock:
            for known in self.builtin_models:
                if self._same_model(known, model):
                    return known

            for index, known in enumerate(self.user_models):
                if self._same_model(known, model):
                    self.user_models[index] = model
                    self._save_user_models()
                    return model

            self.user_models.append(model)
            self._save_user_models()
            return model

    def _save_user_models(self) -> None:
        save = getattr(self.loader, "save", None)
        if callable(save):
            save(list(self.user_models))

    @staticmethod
    def _same_model(
        first: LocalModelDefinition,
        second: LocalModelDefinition,
    ) -> bool:
        return (
            first.provider.lower() == second.provider.lower()
            and first.model_name.lower() == second.model_name.lower()
            and first.model_type == second.model_type
        )

    def _replace_user_catalog(self, catalog: ModelCatalogResult) -> None:
        with self._lock:
            user_models: list[LocalModelDefinition] = []
            warnings = list(catalog.warnings)
            known_ids = {model.id for model in self.builtin_models}

            for model in catalog.models:
                if model.id in known_ids:
                    warnings.append(
                        ModelCatalogWarning(
                            code="duplicate_model_id",
                            message=(
                                f"User model '{model.id}' was skipped because its ID "
                                "already exists in the catalog."
                            ),
                            source=model.id,
                        )
                    )
                    continue
                user_models.append(model)
                known_ids.add(model.id)

            self.user_models = user_models
            self.warnings = warnings


ALL_ASSISTANT_PROFILES = [
    "devops",
    "developer",
    "documentation",
    "support_incident",
    "manager_summary",
]


DEFAULT_LOCAL_MODELS = [
    LocalModelDefinition(
        id="ollama-llama3.2",
        provider="ollama",
        model_name="llama3.2",
        model_type="llm",
        display_name="Llama 3.2",
        description="General-purpose local language model for concise assistant tasks.",
        capabilities=["workspace_ask", "summarization", "documentation"],
        recommended_for_profiles=["devops", "documentation", "manager_summary"],
        recommended_laptop_profiles=["balanced", "powerful"],
        estimated_size="2.0 GB",
        context_window=None,
        embedding_dimension=None,
        quality_tier="good",
        speed_tier="medium",
        local_only=True,
        notes=[
            "General local assistant model.",
            "Exact size and context window depend on the installed Ollama variant.",
        ],
    ),
    LocalModelDefinition(
        id="ollama-qwen2.5-coder",
        provider="ollama",
        model_name="qwen2.5-coder",
        model_type="llm",
        display_name="Qwen 2.5 Coder",
        description="Code-oriented local language model for project and DevOps tasks.",
        capabilities=["workspace_ask", "code_analysis", "devops_analysis"],
        recommended_for_profiles=["devops", "developer"],
        recommended_laptop_profiles=["balanced", "powerful"],
        estimated_size="4.7 GB",
        context_window=None,
        embedding_dimension=None,
        quality_tier="strong",
        speed_tier="medium",
        local_only=True,
        notes=[
            "Better fit for code-oriented tasks.",
            "Exact size and context window depend on the installed Ollama variant.",
        ],
    ),
    LocalModelDefinition(
        id="ollama-mistral",
        provider="ollama",
        model_name="mistral",
        model_type="llm",
        display_name="Mistral",
        description="General local language model suited to text-oriented responses.",
        capabilities=["workspace_ask", "summarization", "documentation"],
        recommended_for_profiles=["documentation", "manager_summary"],
        recommended_laptop_profiles=["balanced", "powerful"],
        estimated_size="4.1 GB",
        context_window=None,
        embedding_dimension=None,
        quality_tier="good",
        speed_tier="medium",
        local_only=True,
        notes=[
            "Useful for text summarization and documentation-style answers.",
            "Exact size and context window depend on the installed Ollama variant.",
        ],
    ),
    LocalModelDefinition(
        id="fake-llm",
        provider="fake",
        model_name="fake-llm",
        model_type="llm",
        display_name="Fake LLM",
        description="Deterministic fake language model for development and tests.",
        capabilities=["workspace_ask", "testing"],
        recommended_for_profiles=ALL_ASSISTANT_PROFILES,
        recommended_laptop_profiles=["low_power"],
        estimated_size=None,
        context_window=None,
        embedding_dimension=None,
        quality_tier="basic",
        speed_tier="fast",
        local_only=True,
        notes=["Testing and development only; it does not generate real answers."],
    ),
    LocalModelDefinition(
        id="ollama-nomic-embed-text",
        provider="ollama",
        model_name="nomic-embed-text",
        model_type="embedding",
        display_name="Nomic Embed Text",
        description="Local text embedding model for workspace indexing and retrieval.",
        capabilities=["workspace_indexing", "context_search", "rag_retrieval"],
        recommended_for_profiles=ALL_ASSISTANT_PROFILES,
        recommended_laptop_profiles=["balanced", "powerful"],
        estimated_size="0.3 GB",
        context_window=None,
        embedding_dimension=768,
        quality_tier="good",
        speed_tier="fast",
        local_only=True,
        notes=[
            "Embedding dimension reflects the current catalog assumption and should "
            "be verified against the installed runtime."
        ],
    ),
    LocalModelDefinition(
        id="fake-embedding",
        provider="fake",
        model_name="fake-embedding",
        model_type="embedding",
        display_name="Fake Embedding",
        description="Deterministic fake embedding provider for development and tests.",
        capabilities=["workspace_indexing", "context_search", "testing"],
        recommended_for_profiles=ALL_ASSISTANT_PROFILES,
        recommended_laptop_profiles=["low_power"],
        estimated_size=None,
        context_window=None,
        embedding_dimension=128,
        quality_tier="basic",
        speed_tier="fast",
        local_only=True,
        notes=["Testing and development only; vectors are not semantically meaningful."],
    ),
]


def build_custom_ollama_model_definition(
    model_name: str,
    model_type: str,
    *,
    display_name: str | None = None,
    capabilities: list[str] | None = None,
    estimated_size: str | None = None,
    context_window: int | None = None,
    embedding_dimension: int | None = None,
    notes: list[str] | None = None,
) -> LocalModelDefinition:
    normalized_name = model_name.strip()
    normalized_type = model_type.strip().lower()
    if normalized_type not in {"llm", "embedding"}:
        raise ValueError(f"Unknown model type: {model_type}")
    if not normalized_name or any(character.isspace() for character in normalized_name):
        raise ValueError("Ollama model name must be a non-empty tag without spaces")

    safe_id = "".join(
        character.lower() if character.isalnum() else "-" for character in normalized_name
    ).strip("-")
    default_capabilities = (
        ["workspace_ask", "custom_ollama_model"]
        if normalized_type == "llm"
        else [
            "workspace_indexing",
            "context_search",
            "rag_retrieval",
            "custom_ollama_model",
        ]
    )
    return LocalModelDefinition(
        id=f"user-ollama-{normalized_type}-{safe_id}",
        provider="ollama",
        model_name=normalized_name,
        model_type=normalized_type,
        display_name=display_name or normalized_name,
        description=(
            "User-selected local Ollama answer model."
            if normalized_type == "llm"
            else "User-selected local Ollama embedding model."
        ),
        capabilities=capabilities or default_capabilities,
        recommended_for_profiles=ALL_ASSISTANT_PROFILES,
        recommended_laptop_profiles=["low_power", "balanced", "powerful"],
        estimated_size=estimated_size,
        context_window=context_window,
        embedding_dimension=embedding_dimension,
        quality_tier="experimental",
        speed_tier="medium",
        local_only=True,
        notes=notes
        or [
            "Added from a custom Ollama model tag.",
            "Runtime metadata is refreshed from the local Ollama installation.",
        ],
    )
