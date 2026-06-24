import os
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import datetime
from time import perf_counter

from app.core.domain.attached_documents import (
    AttachedDocument,
    build_attached_documents_section,
)
from app.core.domain.context_budget import chunk_char_budget, fit_context_results
from app.core.domain.conversation_budget import (
    SUMMARY_TRIGGER_MIN_OLDER_TURNS,
    build_summary_prompt,
    history_token_budget,
    split_history_by_budget,
)
from app.core.domain.indexing import ContextSearchResult
from app.core.domain.llm_usage import LLMUsageMetrics, build_llm_usage_metrics
from app.core.domain.mmr import EMBEDDING_KEY, mmr_select
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
from app.core.domain.rag_query_rewrite import (
    build_query_rewrite_prompt,
    merge_queries,
    parse_rewritten_query,
)
from app.core.ports.conversation_repository import ConversationRepositoryPort
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.llm_provider import LLMProviderPort
from app.core.ports.llm_provider_factory import (
    LLMProviderFactoryError,
    LLMProviderFactoryPort,
)
from app.core.ports.reranker import RerankerPort
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

# How many chunks to aim for in a grounded answer (the window budget trims if
# they don't fit), and how wide a candidate pool to draw them from for MMR.
_ANSWER_CHUNK_TARGET = 8
_MMR_POOL = 24

# Optional LLM query rewrite before retrieval (one extra model call per ask).
# Off by default to keep time-to-first-token low; opt in via this env var, the
# same "available but not forced" stance as the reranker.
QUERY_REWRITE_ENV_VAR = "AI_WORKSPACE_ASK_QUERY_REWRITE"


def _strip_embeddings(results: list[ContextSearchResult]) -> list[ContextSearchResult]:
    """Drop the internal per-chunk embedding the store attached for MMR, so it
    never travels further than retrieval."""
    cleaned: list[ContextSearchResult] = []
    for result in results:
        metadata = result.metadata
        if metadata and EMBEDDING_KEY in metadata:
            cleaned.append(
                replace(
                    result,
                    metadata={k: v for k, v in metadata.items() if k != EMBEDDING_KEY},
                )
            )
        else:
            cleaned.append(result)
    return cleaned


def _usage_kwargs(llm_provider: LLMProviderPort) -> dict[str, object | None]:
    """Pull real per-request usage from the provider (token counts + context
    window) when it exposes them, so the UI shows exact numbers instead of a
    character-based estimate. Providers that don't expose these yield None."""
    prompt_tokens = getattr(llm_provider, "last_prompt_tokens", None)
    completion_tokens = getattr(llm_provider, "last_completion_tokens", None)
    has_real = prompt_tokens is not None and completion_tokens is not None
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated": not has_real,
        "context_window": getattr(llm_provider, "context_window", None),
    }


