import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter

from app.core.domain.attached_documents import (
    AttachedDocument,
    build_attached_documents_section,
)
from app.core.domain.indexing import ContextSearchResult
from app.core.domain.llm_usage import LLMUsageMetrics, build_llm_usage_metrics
from app.core.domain.rag import (
    RagQualityWarning,
    RagSource,
    SkillProfileAudit,
    WorkspaceQuestionAnswer,
)
from app.core.domain.rag_answer_evaluator import evaluate_rag_answer
from app.core.domain.rag_prompt import (
    SkillPromptInstruction,
    build_general_chat_prompt,
    build_workspace_question_prompt,
)
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.llm_provider import LLMProviderPort
from app.core.ports.llm_provider_factory import (
    LLMProviderFactoryError,
    LLMProviderFactoryPort,
)
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)

WORKSPACE_NOT_INDEXED_ANSWER = (
    "This workspace has not been indexed yet. Run workspace indexing first."
)
WORKSPACE_NOT_INDEXED_MESSAGE = "No workspace index metadata was found."
INDEX_METADATA_WITHOUT_CHUNKS_ANSWER = "No context chunks were found in the active vector store."
INDEX_METADATA_WITHOUT_CHUNKS_MESSAGE = (
    "Index metadata exists, but the active vector store returned no chunks. "
    "If VECTOR_STORE=memory, reindex after API restart. If VECTOR_STORE=qdrant, "
    "verify VECTOR_STORE, EMBEDDING_PROVIDER, model, and collection settings."
)
NO_RELEVANT_CONTEXT_ANSWER = (
    "I answer using this project's files, and I didn't find anything relevant to "
    "that question here. Try asking about the project's code, configuration, "
    "documentation, or setup. (General questions that aren't about the project — "
    "like which AI model is running — aren't answered from project files; the "
    "current model is shown above each answer.)"
)
NO_RELEVANT_CONTEXT_MESSAGE = (
    "The active vector store returned no context chunks for this question."
)

# When the best retrieved chunk is below this cosine-similarity score, the
# question is treated as general conversation (e.g. "what time is it", "how are
# you") and answered directly by the model instead of being grounded in
# unrelated project files. Score scales differ by embedding model, so the
# default depends on the provider and can be overridden via environment.
RELEVANCE_THRESHOLD_ENV_VAR = "AI_WORKSPACE_ASK_RELEVANCE_THRESHOLD"
DEFAULT_RELEVANCE_THRESHOLD = 0.38
FAKE_EMBEDDING_RELEVANCE_THRESHOLD = 0.2
GENERAL_CHAT_DIAGNOSTIC_CODE = "answered_as_general_conversation"
GENERAL_CHAT_DIAGNOSTIC_MESSAGE = (
    "No project files were relevant to this question, so it was answered as "
    "general conversation instead of from project context."
)


@dataclass(frozen=True)
class AskWorkspaceQuestionInput:
    workspace_id: str
    question: str
    limit: int = 5
    llm_provider_override: str | None = None
    llm_model_override: str | None = None
    additional_quality_warnings: list[RagQualityWarning] = field(default_factory=list)
    timeline_metadata: dict[str, str] = field(default_factory=dict)
    skill_instructions: list[SkillPromptInstruction] = field(default_factory=list)
    skill_profile_source: str = "default"
    skill_profile_name: str = "workspace"
    skill_profile_updated_at: str | None = None
    conversation_id: str | None = None
    images: list[str] = field(default_factory=list)
    temperature: float | None = None
    think: bool | None = None
    attached_documents: list[AttachedDocument] = field(default_factory=list)


@dataclass(frozen=True)
class AskStreamDelta:
    """A chunk of answer text produced while streaming."""

    text: str


@dataclass(frozen=True)
class AskStreamFinal:
    """The completed answer, emitted once after all deltas."""

    answer: WorkspaceQuestionAnswer


AskStreamEvent = AskStreamDelta | AskStreamFinal


class AskWorkspaceQuestionNotFoundError(ValueError):
    pass


class AskWorkspaceQuestionValidationError(ValueError):
    pass


class AskWorkspaceQuestionUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        embedding_provider: EmbeddingProviderPort,
        vector_store: VectorStorePort,
        llm_provider_factory: LLMProviderFactoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.llm_provider_factory = llm_provider_factory
        self.index_status_repository = index_status_repository
        self.timeline_repository = timeline_repository

    def execute(
        self,
        request: AskWorkspaceQuestionInput,
    ) -> WorkspaceQuestionAnswer:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise AskWorkspaceQuestionNotFoundError("Workspace not found")

        llm_provider = self._create_llm_provider(request)
        index_status = self.index_status_repository.get(request.workspace_id)
        if index_status is None or index_status.status == "not_indexed":
            return self._record_question_event(
                self._diagnostic_answer(
                    request=request,
                    llm_provider=llm_provider,
                    answer=WORKSPACE_NOT_INDEXED_ANSWER,
                    diagnostic_code="workspace_not_indexed",
                    diagnostic_message=WORKSPACE_NOT_INDEXED_MESSAGE,
                ),
                request,
            )

        context_results = self._search_context(request)
        sources = [
            RagSource(
                chunk_id=result.chunk_id,
                source_path=result.source_path,
                score=result.score,
                preview=result.content[:200],
            )
            for result in context_results
        ]

        if not context_results:
            if index_status.status == "indexed":
                return self._record_question_event(
                    self._diagnostic_answer(
                        request=request,
                        llm_provider=llm_provider,
                        answer=INDEX_METADATA_WITHOUT_CHUNKS_ANSWER,
                        diagnostic_code="index_metadata_exists_but_no_chunks_found",
                        diagnostic_message=INDEX_METADATA_WITHOUT_CHUNKS_MESSAGE,
                    ),
                    request,
                )
            return self._record_question_event(
                self._diagnostic_answer(
                    request=request,
                    llm_provider=llm_provider,
                    answer=NO_RELEVANT_CONTEXT_ANSWER,
                    diagnostic_code="no_relevant_context_found",
                    diagnostic_message=NO_RELEVANT_CONTEXT_MESSAGE,
                ),
                request,
            )

        best_score = max((result.score for result in context_results), default=0.0)
        if best_score < self._relevance_threshold():
            return self._record_question_event(
                self._answer_general_conversation(request, llm_provider),
                request,
            )

        prompt = build_workspace_question_prompt(
            question=request.question,
            context_results=context_results,
            skill_instructions=request.skill_instructions,
            attached_section=build_attached_documents_section(
                request.question, request.attached_documents
            ),
        )
        try:
            answer, usage = self._generate_answer_with_usage(
                llm_provider, prompt, request.images, request.temperature, request.think
            )
        except RuntimeError as exc:
            return self._record_question_event(
                self._diagnostic_answer(
                    request=request,
                    llm_provider=llm_provider,
                    answer=(
                        "The selected local model could not answer right now. "
                        "Check that Ollama is running and that this model is installed, "
                        "or choose another ready model in Models."
                    ),
                    diagnostic_code="selected_llm_runtime_unavailable",
                    diagnostic_message=str(exc),
                ),
                request,
            )
        quality_warnings = [
            *evaluate_rag_answer(
                question=request.question,
                answer=answer,
                sources=sources,
                source_contents=[result.content for result in context_results],
            ),
            *request.additional_quality_warnings,
        ]

        return self._record_question_event(
            WorkspaceQuestionAnswer(
                workspace_id=request.workspace_id,
                question=request.question,
                answer=answer,
                sources=sources,
                used_context_chunks=len(context_results),
                llm_provider=llm_provider.provider_name,
                llm_model=llm_provider.model_name,
                diagnostic_code=None,
                diagnostic_message=None,
                quality_warnings=quality_warnings,
                usage=usage,
                skill_profile=self._skill_profile_audit(request),
                conversation_id=request.conversation_id,
            ),
            request,
        )

    def execute_stream(
        self,
        request: AskWorkspaceQuestionInput,
    ) -> Iterator[AskStreamEvent]:
        """Same flow as ``execute`` but yields answer deltas as they arrive.

        Diagnostic / canned short-circuits (not indexed, no context) emit no
        deltas — only a single final event. The model-backed paths (workspace
        answer and general conversation) stream token deltas first, then a final
        event carrying the persisted answer, sources, usage and warnings.
        """
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise AskWorkspaceQuestionNotFoundError("Workspace not found")

        llm_provider = self._create_llm_provider(request)
        index_status = self.index_status_repository.get(request.workspace_id)
        if index_status is None or index_status.status == "not_indexed":
            yield AskStreamFinal(
                self._record_question_event(
                    self._diagnostic_answer(
                        request=request,
                        llm_provider=llm_provider,
                        answer=WORKSPACE_NOT_INDEXED_ANSWER,
                        diagnostic_code="workspace_not_indexed",
                        diagnostic_message=WORKSPACE_NOT_INDEXED_MESSAGE,
                    ),
                    request,
                )
            )
            return

        context_results = self._search_context(request)
        sources = [
            RagSource(
                chunk_id=result.chunk_id,
                source_path=result.source_path,
                score=result.score,
                preview=result.content[:200],
            )
            for result in context_results
        ]

        if not context_results:
            if index_status.status == "indexed":
                yield AskStreamFinal(
                    self._record_question_event(
                        self._diagnostic_answer(
                            request=request,
                            llm_provider=llm_provider,
                            answer=INDEX_METADATA_WITHOUT_CHUNKS_ANSWER,
                            diagnostic_code="index_metadata_exists_but_no_chunks_found",
                            diagnostic_message=INDEX_METADATA_WITHOUT_CHUNKS_MESSAGE,
                        ),
                        request,
                    )
                )
                return
            yield AskStreamFinal(
                self._record_question_event(
                    self._diagnostic_answer(
                        request=request,
                        llm_provider=llm_provider,
                        answer=NO_RELEVANT_CONTEXT_ANSWER,
                        diagnostic_code="no_relevant_context_found",
                        diagnostic_message=NO_RELEVANT_CONTEXT_MESSAGE,
                    ),
                    request,
                )
            )
            return

        best_score = max((result.score for result in context_results), default=0.0)
        if best_score < self._relevance_threshold():
            prompt = build_general_chat_prompt(
                question=request.question,
                skill_instructions=request.skill_instructions,
                current_time=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
                attached_section=build_attached_documents_section(
                    request.question, request.attached_documents
                ),
            )
            answer_text, usage, failed = yield from self._stream_generation(
                llm_provider, prompt, request
            )
            if failed:
                yield AskStreamFinal(
                    self._record_question_event(
                        self._diagnostic_answer(
                            request=request,
                            llm_provider=llm_provider,
                            answer=(
                                "The selected local model could not answer right now. "
                                "Check that Ollama is running and that this model is "
                                "installed, or choose another ready model in Models."
                            ),
                            diagnostic_code="selected_llm_runtime_unavailable",
                            diagnostic_message=failed,
                        ),
                        request,
                    )
                )
                return
            yield AskStreamFinal(
                self._record_question_event(
                    WorkspaceQuestionAnswer(
                        workspace_id=request.workspace_id,
                        question=request.question,
                        answer=answer_text,
                        sources=[],
                        used_context_chunks=0,
                        llm_provider=llm_provider.provider_name,
                        llm_model=llm_provider.model_name,
                        diagnostic_code=GENERAL_CHAT_DIAGNOSTIC_CODE,
                        diagnostic_message=GENERAL_CHAT_DIAGNOSTIC_MESSAGE,
                        quality_warnings=list(request.additional_quality_warnings),
                        usage=usage,
                        skill_profile=self._skill_profile_audit(request),
                        conversation_id=request.conversation_id,
                    ),
                    request,
                )
            )
            return

        prompt = build_workspace_question_prompt(
            question=request.question,
            context_results=context_results,
            skill_instructions=request.skill_instructions,
            attached_section=build_attached_documents_section(
                request.question, request.attached_documents
            ),
        )
        answer_text, usage, failed = yield from self._stream_generation(
            llm_provider, prompt, request
        )
        if failed:
            yield AskStreamFinal(
                self._record_question_event(
                    self._diagnostic_answer(
                        request=request,
                        llm_provider=llm_provider,
                        answer=(
                            "The selected local model could not answer right now. "
                            "Check that Ollama is running and that this model is "
                            "installed, or choose another ready model in Models."
                        ),
                        diagnostic_code="selected_llm_runtime_unavailable",
                        diagnostic_message=failed,
                    ),
                    request,
                )
            )
            return

        quality_warnings = [
            *evaluate_rag_answer(
                question=request.question,
                answer=answer_text,
                sources=sources,
                source_contents=[result.content for result in context_results],
            ),
            *request.additional_quality_warnings,
        ]
        yield AskStreamFinal(
            self._record_question_event(
                WorkspaceQuestionAnswer(
                    workspace_id=request.workspace_id,
                    question=request.question,
                    answer=answer_text,
                    sources=sources,
                    used_context_chunks=len(context_results),
                    llm_provider=llm_provider.provider_name,
                    llm_model=llm_provider.model_name,
                    diagnostic_code=None,
                    diagnostic_message=None,
                    quality_warnings=quality_warnings,
                    usage=usage,
                    skill_profile=self._skill_profile_audit(request),
                    conversation_id=request.conversation_id,
                ),
                request,
            )
        )

    def _stream_generation(
        self,
        llm_provider: LLMProviderPort,
        prompt: str,
        request: AskWorkspaceQuestionInput,
    ) -> Iterator[AskStreamEvent]:
        """Yield ``AskStreamDelta`` chunks and return ``(answer, usage, error)``.

        ``error`` is ``None`` on success or a message string if the model failed.
        Uses the provider's ``generate_stream`` when available, otherwise falls
        back to a single-shot ``generate`` call yielded as one delta.
        """
        started_at = perf_counter()
        chunks: list[str] = []
        stream = getattr(llm_provider, "generate_stream", None)
        try:
            if callable(stream):
                for delta in stream(
                    prompt,
                    request.images or None,
                    request.temperature,
                    request.think,
                ):
                    if not delta:
                        continue
                    chunks.append(delta)
                    yield AskStreamDelta(delta)
            else:
                answer = llm_provider.generate(
                    prompt,
                    request.images or None,
                    request.temperature,
                    request.think,
                )
                chunks.append(answer)
                yield AskStreamDelta(answer)
        except RuntimeError as exc:
            return "", None, str(exc) or "Model runtime error"

        answer_text = "".join(chunks)
        latency_ms = max(0, round((perf_counter() - started_at) * 1000))
        usage = build_llm_usage_metrics(
            prompt=prompt,
            completion=answer_text,
            latency_ms=latency_ms,
            provider=llm_provider.provider_name,
            model=llm_provider.model_name,
            estimated=True,
        )
        return answer_text, usage, None

    def _generate_answer_with_usage(
        self,
        llm_provider: LLMProviderPort,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
    ) -> tuple[str, LLMUsageMetrics]:
        started_at = perf_counter()
        answer = llm_provider.generate(prompt, images or None, temperature, think)
        latency_ms = max(0, round((perf_counter() - started_at) * 1000))
        usage = build_llm_usage_metrics(
            prompt=prompt,
            completion=answer,
            latency_ms=latency_ms,
            provider=llm_provider.provider_name,
            model=llm_provider.model_name,
            estimated=True,
        )
        return answer, usage

    def _relevance_threshold(self) -> float:
        override = os.environ.get(RELEVANCE_THRESHOLD_ENV_VAR)
        if override:
            try:
                return float(override)
            except ValueError:
                pass
        if getattr(self.embedding_provider, "provider_name", "") == "fake":
            return FAKE_EMBEDDING_RELEVANCE_THRESHOLD
        return DEFAULT_RELEVANCE_THRESHOLD

    def _answer_general_conversation(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
    ) -> WorkspaceQuestionAnswer:
        prompt = build_general_chat_prompt(
            question=request.question,
            skill_instructions=request.skill_instructions,
            current_time=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
            attached_section=build_attached_documents_section(
                request.question, request.attached_documents
            ),
        )
        try:
            answer, usage = self._generate_answer_with_usage(
                llm_provider, prompt, request.images, request.temperature, request.think
            )
        except RuntimeError as exc:
            return self._diagnostic_answer(
                request=request,
                llm_provider=llm_provider,
                answer=(
                    "The selected local model could not answer right now. "
                    "Check that Ollama is running and that this model is installed, "
                    "or choose another ready model in Models."
                ),
                diagnostic_code="selected_llm_runtime_unavailable",
                diagnostic_message=str(exc),
            )

        return WorkspaceQuestionAnswer(
            workspace_id=request.workspace_id,
            question=request.question,
            answer=answer,
            sources=[],
            used_context_chunks=0,
            llm_provider=llm_provider.provider_name,
            llm_model=llm_provider.model_name,
            diagnostic_code=GENERAL_CHAT_DIAGNOSTIC_CODE,
            diagnostic_message=GENERAL_CHAT_DIAGNOSTIC_MESSAGE,
            quality_warnings=list(request.additional_quality_warnings),
            usage=usage,
            skill_profile=self._skill_profile_audit(request),
            conversation_id=request.conversation_id,
        )

    def _diagnostic_answer(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
        answer: str,
        diagnostic_code: str,
        diagnostic_message: str,
    ) -> WorkspaceQuestionAnswer:
        return WorkspaceQuestionAnswer(
            workspace_id=request.workspace_id,
            question=request.question,
            answer=answer,
            sources=[],
            used_context_chunks=0,
            llm_provider=llm_provider.provider_name,
            llm_model=llm_provider.model_name,
            diagnostic_code=diagnostic_code,
            diagnostic_message=diagnostic_message,
            quality_warnings=list(request.additional_quality_warnings),
            skill_profile=self._skill_profile_audit(request),
            conversation_id=request.conversation_id,
        )

    def _create_llm_provider(
        self,
        request: AskWorkspaceQuestionInput,
    ) -> LLMProviderPort:
        try:
            return self.llm_provider_factory.create(
                provider=request.llm_provider_override,
                model=request.llm_model_override,
            )
        except LLMProviderFactoryError as exc:
            raise AskWorkspaceQuestionValidationError(str(exc)) from exc

    def _search_context(
        self,
        request: AskWorkspaceQuestionInput,
    ) -> list[ContextSearchResult]:
        if request.limit <= 0 or not request.question.strip():
            return []

        query_embedding = self.embedding_provider.embed_text(request.question)
        return self.vector_store.search(
            workspace_id=request.workspace_id,
            query_embedding=query_embedding,
            limit=request.limit,
            embedding_provider=self.embedding_provider.provider_name,
            embedding_model=self.embedding_provider.model_name,
            embedding_dimension=len(query_embedding),
        )

    def _skill_profile_audit(
        self,
        request: AskWorkspaceQuestionInput,
    ) -> SkillProfileAudit:
        return SkillProfileAudit(
            source=request.skill_profile_source,
            profile=request.skill_profile_name,
            active_skills=[instruction.name for instruction in request.skill_instructions],
            guidance_count=len(request.skill_instructions),
            updated_at=request.skill_profile_updated_at,
        )

    def _record_question_event(
        self,
        answer: WorkspaceQuestionAnswer,
        request: AskWorkspaceQuestionInput,
    ) -> WorkspaceQuestionAnswer:
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=answer.workspace_id,
                    event_type="workspace_question_asked",
                    title="Workspace question asked",
                    summary=answer.question,
                    metadata={
                        "used_context_chunks": str(answer.used_context_chunks),
                        "llm_provider": answer.llm_provider,
                        "llm_model": answer.llm_model or "",
                        "quality_warnings_count": str(len(answer.quality_warnings)),
                        "skill_profile_source": request.skill_profile_source,
                        "skill_profile": request.skill_profile_name,
                        "skill_profile_updated_at": request.skill_profile_updated_at or "",
                        "guidance_count": str(len(request.skill_instructions)),
                        "applied_skills_count": str(len(request.skill_instructions)),
                        "applied_skills": ", ".join(
                            instruction.name for instruction in request.skill_instructions
                        ),
                        **request.timeline_metadata,
                    },
                )
            )
        return answer
