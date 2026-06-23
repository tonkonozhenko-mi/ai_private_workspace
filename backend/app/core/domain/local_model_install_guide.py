from dataclasses import dataclass

from app.core.domain.model_catalog import LocalModelDefinition


@dataclass(frozen=True)
class LocalModelInstallOption:
    provider: str
    model: str
    model_type: str
    display_name: str
    purpose: str
    estimated_size: str | None
    recommended: bool
    install_command: str
    verify_command: str
    notes: list[str]


@dataclass(frozen=True)
class LocalModelInstallGuide:
    title: str
    summary: str
    status: str
    options: list[LocalModelInstallOption]
    safety_notes: list[str]
    next_steps: list[str]


def build_local_model_install_guide(
    catalog_models: list[LocalModelDefinition],
) -> LocalModelInstallGuide:
    # Show the common defaults first, then every other answer/search model in the
    # catalog — so newer embedders (BGE-M3, Qwen3-Embedding) and extra answer
    # models are installable here too, not just the original three.
    preferred = [
        ("llm", "qwen3:4b"),
        ("llm", "qwen2.5-coder"),
        ("llm", "llama3.2"),
        ("embedding", "nomic-embed-text"),
    ]
    selected: list[LocalModelDefinition] = []
    seen: set[tuple[str, str]] = set()

    def _add(item: LocalModelDefinition) -> None:
        key = (item.model_type, item.model_name)
        if key not in seen:
            seen.add(key)
            selected.append(item)

    for model_type, model_name in preferred:
        match = next(
            (
                item
                for item in catalog_models
                if item.model_type == model_type and item.model_name == model_name
            ),
            None,
        )
        if match is not None:
            _add(match)

    for item in catalog_models:
        if item.model_type in {"llm", "embedding"} and item.provider != "fake":
            _add(item)

    if not selected:
        selected = catalog_models[:3]

    options = [
        LocalModelInstallOption(
            provider=model.provider,
            model=model.model_name,
            model_type=model.model_type,
            display_name=model.display_name,
            purpose=_purpose_for(model),
            estimated_size=model.estimated_size,
            recommended=model.model_name in {"qwen3:4b", "qwen2.5-coder", "nomic-embed-text"},
            install_command=f"ollama pull {model.model_name}",
            verify_command="ollama list",
            notes=[
                "Install is explicit and user-approved only.",
                "The current backend only exposes the plan; it does not run model downloads from the UI.",
                *model.notes[:2],
            ],
        )
        for model in selected
    ]

    return LocalModelInstallGuide(
        title="Local model install plan",
        summary=(
            "This is the safe foundation for a future in-app model download manager. "
            "For now it gives clear model choices and copyable Ollama commands without executing them."
        ),
        status="manual_install_required",
        options=options,
        safety_notes=[
            "The frontend must not run shell commands.",
            "Downloading a model must be an explicit user action, never automatic during startup.",
            "Embedding model changes may require rebuilding the local search context.",
        ],
        next_steps=[
            "Choose one AI answer model and one search context model.",
            "Run the copied ollama pull command outside the UI.",
            "Verify installed models with ollama list.",
            "Return to the Models screen and save the preferred model names.",
        ],
    )


def _purpose_for(model: LocalModelDefinition) -> str:
    name = model.model_name.lower()
    if model.model_type == "embedding":
        if "bge-m3" in name:
            return "Multilingual hybrid search — stronger recall across languages and long files."
        if "qwen3-embedding" in name:
            return "Most accurate retrieval — a little heavier; best when answers must be precise."
        return "Light, fast default — builds searchable local context for answers."
    if "coder" in name:
        return "Best default for DevOps, code, CI/CD, Terraform, and infrastructure questions."
    return "General local answer model for lighter workspace questions."
