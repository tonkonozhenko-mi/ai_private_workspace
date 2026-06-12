from dataclasses import dataclass


@dataclass(frozen=True)
class LocalAIActivationStep:
    id: str
    title: str
    description: str
    command: str | None
    status: str
    reason: str
    category: str
    commands: list[str] | None = None


@dataclass(frozen=True)
class LocalAIActivationGuide:
    workspace_id: str
    overall_status: str
    selected_llm: str | None
    selected_embedding: str | None
    active_llm: str
    active_embedding: str
    selected_vector_store: str | None
    active_vector_store: str
    steps: list[LocalAIActivationStep]
    notes: list[str]