def _empty_context_warning(index_status: str) -> RagQualityWarning:
    """A non-blocking note: the question was answered without project context
    because none was retrievable. When the index says 'indexed' but the store is
    empty, the index very likely needs rebuilding (e.g. after a backend restart
    or a vector-store/embedding change)."""
    if index_status == "indexed":
        message = (
            "Answered without project context: the search index reports 'indexed' "
            "but the vector store returned no chunks — rebuild the search context "
            "(scan, then build) to search your files again."
        )
    else:
        message = (
            "Answered without project context: nothing relevant was found for this "
            "question in the project. Build/rebuild the search context to enable "
            "project-grounded answers."
        )
    return RagQualityWarning(
        code="answered_without_project_context",
        message=message,
        severity="review",
        evidence=[],
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
        reranker: RerankerPort | None = None,
        rerank_candidates: int = 30,
        conversation_repository: ConversationRepositoryPort | None = None,
        max_history_turns: int = 6,
        project_context_provider=None,
        enable_query_rewrite: bool | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.llm_provider_factory = llm_provider_factory
        self.index_status_repository = index_status_repository
        self.timeline_repository = timeline_repository
        # Optional conversation memory: when set, recent turns of the same
        # conversation are fed into the prompt so follow-ups ("disable it") keep
        # their context. None = stateless, exactly as before.
        self.conversation_repository = conversation_repository
        self.max_history_turns = max_history_turns
        # Optional cross-encoder precision pass. None (or a disabled reranker)
        # means Ask behaves exactly as before — plain hybrid retrieval.
        self.reranker: RerankerPort | None = reranker
        self.rerank_candidates = rerank_candidates
        # Optional shared project-context provider (handbook + memory + graph
        # facts): (workspace_id, query) -> str. None = unchanged behaviour.
        self.project_context_provider = project_context_provider
        # Optional LLM query rewrite before retrieval. None reads the env toggle
        # (default off), so it can ship available-but-not-forced like the reranker.
        if enable_query_rewrite is None:
            enable_query_rewrite = os.environ.get(QUERY_REWRITE_ENV_VAR, "").strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
        self.enable_query_rewrite = enable_query_rewrite

    def _project_memory_section(self, workspace_id: str, query: str) -> str:
        section, _, _ = self._project_context(workspace_id, query)
        return section

    def _project_context(self, workspace_id: str, query: str) -> tuple[str, int, int]:
        """Return (context_text, memory_items_used, graph_facts_used)."""
        provider = self.project_context_provider
        if provider is None:
            return "", 0, 0
        try:
            if hasattr(provider, "compose_with_stats"):
                text, stats = provider.compose_with_stats(workspace_id, query)
                return text or "", stats.memory_items, stats.graph_facts
            return provider(workspace_id, query) or "", 0, 0
        except Exception:  # noqa: BLE001 - context is best-effort, never fatal
            return "", 0, 0

    def _grounded_prompt(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
        context_results: list[ContextSearchResult],
        history: list[tuple[str, str]],
    ) -> tuple[list[ContextSearchResult], str, int, int]:
        """Build the grounded prompt, fitting the retrieved chunks to the model's
        real context window so memory + history + chunks + answer headroom never
        overflow it (the engine would otherwise silently truncate).

        ``history`` is the prompt history (recent turns + any summary) already
        computed by the caller, so it is budgeted for and not recomputed.

        Returns the (possibly trimmed) chunks actually used, the prompt, and the
        memory/facts counts — so sources and ``used_context_chunks`` reflect what
        the model really saw.
        """
        # Memory selection uses the same history-expanded query as retrieval, so a
        # bare follow-up ("disable it") still matches relevant memory.
        memory_section, memory_used, facts_used = self._project_context(
            request.workspace_id, self._retrieval_query(request)
        )
        budget = chunk_char_budget(
            getattr(llm_provider, "context_window", None),
            memory_text=memory_section,
            history=history,
        )
        fitted = fit_context_results(context_results, budget)
        prompt = build_workspace_question_prompt(
            question=request.question,
            context_results=fitted,
            skill_instructions=request.skill_instructions,
            attached_section=build_attached_documents_section(
                request.question, request.attached_documents
            ),
            assistant_identity=f"{llm_provider.provider_name}/{llm_provider.model_name}",
            project_memory_section=memory_section,
        )
        return fitted, prompt, memory_used, facts_used

    def _all_turns(self, request: AskWorkspaceQuestionInput) -> list[tuple[str, str]]:
        """Every (role, content) user/assistant turn of this conversation.

        Best-effort: missing repo/conversation, or any error, yields no history so
        answering never depends on it.
        """
        if self.conversation_repository is None or not request.conversation_id:
            return []
        try:
            conversation = self.conversation_repository.get_conversation(
                request.workspace_id, request.conversation_id
            )
        except Exception:  # noqa: BLE001 - history is optional, never fail the ask
            return []
        if conversation is None:
            return []
        return [
            (message.role, message.content)
            for message in conversation.messages
            if message.role in ("user", "assistant") and message.content.strip()
        ]

    def _conversation_history(self, request: AskWorkspaceQuestionInput) -> list[tuple[str, str]]:
        """Recent turns that fit a token budget (used to steer retrieval). Token-
        budgeted rather than a fixed turn count, so long turns don't overflow and
        short ones don't waste room."""
        turns = self._all_turns(request)
        _older, recent = split_history_by_budget(turns, history_token_budget(None))
        return recent

    def _history_for_prompt(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
    ) -> list[tuple[str, str]]:
        """The history actually sent to the model: recent turns that fit the
        window's history budget, with the older evicted turns folded into one
        short summary so the thread isn't lost after a few exchanges.

        Summarization is best-effort and only runs when enough older turns were
        evicted; any failure falls back to just the recent turns.
        """
        turns = self._all_turns(request)
        if not turns:
            return []
        budget = history_token_budget(getattr(llm_provider, "context_window", None))
        older, recent = split_history_by_budget(turns, budget)
        if len(older) < SUMMARY_TRIGGER_MIN_OLDER_TURNS:
            return recent
        summary = self._summarize_history(older, llm_provider)
        if not summary:
            return recent
        preface = (
            f"[Summary of the earlier conversation — context only, not a new question]\n{summary}"
        )
        return [("user", preface), *recent]

    def _summarize_history(
        self,
        older_turns: list[tuple[str, str]],
        llm_provider: LLMProviderPort,
    ) -> str:
        """Compress the evicted older turns into a few sentences via the local
        model. Best-effort: returns "" on any failure so history degrades to just
        the recent turns (the previous behaviour)."""
        try:
            text = llm_provider.generate(build_summary_prompt(older_turns), None, 0.0, False, None)
        except Exception:  # noqa: BLE001 - summary is optional, never fail the ask
            return ""
        return " ".join((text or "").split())[:800]

    def _retrieval_query(self, request: AskWorkspaceQuestionInput) -> str:
        """The text used for RAG retrieval, expanded with recent context.

        A follow-up like "how do I disable it?" has no searchable subject on its
        own, so retrieval would miss the files the conversation is actually about.
        We prepend the last couple of user questions (which carry the real terms,
        e.g. "ecs", "<project name>", "dev") so dense + keyword search lands on the right
        files. The question shown to the model is unchanged — this only steers
        retrieval. With no history it is exactly the current question.
        """
        history = self._conversation_history(request)
        prior_user_questions = [
            content for role, content in history if role == "user" and content.strip()
        ][-2:]
        if not prior_user_questions:
            return request.question
        return "\n".join([*prior_user_questions, request.question])

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

        context_results = self._search_context(request, llm_provider)
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
            # No project context available (empty/stale index, or nothing
            # relevant). Still answer the question normally — a greeting or a
            # general question shouldn't fail — and attach a note that project
            # search wasn't used (with a rebuild hint when the index is stale).
            return self._record_question_event(
                self._answer_general_conversation(
                    request,
                    llm_provider,
                    extra_warnings=[_empty_context_warning(index_status.status)],
                ),
                request,
            )

        best_score = max((result.score for result in context_results), default=0.0)
        if best_score < self._relevance_threshold():
            return self._record_question_event(
                self._answer_general_conversation(request, llm_provider),
                request,
            )

        prompt_history = self._history_for_prompt(request, llm_provider)
        context_results, prompt, memory_used, facts_used = self._grounded_prompt(
            request, llm_provider, context_results, prompt_history
        )
        # Rebuild sources from the chunks that actually fit the window.
        sources = [
            RagSource(
                chunk_id=result.chunk_id,
                source_path=result.source_path,
                score=result.score,
                preview=result.content[:200],
            )
            for result in context_results
        ]
        try:
            answer, usage = self._generate_answer_with_usage(
                llm_provider,
                prompt,
                request.images,
                request.temperature,
                request.think,
                prompt_history,
            )
        except RuntimeError as exc:
            return self._record_question_event(
                self._diagnostic_answer(
                    request=request,
                    llm_provider=llm_provider,
                    answer=(
                        "The selected local model could not answer right now. "
                        "Check that the local model engine is running and that this "
                        "model is installed, or choose another ready model in Models."
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
                project_memory_used=memory_used,
                project_facts_used=facts_used,
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

        context_results = self._search_context(request, llm_provider)
        sources = [
            RagSource(
                chunk_id=result.chunk_id,
                source_path=result.source_path,
                score=result.score,
                preview=result.content[:200],
            )
            for result in context_results
        ]

        # No project context (empty/stale index, or nothing relevant): fall
        # through to a normal general-chat answer with a non-blocking note, so a
        # greeting or general question still gets answered instead of a hard error.
        empty_context_warnings = (
            [_empty_context_warning(index_status.status)] if not context_results else []
        )

        best_score = max((result.score for result in context_results), default=0.0)
        if not context_results or best_score < self._relevance_threshold():
            prompt = build_general_chat_prompt(
                question=request.question,
                skill_instructions=request.skill_instructions,
                current_time=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
                attached_section=build_attached_documents_section(
                    request.question, request.attached_documents
                ),
                assistant_identity=f"{llm_provider.provider_name}/{llm_provider.model_name}",
            )
            answer_text, usage, failed = yield from self._stream_generation(
                llm_provider, prompt, request, self._conversation_history(request)
            )
            if failed:
                yield AskStreamFinal(
                    self._record_question_event(
                        self._diagnostic_answer(
                            request=request,
                            llm_provider=llm_provider,
                            answer=(
                                "The selected local model could not answer right now. "
                                "Check that the local model engine is running and that "
                                "this model is installed, or choose another ready model "
                                "in Models."
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
                        quality_warnings=[
                            *empty_context_warnings,
                            *request.additional_quality_warnings,
                        ],
                        usage=usage,
                        skill_profile=self._skill_profile_audit(request),
                        conversation_id=request.conversation_id,
                    ),
                    request,
                )
            )
            return

        prompt_history = self._history_for_prompt(request, llm_provider)
        context_results, prompt, memory_used, facts_used = self._grounded_prompt(
            request, llm_provider, context_results, prompt_history
        )
        # Rebuild sources from the chunks that actually fit the window.
        sources = [
            RagSource(
                chunk_id=result.chunk_id,
                source_path=result.source_path,
                score=result.score,
                preview=result.content[:200],
            )
            for result in context_results
        ]
        answer_text, usage, failed = yield from self._stream_generation(
            llm_provider, prompt, request, prompt_history
        )
        if failed:
            yield AskStreamFinal(
                self._record_question_event(
                    self._diagnostic_answer(
                        request=request,
                        llm_provider=llm_provider,
                        answer=(
                            "The selected local model could not answer right now. "
                            "Check that the local model engine is running and that "
                            "this model is installed, or choose another ready model "
                            "in Models."
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
                    project_memory_used=memory_used,
                    project_facts_used=facts_used,
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
        history: list[tuple[str, str]] | None = None,
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
                    history,
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
                    history,
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
            **_usage_kwargs(llm_provider),
        )
        return answer_text, usage, None

    def _generate_answer_with_usage(
        self,
        llm_provider: LLMProviderPort,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
        history: list[tuple[str, str]] | None = None,
    ) -> tuple[str, LLMUsageMetrics]:
        started_at = perf_counter()
        answer = llm_provider.generate(prompt, images or None, temperature, think, history)
        latency_ms = max(0, round((perf_counter() - started_at) * 1000))
        usage = build_llm_usage_metrics(
            prompt=prompt,
            completion=answer,
            latency_ms=latency_ms,
            provider=llm_provider.provider_name,
            model=llm_provider.model_name,
            **_usage_kwargs(llm_provider),
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
        extra_warnings: list[RagQualityWarning] | None = None,
    ) -> WorkspaceQuestionAnswer:
        prompt = build_general_chat_prompt(
            question=request.question,
            skill_instructions=request.skill_instructions,
            current_time=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
            attached_section=build_attached_documents_section(
                request.question, request.attached_documents
            ),
            assistant_identity=f"{llm_provider.provider_name}/{llm_provider.model_name}",
        )
        try:
            answer, usage = self._generate_answer_with_usage(
                llm_provider,
                prompt,
                request.images,
                request.temperature,
                request.think,
                self._conversation_history(request),
            )
        except RuntimeError as exc:
            return self._diagnostic_answer(
                request=request,
                llm_provider=llm_provider,
                answer=(
                    "The selected local model could not answer right now. "
                    "Check that the local model engine is running and that this "
                    "model is installed, or choose another ready model in Models."
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
            quality_warnings=[
                *(extra_warnings or []),
                *request.additional_quality_warnings,
            ],
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

    def _rewrite_query(
        self,
        base_query: str,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
    ) -> str:
        """Best-effort LLM rewrite of the retrieval query (opt-in via env).

        Asks the already-loaded answer model to distil the question into search
        terms, then merges the result with the original wording. Any error, empty,
        or degenerate reply falls back to ``base_query``, so retrieval is never
        worse than the no-rewrite path.
        """
        if not self.enable_query_rewrite:
            return base_query
        prior_terms = "\n".join(
            content
            for role, content in self._conversation_history(request)
            if role == "user" and content.strip()
        )
        prompt = build_query_rewrite_prompt(request.question, prior_terms=prior_terms or None)
        try:
            raw = llm_provider.generate(prompt, None, 0.0, False, None)
        except Exception:  # noqa: BLE001 - rewrite is optional, never fail the ask
            return base_query
        rewritten = parse_rewritten_query(raw, request.question)
        return merge_queries(base_query, rewritten)

    def _search_context(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort | None = None,
    ) -> list[ContextSearchResult]:
        if request.limit <= 0 or not request.question.strip():
            return []

        # Expand the follow-up with recent conversation terms so retrieval lands
        # on the files the dialogue is about ("disable it" -> "...ecs...disable it").
        retrieval_query = self._retrieval_query(request)
        if llm_provider is not None:
            retrieval_query = self._rewrite_query(retrieval_query, request, llm_provider)
        query_embedding = self.embedding_provider.embed_text(retrieval_query)
        rerank = self.reranker is not None and self.reranker.enabled

        if rerank:
            # Cross-encoder path: pull a wide set, re-sort, keep request.limit.
            candidates = self.vector_store.search(
                workspace_id=request.workspace_id,
                query_embedding=query_embedding,
                limit=max(request.limit, self.rerank_candidates),
                embedding_provider=self.embedding_provider.provider_name,
                embedding_model=self.embedding_provider.model_name,
                embedding_dimension=len(query_embedding),
                query_text=retrieval_query,
            )
            if len(candidates) <= request.limit:
                return _strip_embeddings(candidates[: request.limit])
            order = self.reranker.rerank(
                retrieval_query, [result.content for result in candidates], request.limit
            )
            reranked = [candidates[i] for i in order if 0 <= i < len(candidates)]
            return _strip_embeddings((reranked or candidates)[: request.limit])

        # Default path (no reranker): fetch a wider pool and pick a relevant-but-
        # diverse subset with MMR, so the budgeted context covers more of the
        # codebase instead of near-duplicate top hits.
        target = max(request.limit, _ANSWER_CHUNK_TARGET)
        pool = max(target * 3, _MMR_POOL)
        candidates = self.vector_store.search(
            workspace_id=request.workspace_id,
            query_embedding=query_embedding,
            limit=pool,
            embedding_provider=self.embedding_provider.provider_name,
            embedding_model=self.embedding_provider.model_name,
            embedding_dimension=len(query_embedding),
            query_text=retrieval_query,
        )
        return _strip_embeddings(mmr_select(query_embedding, candidates, target))

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
