from app.core.domain.model_catalog import (
    LocalModelDefinition,
    ModelCatalogResult,
    ModelCatalogWarning,
)


class ModelCatalogRegistry:
    def __init__(
        self,
        models: list[LocalModelDefinition] | None = None,
        user_models: list[LocalModelDefinition] | None = None,
        warnings: list[ModelCatalogWarning] | None = None,
    ) -> None:
        self.models = list(DEFAULT_LOCAL_MODELS if models is None else models)
        self.warnings = list(warnings or [])
        known_ids = {model.id for model in self.models}

        for model in user_models or []:
            if model.id in known_ids:
                self.warnings.append(
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
            self.models.append(model)
            known_ids.add(model.id)

    def list_models(self) -> list[LocalModelDefinition]:
        return list(self.models)

    def get_result(self) -> ModelCatalogResult:
        return ModelCatalogResult(
            models=self.list_models(),
            warnings=list(self.warnings),
        )


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
        estimated_size=None,
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
        estimated_size=None,
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
        estimated_size=None,
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
        estimated_size=None,
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
