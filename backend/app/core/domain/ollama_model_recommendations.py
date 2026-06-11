from dataclasses import dataclass

from app.core.domain.model_catalog import LocalModelDefinition


@dataclass(frozen=True)
class OllamaHardwareProfile:
    id: str
    title: str
    summary: str
    recommended_llm: str
    fallback_llm: str
    recommended_embedding: str
    notes: list[str]


@dataclass(frozen=True)
class OllamaModelRole:
    id: str
    title: str
    model_type: str
    default_model: str
    purpose: str
    why_it_matters: str


@dataclass(frozen=True)
class OllamaModelRecommendationGuide:
    title: str
    summary: str
    default_profile_id: str
    roles: list[OllamaModelRole]
    profiles: list[OllamaHardwareProfile]
    catalog_models: list[LocalModelDefinition]
    safety_notes: list[str]
    next_steps: list[str]


def build_ollama_model_recommendation_guide(
    catalog_models: list[LocalModelDefinition],
) -> OllamaModelRecommendationGuide:
    ollama_models = [model for model in catalog_models if model.provider == "ollama"]
    known_models = {model.model_name for model in ollama_models}

    def pick(preferred: str, fallback: str) -> str:
        if preferred in known_models:
            return preferred
        if fallback in known_models:
            return fallback
        return preferred

    answer_model = pick("qwen2.5-coder", "llama3.2")
    fallback_model = pick("llama3.2", answer_model)
    embedding_model = pick("nomic-embed-text", "nomic-embed-text")

    return OllamaModelRecommendationGuide(
        title="Ollama model recommendations",
        summary=(
            "Use one local model for answers and one local embedding model for search. "
            "Start small, verify the model is installed, then switch to a stronger model only "
            "when your Mac handles it comfortably."
        ),
        default_profile_id="balanced_mac",
        roles=[
            OllamaModelRole(
                id="answer_model",
                title="AI answer model",
                model_type="llm",
                default_model=answer_model,
                purpose="Generates answers, summaries, reports, and agent plans.",
                why_it_matters=(
                    "This model controls answer quality and speed. Code-oriented models are "
                    "usually better for DevOps repositories."
                ),
            ),
            OllamaModelRole(
                id="search_model",
                title="Search context model",
                model_type="embedding",
                default_model=embedding_model,
                purpose="Converts project chunks into vectors for local RAG search.",
                why_it_matters=(
                    "Changing this model usually requires rebuilding the local search context "
                    "so stored vectors stay compatible."
                ),
            ),
        ],
        profiles=[
            OllamaHardwareProfile(
                id="starter_mac",
                title="Starter Mac / low memory",
                summary="Prioritize fast startup, low memory use, and predictable demos.",
                recommended_llm=fallback_model,
                fallback_llm=fallback_model,
                recommended_embedding=embedding_model,
                notes=[
                    "Good first choice when you are not sure how much memory is available.",
                    "Use this profile for demos where responsiveness matters more than maximum quality.",
                ],
            ),
            OllamaHardwareProfile(
                id="balanced_mac",
                title="Balanced Mac / daily DevOps work",
                summary="Best default for code, CI/CD, Terraform, Kubernetes, and documentation.",
                recommended_llm=answer_model,
                fallback_llm=fallback_model,
                recommended_embedding=embedding_model,
                notes=[
                    "Recommended default for AI Private Workspace v0.1.",
                    "If responses are slow, switch the answer model back to the fallback model.",
                ],
            ),
            OllamaHardwareProfile(
                id="power_user",
                title="Power user / larger models later",
                summary="Use stronger custom Ollama tags only after the base flow is stable.",
                recommended_llm=answer_model,
                fallback_llm=fallback_model,
                recommended_embedding=embedding_model,
                notes=[
                    "Custom Ollama tags are allowed, but they should be installed and verified first.",
                    "Keep the embedding model stable unless you are ready to rebuild the index.",
                ],
            ),
        ],
        catalog_models=ollama_models,
        safety_notes=[
            "The frontend never runs ollama pull directly.",
            "Downloads are explicit user actions and can be handled manually or by the approved backend job flow.",
            "Model selection does not automatically scan, index, restart, or rebuild anything.",
        ],
        next_steps=[
            "Choose the Balanced Mac profile unless you need a lighter demo setup.",
            "Install missing models manually or through the approved backend download job flow.",
            "Refresh installed models after download.",
            "Save one answer model and one search context model for the workspace.",
        ],
    )
