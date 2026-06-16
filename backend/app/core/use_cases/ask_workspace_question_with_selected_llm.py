from collections.abc import Iterator
from dataclasses import dataclass

from app.core.domain.attached_documents import AttachedDocument
from app.core.domain.rag import RagQualityWarning, WorkspaceQuestionAnswer
from app.core.domain.rag_prompt import SkillPromptInstruction
from app.core.domain.workspace_model_selection import WorkspaceSelectedModel
from app.core.ports.llm_provider_factory import LLMProviderFactoryPort
from app.core.ports.workspace_model_selection_repository import (
    WorkspaceModelSelectionRepositoryPort,
)
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.ask_workspace_question import (
    AskStreamEvent,
    AskWorkspaceQuestionInput,
    AskWorkspaceQuestionNotFoundError,
    AskWorkspaceQuestionUseCase,
    AskWorkspaceQuestionValidationError,
)

SELECTED_EMBEDDING_MISMATCH_MESSAGE = (
    "Answer used active embedding/index configuration, not the selected embedding model."
)


@dataclass(frozen=True)
class AskWorkspaceQuestionWithSelectedLLMInput:
    workspace_id: str
    question: str
    limit: int = 5
    skill_instructions: list[SkillPromptInstruction] | None = None
    skill_profile_source: str = "default"
    skill_profile_name: str = "workspace"
    skill_profile_updated_at: str | None = None
    conversation_id: str | None = None
    images: list[str] | None = None
    temperature: float | None = None
    think: bool | None = None
    attached_documents: list[AttachedDocument] | None = None


class AskWorkspaceQuestionWithSelectedLLMNotFoundError(ValueError):
    pass


class AskWorkspaceQuestionWithSelectedLLMValidationError(ValueError):
    pass


class AskWorkspaceQuestionWithSelectedLLMUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        selection_repository: WorkspaceModelSelectionRepositoryPort,
        llm_provider_factory: LLMProviderFactoryPort,
        ask_workspace_question: AskWorkspaceQuestionUseCase,
        configuration: dict[str, str],
    ) -> None:
        self.workspace_repository = workspace_repository
        self.selection_repository = selection_repository
        self.llm_provider_factory = llm_provider_factory
        self.ask_workspace_question = ask_workspace_question
        self.configuration = dict(configuration)

    def execute(
        self,
        request: AskWorkspaceQuestionWithSelectedLLMInput,
    ) -> WorkspaceQuestionAnswer:
        ask_input = self._build_ask_input(request)
        try:
            return self.ask_workspace_question.execute(ask_input)
        except AskWorkspaceQuestionNotFoundError as exc:
            raise AskWorkspaceQuestionWithSelectedLLMNotFoundError(str(exc)) from exc
        except AskWorkspaceQuestionValidationError as exc:
            raise AskWorkspaceQuestionWithSelectedLLMValidationError(str(exc)) from exc

    def execute_stream(
        self,
        request: AskWorkspaceQuestionWithSelectedLLMInput,
    ) -> Iterator[AskStreamEvent]:
        ask_input = self._build_ask_input(request)
        try:
            yield from self.ask_workspace_question.execute_stream(ask_input)
        except AskWorkspaceQuestionNotFoundError as exc:
            raise AskWorkspaceQuestionWithSelectedLLMNotFoundError(str(exc)) from exc
        except AskWorkspaceQuestionValidationError as exc:
            raise AskWorkspaceQuestionWithSelectedLLMValidationError(str(exc)) from exc

    def _build_ask_input(
        self,
        request: AskWorkspaceQuestionWithSelectedLLMInput,
    ) -> AskWorkspaceQuestionInput:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise AskWorkspaceQuestionWithSelectedLLMNotFoundError("Workspace not found")

        selection = self.selection_repository.get(request.workspace_id)
        selected_llm = selection.selected_llm if selection is not None else None
        if selected_llm is None:
            raise AskWorkspaceQuestionWithSelectedLLMValidationError(
                "No selected LLM is configured for this workspace."
            )
        if not self.llm_provider_factory.supports(selected_llm.provider):
            raise AskWorkspaceQuestionWithSelectedLLMValidationError(
                f"Unsupported selected LLM provider: {selected_llm.provider}"
            )

        additional_warnings: list[RagQualityWarning] = []
        selected_embedding = selection.selected_embedding if selection is not None else None
        if selected_embedding is not None and not self._embedding_matches_active(
            selected_embedding
        ):
            additional_warnings.append(
                RagQualityWarning(
                    code="selected_embedding_not_active",
                    message=SELECTED_EMBEDDING_MISMATCH_MESSAGE,
                    severity="low",
                    evidence=[
                        f"selected={selected_embedding.provider}/{selected_embedding.model}",
                        (
                            "active="
                            f"{self._active_embedding_provider()}/"
                            f"{self._active_embedding_model()}"
                        ),
                    ],
                )
            )

        if selected_llm.provider == "fake":
            additional_warnings.append(
                RagQualityWarning(
                    code="fake_test_model_selected",
                    message=(
                        "This workspace is using the built-in test model, which only "
                        "returns placeholder text — not real answers. Open Models and "
                        "choose (and install) a local AI to get real responses."
                    ),
                    severity="high",
                    evidence=[f"selected={selected_llm.provider}/{selected_llm.model}"],
                )
            )

        return AskWorkspaceQuestionInput(
            workspace_id=request.workspace_id,
            question=request.question,
            limit=request.limit,
            llm_provider_override=selected_llm.provider,
            llm_model_override=selected_llm.model,
            additional_quality_warnings=additional_warnings,
            timeline_metadata={"asked_with_selected_llm": "true"},
            skill_instructions=request.skill_instructions or [],
            skill_profile_source=request.skill_profile_source,
            skill_profile_name=request.skill_profile_name,
            skill_profile_updated_at=request.skill_profile_updated_at,
            conversation_id=request.conversation_id,
            images=request.images or [],
            temperature=request.temperature,
            think=request.think,
            attached_documents=request.attached_documents or [],
        )

    def _embedding_matches_active(self, selected: WorkspaceSelectedModel) -> bool:
        return (
            selected.provider.lower() == self._active_embedding_provider().lower()
            and selected.model.lower() == self._active_embedding_model().lower()
        )

    def _active_embedding_provider(self) -> str:
        return self.configuration.get("EMBEDDING_PROVIDER", "").lower()

    def _active_embedding_model(self) -> str:
        provider = self._active_embedding_provider()
        if provider == "ollama":
            return self.configuration.get("OLLAMA_EMBEDDING_MODEL", "")
        if provider == "fake":
            return "fake-embedding"
        return ""
