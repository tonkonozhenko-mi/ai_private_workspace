from dataclasses import dataclass

PREFERENCE_ONLY_NOTE = (
    "Workspace model selection is preference metadata only and does not change "
    "active runtime settings."
)
EMPTY_SELECTION_NOTE = "No workspace model selections have been saved."
UNKNOWN_CATALOG_NOTE = "Selected model is not in catalog; validate metadata before use."
EMBEDDING_CHANGE_NOTE = (
    "Changing embedding model selection may require reindexing before RAG/search "
    "uses the new embedding space."
)


@dataclass(frozen=True)
class WorkspaceSelectedModel:
    provider: str
    model: str
    model_type: str
    selected_at: str
    selected_reason: str | None


@dataclass(frozen=True)
class WorkspaceModelSelection:
    workspace_id: str
    selected_llm: WorkspaceSelectedModel | None
    selected_embedding: WorkspaceSelectedModel | None
    notes: list[str]


def runtime_match_notes(
    selection: WorkspaceModelSelection,
    configuration: dict[str, str],
) -> list[str]:
    notes: list[str] = []
    if selection.selected_llm is not None:
        notes.append(
            _runtime_match_note(
                selection.selected_llm,
                configured_provider=configuration.get("LLM_PROVIDER", ""),
                configured_ollama_model=configuration.get("OLLAMA_LLM_MODEL", ""),
                fake_model="fake-llm",
                label="LLM",
            )
        )
    if selection.selected_embedding is not None:
        notes.append(
            _runtime_match_note(
                selection.selected_embedding,
                configured_provider=configuration.get("EMBEDDING_PROVIDER", ""),
                configured_ollama_model=configuration.get(
                    "OLLAMA_EMBEDDING_MODEL",
                    "",
                ),
                fake_model="fake-embedding",
                label="embedding model",
            )
        )
    return notes


def with_runtime_match_notes(
    selection: WorkspaceModelSelection,
    configuration: dict[str, str],
) -> WorkspaceModelSelection:
    notes = list(selection.notes)
    if configuration:
        notes.extend(runtime_match_notes(selection, configuration))
    return WorkspaceModelSelection(
        workspace_id=selection.workspace_id,
        selected_llm=selection.selected_llm,
        selected_embedding=selection.selected_embedding,
        notes=list(dict.fromkeys(notes)),
    )


def _runtime_match_note(
    selected: WorkspaceSelectedModel,
    *,
    configured_provider: str,
    configured_ollama_model: str,
    fake_model: str,
    label: str,
) -> str:
    provider = configured_provider.lower()
    provider_matches = selected.provider.lower() == provider
    if provider == "ollama":
        model_matches = selected.model.lower() == configured_ollama_model.lower()
    elif provider == "fake":
        model_matches = selected.model.lower() == fake_model
    else:
        model_matches = False

    if provider_matches and model_matches:
        return f"Selected {label} matches active runtime configuration."
    return f"Selected {label} does not match active runtime configuration."
