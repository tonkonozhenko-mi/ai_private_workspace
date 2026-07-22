import os
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import datetime
from time import perf_counter

from app.core.domain.attached_documents import (
    AttachedDocument,
    build_attached_documents_section,
)
from app.core.domain.context_budget import (
    chunk_token_budget,
    fit_context_results_by_tokens,
    project_fits_whole_context,
    shrink_to_window,
)
from app.core.domain.conversation_budget import build_summary_prompt
from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.domain.indexing import ContextSearchResult
from app.core.domain.instruction_split import retrieval_text
from app.core.domain.llm_errors import ContextOverflowError, context_overflow_answer
from app.core.domain.llm_usage import LLMUsageMetrics, build_llm_usage_metrics
from app.core.domain.mmr import EMBEDDING_KEY, mmr_select
from app.core.domain.parent_document import expand_to_parents
from app.core.domain.query_synonyms import expand_query_synonyms
from app.core.domain.question_intent import looks_general_chat, looks_project_specific
from app.core.domain.rag import (
    RagQualityWarning,
    RagSource,
    SkillProfileAudit,
    WorkspaceQuestionAnswer,
)
from app.core.domain.indexing_blind_spots import unread_files, unread_files_prompt_note
from app.core.domain.rag_answer_cleanup import strip_source_path_echo
from app.core.domain.rag_answer_evaluator import evaluate_rag_answer
from app.core.domain.rag_prompt import (
    AnswerMode,
    SkillPromptInstruction,
    answer_mode_tuning,
    build_general_chat_prompt,
    build_workspace_question_prompt,
    source_status_line,
)
from app.core.domain.rag_query_rewrite import (
    build_corrective_query_rewrite_prompt,
    build_query_rewrite_prompt,
    merge_queries,
    parse_rewritten_query,
)
from app.core.domain.rag_structured_answer import (
    STRUCTURED_CITATIONS_ENV_VAR,
    citations_response_format,
    structured_answer_instruction,
    structured_answer_text,
)
from app.core.domain.retrieval_diversity import limit_per_source
from app.core.domain.supersession import follow_supersession
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
from app.core.ports.vector_store import VectorStoreCorruptError, VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)
from app.core.use_cases.conversation_thread import (
    conversation_turns,
    history_for_prompt,
    recent_turns,
    retrieval_query_with_history,
)

WORKSPACE_NOT_INDEXED_ANSWER = (
    "This workspace has not been indexed yet. Run workspace indexing first."
)
WORKSPACE_NOT_INDEXED_MESSAGE = "No workspace index metadata was found."

WORKSPACE_INDEX_CORRUPT_ANSWER = (
    "The project's search index looks damaged, so I can't search your files right "
    "now. Rebuild the index for this workspace (re-index it), then ask again."
)
WORKSPACE_INDEX_CORRUPT_MESSAGE = "The search index is corrupt and must be rebuilt."

# When the best retrieved chunk is below this cosine-similarity score, the
# question is treated as general conversation (e.g. "what time is it", "how are
# you") and answered directly by the model instead of being grounded in
# unrelated project files. Score scales differ by embedding model, so the
# default depends on the provider and can be overridden via environment.
RELEVANCE_THRESHOLD_ENV_VAR = "AI_WORKSPACE_ASK_RELEVANCE_THRESHOLD"
DEFAULT_RELEVANCE_THRESHOLD = 0.38
FAKE_EMBEDDING_RELEVANCE_THRESHOLD = 0.2
# The abstention threshold sits just BELOW the calibrated noise floor: real
# query↔chunk matches score above the model's background, unrelated text sits
# within it. The golden-set showed the noise floor calibrates to ~0.60 while
# chit-chat scores 0.40–0.66, so the old flat 0.38 cap let all of it through —
# floor minus this margin (clamped) separates them. Chit-chat itself is now routed
# out earlier by looks_general_chat(); this threshold is the retrieval safety net.
RELEVANCE_FLOOR_MARGIN = 0.10
RELEVANCE_FLOOR_MIN = 0.15
RELEVANCE_FLOOR_MAX = 0.60
# The chunk↔chunk noise floor is calibrated on a different scale than the
# query↔chunk decision, and the fixed 0.10 margin doesn't transfer between corpora:
# on a small, homogeneous index (e.g. an infra monorepo) the floor sits well above
# where real matches actually score, so the threshold over-abstains. A second anchor
# fixes this: the empirical chit-chat ceiling (highest similarity neutral probe
# queries reach against the corpus), measured on the query↔chunk scale. The
# threshold is capped just above that ceiling. Combined with min(), this can only
# ever LOWER the bar (never raise it above today's floor−margin), so over-blocking
# can fall but chit-chat protection — held by the router upstream and the ceiling
# here — is never weakened.
RELEVANCE_PROBE_MARGIN = 0.03
GENERAL_CHAT_DIAGNOSTIC_CODE = "answered_as_general_conversation"
GENERAL_CHAT_DIAGNOSTIC_MESSAGE = (
    "No project files were relevant to this question, so it was answered as "
    "general conversation instead of from project context."
)

# Attached when a question that *looks* project-specific found no confident
# context — so the user knows the answer is general-knowledge, not grounded.
PROJECT_NOT_FOUND_WARNING = RagQualityWarning(
    code="project_answer_not_grounded",
    message=(
        "No relevant files were found in the indexed project for this question, "
        "so this answer is from the model's general knowledge — not your project. "
        "Try rephrasing, or re-index if the project changed."
    ),
    severity="warning",
    evidence=[],
)

# Grounding warnings strong enough to justify one CRAG-lite corrective pass: the
# answer cited no retrieved file, asserted a project term that isn't in the
# retrieved content, or named a file that exists nowhere in the evidence. Softer
# signals (absence-phrase conflicts, quote mismatches) don't trigger a costly
# regeneration.
#
# ``answer_cited_unknown_source`` joined this set on 2026-07-15: an answer that
# located a project's storage configuration in "main.tf in the Terraform
# directory" — a file, and a directory, that do not exist in that project — was
# flagged and shipped anyway, because a warning nobody acts on is a warning
# nobody reads. Naming a file that is not there is not a nuance; it is the
# hallucination this app exists to refuse.
_HARD_GROUNDING_CODES = frozenset(
    {
        "answer_missing_source_paths",
        "answer_term_not_in_context",
        "answer_cited_unknown_source",
        # A page of true statements about Terraform is not an answer about this
        # project. Worth one more attempt with the sources named again.
        "answer_grounded_in_nothing",
    }
)


def _hard_grounding_warnings(
    warnings: list[RagQualityWarning],
) -> list[RagQualityWarning]:
    return [w for w in warnings if w.code in _HARD_GROUNDING_CODES]


# How many chunks to aim for in a grounded answer (the window budget trims if
# they don't fit), and how wide a candidate pool to draw them from for MMR.
_ANSWER_CHUNK_TARGET = 8
_MMR_POOL = 24

# Optional LLM query rewrite before retrieval (one extra model call per ask).
# Off by default to keep time-to-first-token low; opt in via this env var, the
# same "available but not forced" stance as the reranker.
QUERY_REWRITE_ENV_VAR = "AI_WORKSPACE_ASK_QUERY_REWRITE"


def _best_score(results: list[ContextSearchResult] | None) -> float:
    """The best score in a retrieval, or zero when it returned nothing."""
    return max((result.score for result in results or []), default=0.0)


def _sources_of(results: list[ContextSearchResult]) -> list[RagSource]:
    """The chunks the model was actually given, as the sources the person is shown.

    Built in one place because every path that changes the context — corrective
    retrieval, window fitting, a retry with less context — must change the shown
    sources with it. A source list that outlives the context it describes is a lie.
    """
    return [
        RagSource(
            chunk_id=result.chunk_id,
            source_path=result.source_path,
            score=result.score,
            preview=result.content[:200],
        )
        for result in results
    ]


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
    answer_mode: str | None = None


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
        index_manifest_repository=None,
        project_scan_repository=None,
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
        # Optional LLM query rewrite before retrieval. Precedence: explicit env
        # override wins either way; otherwise it defaults ON when a reranker is
        # active and OFF when not. Rationale (P7a): enabling the reranker already
        # opts the user into the extra latency of a precision pass, and the rewrite
        # is exactly what feeds that pass better candidates — so pairing them is the
        # sensible default, while a plain-retrieval setup stays fast by default.
        if enable_query_rewrite is None:
            env = os.environ.get(QUERY_REWRITE_ENV_VAR, "").strip().lower()
            if env in ("1", "true", "yes", "on"):
                enable_query_rewrite = True
            elif env in ("0", "false", "no", "off"):
                enable_query_rewrite = False
            else:
                enable_query_rewrite = bool(
                    reranker is not None and getattr(reranker, "enabled", False)
                )
        self.enable_query_rewrite = enable_query_rewrite
        # Optional index manifest (source_path -> {hash, chunks}). When present it
        # enumerates every indexed file, enabling small-project full-context mode:
        # if the whole project provably fits the window we skip retrieval and feed
        # all files. None = feature disabled (plain retrieval, as before).
        self.index_manifest_repository = index_manifest_repository
        # Optional latest scan, read only to tell the model which extensions it
        # never saw. None = the sentence is simply absent, which is also what
        # happens when nothing was skipped — an unknown blind spot and no blind
        # spot look the same here on purpose: we only ever claim what we counted.
        self.project_scan_repository = project_scan_repository

    def _unread_files_note(self, workspace_id: str) -> str:
        if self.project_scan_repository is None:
            return ""
        try:
            scan = self.project_scan_repository.get_latest_scan(workspace_id)
        except Exception:
            # A missing or unreadable scan must never cost the person an answer.
            return ""
        if scan is None:
            return ""
        return unread_files_prompt_note(unread_files(scan.files))

    def _project_memory_section(self, workspace_id: str, query: str) -> str:
        section, _, _, _ = self._project_context(workspace_id, query)
        return section

    def _user_style_directive(self) -> str:
        """The person's cross-project style/language preference, for the general-chat
        path that skips retrieval. Best-effort: empty when no profile-aware provider
        is wired or the person has set no style preference."""
        provider = self.project_context_provider
        getter = getattr(provider, "user_style_directive", None)
        if not callable(getter):
            return ""
        try:
            return getter() or ""
        except Exception:  # noqa: BLE001 - a preference must never fail an answer
            return ""

    def _project_context(self, workspace_id: str, query: str) -> tuple[str, int, int, dict]:
        """Return (context_text, memory_items_used, graph_facts_used, used_details).

        ``used_details`` = {"memory": [...], "guardrails": [...], "style_directive": ...}
        for the "Why this answer?" panel and the terminal style directive; empty when
        no stats-aware provider is present."""
        empty: dict = {
            "memory": [],
            "guardrails": [],
            "profile": [],
            "profile_facts": 0,
            "style_directive": "",
        }
        provider = self.project_context_provider
        if provider is None:
            return "", 0, 0, empty
        try:
            if hasattr(provider, "compose_with_stats"):
                text, stats = provider.compose_with_stats(workspace_id, query)
                details = {
                    "memory": list(getattr(stats, "memory_used", []) or []),
                    "guardrails": list(getattr(stats, "guardrails_used", []) or []),
                    "profile": list(getattr(stats, "profile_used", []) or []),
                    "profile_facts": getattr(stats, "profile_facts", 0) or 0,
                    "style_directive": getattr(stats, "style_directive", "") or "",
                }
                return text or "", stats.memory_items, stats.graph_facts, details
            return provider(workspace_id, query) or "", 0, 0, empty
        except Exception:  # noqa: BLE001 - context is best-effort, never fatal
            return "", 0, 0, empty

    def _grounded_prompt(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
        context_results: list[ContextSearchResult],
        history: list[tuple[str, str]],
        budget_scale: float = 1.0,
    ) -> tuple[list[ContextSearchResult], str, int, int]:
        """Build the grounded prompt, fitting the retrieved chunks to the model's
        real context window so memory + history + question + chunks + answer
        headroom never overflow it.

        Three things guard the window, in order: the token budget (what should
        fit), the per-chunk fitting (what does fit), and ``shrink_to_window``,
        which measures the finished prompt and drops trailing chunks until it
        provably fits. The last one exists because every earlier number is an
        estimate — the chat template adds tokens we never see.

        ``history`` is the prompt history (recent turns + any summary) already
        computed by the caller, so it is budgeted for and not recomputed.
        ``budget_scale`` < 1 shrinks the chunk allowance, which is how a retry
        after a context overflow asks for the same answer with less context.

        Returns the (possibly trimmed) chunks actually used, the prompt, and the
        memory/facts counts — so sources and ``used_context_chunks`` reflect what
        the model really saw.
        """
        # Memory selection uses the same history-expanded query as retrieval, so a
        # bare follow-up ("disable it") still matches relevant memory.
        memory_section, memory_used, facts_used, context_used = self._project_context(
            request.workspace_id, self._retrieval_query(request)
        )
        # A retrieved page that says "Superseded by X" is holding an address. Follow
        # it now, before the budget is spent: the replacement is the answer, and the
        # page that names it is only evidence that it was replaced.
        context_results = self._follow_supersession(request.workspace_id, context_results)
        # Use the engine's exact tokenizer when the provider exposes it (llama.cpp
        # /tokenize); otherwise the script-aware estimate, which no longer assumes
        # every language costs 4 characters per token.
        token_counter = getattr(llm_provider, "count_tokens", None)
        window = getattr(llm_provider, "context_window", None)
        assistant_mode = self._assistant_mode(request.workspace_id)
        attached_section = build_attached_documents_section(
            request.question, request.attached_documents
        )
        unread_note = self._unread_files_note(request.workspace_id)

        def build(chunks: list[ContextSearchResult]) -> str:
            return build_workspace_question_prompt(
                question=request.question,
                context_results=chunks,
                skill_instructions=request.skill_instructions,
                attached_section=attached_section,
                assistant_identity=f"{llm_provider.provider_name}/{llm_provider.model_name}",
                project_memory_section=memory_section,
                answer_mode=request.answer_mode,
                user_style_directive=context_used.get("style_directive", ""),
                # The person's role frames the answer — what is said first, in whose
                # words. It is deliberately NOT part of retrieval: the same question
                # returns the same chunks and the same citations for every role.
                assistant_mode=assistant_mode,
                unread_files_note=unread_note,
            )

        budget = chunk_token_budget(
            window,
            memory_text=memory_section,
            history=history,
            # The question and the attached documents are part of the prompt too;
            # forgetting them is how a long question quietly overflowed the window.
            question=request.question,
            extra_text=attached_section,
            token_counter=token_counter,
        )
        fitted = fit_context_results_by_tokens(
            context_results, int(budget * budget_scale), token_counter
        )
        fitted, prompt = shrink_to_window(
            fitted,
            build,
            window,
            token_counter=token_counter,
            history=history,
        )
        return fitted, prompt, memory_used, facts_used, context_used

    def _grounded_generation(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
        context_results: list[ContextSearchResult],
        prompt_history: list[tuple[str, str]],
    ) -> tuple:
        """Build the grounded prompt and generate, surviving one context overflow.

        Returns ``(grounded, answer, usage, overflow)``. ``overflow`` is set only
        when even the smaller retry did not fit — the one case the person hears
        about. Engine failures propagate as ``RuntimeError``, which is a different
        thing entirely and deserves a different sentence.
        """
        grounded = self._grounded_prompt(request, llm_provider, context_results, prompt_history)
        structured_format, prompt = self._structured_citations(request, llm_provider, grounded[1])
        try:
            answer, usage = self._generate_answer_with_usage(
                llm_provider,
                prompt,
                request.images,
                request.temperature,
                request.think,
                prompt_history,
                structured_format,
            )
        except ContextOverflowError as exc:
            # The prompt didn't fit the model's memory. That is our miscount, not a
            # broken engine — so rebuild with proportionally less context and ask
            # once more. Most of the time the person never learns it happened.
            retry = self._retry_with_less_context(
                request, llm_provider, context_results, prompt_history, exc
            )
            if retry is None:
                return grounded, "", None, exc
            *smaller, answer, usage = retry
            return tuple(smaller), answer, usage, None
        return grounded, answer, usage, None

    def _retry_with_less_context(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
        context_results: list[ContextSearchResult],
        prompt_history: list[tuple[str, str]],
        overflow: ContextOverflowError,
    ) -> tuple | None:
        """Rebuild the prompt with a smaller chunk allowance and generate once more.

        The engine told us exactly how far over we were, so the retry is sized to
        that overshoot (plus 10% to spare) rather than being a blind halving.
        Returns ``None`` if the smaller prompt overflows too — at that point the
        person deserves to be told, not retried at forever.
        """
        try:
            fitted, prompt, memory_used, facts_used, context_used = self._grounded_prompt(
                request,
                llm_provider,
                context_results,
                prompt_history,
                budget_scale=overflow.overflow_ratio,
            )
            _structured_format, prompt = self._structured_citations(request, llm_provider, prompt)
            answer, usage = self._generate_answer_with_usage(
                llm_provider,
                prompt,
                request.images,
                request.temperature,
                request.think,
                prompt_history,
                _structured_format,
            )
        except ContextOverflowError:
            return None
        return fitted, prompt, memory_used, facts_used, context_used, answer, usage

    def _assistant_mode(self, workspace_id: str) -> str | None:
        """The workspace's role, or None when it was never chosen — which the prompt
        builder reads as the neutral developer lens."""
        try:
            workspace = self.workspace_repository.get(workspace_id)
        except Exception:  # noqa: BLE001 - a missing role must never fail an answer
            return None
        return getattr(workspace, "assistant_mode", None) if workspace else None

    def _all_turns(self, request: AskWorkspaceQuestionInput) -> list[tuple[str, str]]:
        return conversation_turns(
            self.conversation_repository, request.workspace_id, request.conversation_id
        )

    def _conversation_history(self, request: AskWorkspaceQuestionInput) -> list[tuple[str, str]]:
        """Recent turns that fit a token budget (used to steer retrieval)."""
        return recent_turns(self._all_turns(request))

    def _history_for_prompt(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
    ) -> list[tuple[str, str]]:
        """The history actually sent to the model, budgeted to this model's window
        and summarised past it."""
        return history_for_prompt(
            self._all_turns(request),
            getattr(llm_provider, "context_window", None),
            lambda older: self._summarize_history(older, llm_provider),
        )

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

        Standing instructions are stripped first. A message can be a page of
        rules wrapped around one short request ("write the onboarding docs" plus
        1,800 tokens of NDA and anonymisation policy); searching with all of it
        finds documents about confidentiality rather than about onboarding, and
        spends a quarter of the window doing it. The rules still reach the model
        in full — they are instructions and must be obeyed. They just stop
        pretending to be a search query.
        """
        return retrieval_query_with_history(
            retrieval_text(request.question), self._conversation_history(request)
        )

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

        # Obvious chit-chat (greeting, time, world trivia, "in general") is answered
        # as general conversation without retrieval at all — no chance of attaching
        # unrelated project files, and no wasted embedding on a tiny device.
        if looks_general_chat(request.question):
            return self._record_question_event(
                self._answer_general_conversation(request, llm_provider),
                request,
            )

        try:
            context_results = self._search_context(request, llm_provider)
        except VectorStoreCorruptError:
            return self._record_question_event(
                self._diagnostic_answer(
                    request=request,
                    llm_provider=llm_provider,
                    answer=WORKSPACE_INDEX_CORRUPT_ANSWER,
                    diagnostic_code="index_corrupt",
                    diagnostic_message=WORKSPACE_INDEX_CORRUPT_MESSAGE,
                ),
                request,
            )
        sources = _sources_of(context_results)

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
        threshold = self._relevance_threshold(index_status, request.answer_mode)
        corrected_retrieval = False
        if best_score < threshold:
            # CRAG-lite trigger (a): about to abstain on a project-looking question —
            # try one corrective retrieval (forced query rewrite) before giving up.
            corrected = self._corrective_retrieval(request, llm_provider)
            corrected_best = _best_score(corrected)
            if corrected and corrected_best >= threshold:
                context_results = corrected
                sources = _sources_of(context_results)
                best_score = corrected_best
                corrected_retrieval = True
            else:
                return self._record_question_event(
                    self._answer_general_conversation(
                        request, llm_provider, project_context_missing=True
                    ),
                    request,
                )

        prompt_history = self._history_for_prompt(request, llm_provider)
        try:
            grounded, answer, usage, overflow = self._grounded_generation(
                request, llm_provider, context_results, prompt_history
            )
        except RuntimeError as exc:
            return self._record_question_event(
                self._runtime_unavailable(request, llm_provider, str(exc)), request
            )
        context_results, _prompt, memory_used, facts_used, context_used = grounded
        # Sources reflect the chunks that actually fit the window.
        sources = _sources_of(context_results)
        if overflow is not None:
            return self._record_question_event(
                self._diagnostic_answer(
                    request=request,
                    llm_provider=llm_provider,
                    answer=context_overflow_answer(overflow),
                    diagnostic_code="context_window_exceeded",
                    diagnostic_message=str(overflow),
                ),
                request,
            )
        base_warnings = evaluate_rag_answer(
            question=request.question,
            answer=answer,
            sources=sources,
            source_contents=[result.content for result in context_results],
        )
        # CRAG-lite trigger (b): if the answer has hard grounding warnings and we
        # haven't already corrected retrieval, try one corrective retrieval +
        # regeneration; adopt it only if it strictly improves grounding.
        if not corrected_retrieval:
            regen = self._corrective_regeneration(
                request, llm_provider, prompt_history, base_warnings, best_score
            )
            if regen is not None:
                answer = regen["answer"]
                sources = regen["sources"]
                context_results = regen["context_results"]
                memory_used = regen["memory_used"]
                facts_used = regen["facts_used"]
                context_used = regen["context_used"]
                usage = regen["usage"]
                base_warnings = regen["warnings"]
        quality_warnings = [
            *base_warnings,
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
                project_memory_details=context_used.get("memory", []),
                project_guardrails_used=context_used.get("guardrails", []),
                profile_facts_used=context_used.get("profile_facts", 0),
                profile_details=context_used.get("profile", []),
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

        # Obvious chit-chat: answer as general conversation without retrieval (same
        # early route as execute()), streamed. No project_context_missing note — the
        # user wasn't asking about the project.
        if looks_general_chat(request.question):
            yield from self._stream_general_chat(
                request, llm_provider, project_context_missing=False, warnings=[]
            )
            return

        try:
            context_results = self._search_context(request, llm_provider)
        except VectorStoreCorruptError:
            yield AskStreamFinal(
                self._record_question_event(
                    self._diagnostic_answer(
                        request=request,
                        llm_provider=llm_provider,
                        answer=WORKSPACE_INDEX_CORRUPT_ANSWER,
                        diagnostic_code="index_corrupt",
                        diagnostic_message=WORKSPACE_INDEX_CORRUPT_MESSAGE,
                    ),
                    request,
                )
            )
            return
        sources = _sources_of(context_results)

        # No project context (empty/stale index, or nothing relevant): fall
        # through to a normal general-chat answer with a non-blocking note, so a
        # greeting or general question still gets answered instead of a hard error.
        empty_context_warnings = (
            [_empty_context_warning(index_status.status)] if not context_results else []
        )

        best_score = max((result.score for result in context_results), default=0.0)
        threshold = self._relevance_threshold(index_status, request.answer_mode)
        if context_results and best_score < threshold:
            # CRAG-lite trigger (a): one corrective retrieval before abstaining.
            # (Streaming applies only the pre-generation correction; a post-answer
            # regenerate — trigger (b) — can't rewind tokens already streamed.)
            corrected = self._corrective_retrieval(request, llm_provider)
            corrected_best = _best_score(corrected)
            if corrected and corrected_best >= threshold:
                context_results = corrected
                sources = _sources_of(context_results)
                best_score = corrected_best
        if not context_results or best_score < threshold:
            yield from self._stream_general_chat(
                request,
                llm_provider,
                project_context_missing=True,
                warnings=empty_context_warnings,
            )
            return

        prompt_history = self._history_for_prompt(request, llm_provider)
        grounded, answer_text, usage, failed, overflow = yield from self._stream_grounded_answer(
            request, llm_provider, context_results, prompt_history
        )
        context_results, _prompt, memory_used, facts_used, context_used = grounded
        # Sources reflect the chunks that actually fit the window.
        sources = _sources_of(context_results)
        if overflow is not None:
            yield AskStreamFinal(
                self._record_question_event(
                    self._diagnostic_answer(
                        request=request,
                        llm_provider=llm_provider,
                        answer=context_overflow_answer(overflow),
                        diagnostic_code="context_window_exceeded",
                        diagnostic_message=str(overflow),
                    ),
                    request,
                )
            )
            return
        if failed:
            yield AskStreamFinal(
                self._record_question_event(
                    self._runtime_unavailable(request, llm_provider, failed), request
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
                    project_memory_details=context_used.get("memory", []),
                    project_guardrails_used=context_used.get("guardrails", []),
                    profile_facts_used=context_used.get("profile_facts", 0),
                    profile_details=context_used.get("profile", []),
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

    def _runtime_unavailable(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
        failed: str,
    ) -> WorkspaceQuestionAnswer:
        """The one thing to say when the engine itself could not answer — and the
        only place we say it, so it can never be given for a failure it doesn't
        describe (an over-long prompt, for one, has its own message)."""
        return self._diagnostic_answer(
            request=request,
            llm_provider=llm_provider,
            answer=(
                "The selected local model could not answer right now. "
                "Check that the local model engine is running and that this "
                "model is installed, or choose another ready model in Models."
            ),
            diagnostic_code="selected_llm_runtime_unavailable",
            diagnostic_message=failed,
        )

    def _stream_general_chat(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
        *,
        project_context_missing: bool,
        warnings: list[RagQualityWarning],
    ) -> Iterator[AskStreamEvent]:
        """Stream an ungrounded answer: either the question was chit-chat, or the
        project had nothing relevant to say about it.

        Both cases are the same act — answer from the model's own knowledge, with
        no sources — and differ only in whether the person is told the project was
        searched and came back empty.
        """
        prompt = build_general_chat_prompt(
            question=request.question,
            skill_instructions=request.skill_instructions,
            current_time=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
            attached_section=build_attached_documents_section(
                request.question, request.attached_documents
            ),
            assistant_identity=f"{llm_provider.provider_name}/{llm_provider.model_name}",
            project_context_missing=project_context_missing,
            user_style_directive=self._user_style_directive(),
        )
        answer_text, usage, failed = yield from self._stream_generation(
            llm_provider, prompt, request, self._conversation_history(request)
        )
        if failed:
            yield AskStreamFinal(
                self._record_question_event(
                    self._runtime_unavailable(request, llm_provider, failed), request
                )
            )
            return
        # A project-shaped question answered without project context earns a note:
        # this came from the model's general knowledge, not from your files.
        not_grounded = (
            [PROJECT_NOT_FOUND_WARNING]
            if project_context_missing and looks_project_specific(request.question)
            else []
        )
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
                        *warnings,
                        *not_grounded,
                        *request.additional_quality_warnings,
                    ],
                    usage=usage,
                    skill_profile=self._skill_profile_audit(request),
                    conversation_id=request.conversation_id,
                ),
                request,
            )
        )

    def _stream_grounded_answer(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
        retrieved: list[ContextSearchResult],
        prompt_history: list[tuple[str, str]],
    ) -> Iterator[AskStreamEvent]:
        """Stream the grounded answer, surviving one context overflow.

        The engine rejects an over-long prompt before it streams a single token,
        so a refusal costs the person nothing: we rebuild the prompt with
        proportionally less context (sized to the overshoot the engine reported)
        and stream again. Returns ``(grounded, answer, usage, failed, overflow)``
        — ``overflow`` set only when even the smaller prompt did not fit, which is
        the one case worth telling the person about.
        """
        grounded = self._grounded_prompt(request, llm_provider, retrieved, prompt_history)
        try:
            answer, usage, failed = yield from self._stream_generation(
                llm_provider, grounded[1], request, prompt_history
            )
            return grounded, answer, usage, failed, None
        except ContextOverflowError as first:
            grounded = self._grounded_prompt(
                request,
                llm_provider,
                retrieved,
                prompt_history,
                budget_scale=first.overflow_ratio,
            )
        try:
            answer, usage, failed = yield from self._stream_generation(
                llm_provider, grounded[1], request, prompt_history
            )
        except ContextOverflowError as second:
            return grounded, "", None, None, second
        return grounded, answer, usage, failed, None

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
        except ContextOverflowError:
            # Not a runtime failure to report — a prompt we must rebuild smaller.
            # The engine rejects an over-long prompt before it streams a single
            # token, so nothing has reached the person yet and the caller can
            # safely try again with less context.
            raise
        except RuntimeError as exc:
            return "", None, str(exc) or "Model runtime error"

        answer_text = strip_source_path_echo("".join(chunks))
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

    def _structured_citations(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
        prompt: str,
    ) -> tuple[dict | None, str]:
        """Decide whether to ask for a schema-constrained answer, returning the
        ``response_format`` and a prompt nudged toward the JSON shape (or ``(None,
        prompt)`` unchanged). Experimental, so gated three ways: the opt-in env flag,
        Deep-dive mode only (its wider context is where citation discipline slips
        most, and it's not the fast default path), and only providers that can
        actually constrain output — otherwise the flag is a no-op."""
        if os.environ.get(STRUCTURED_CITATIONS_ENV_VAR, "").strip().lower() not in (
            "1",
            "true",
            "yes",
            "on",
        ):
            return None, prompt
        if AnswerMode.normalize(request.answer_mode) != AnswerMode.DEEP:
            return None, prompt
        if not getattr(llm_provider, "supports_structured_output", False):
            return None, prompt
        return citations_response_format(), prompt + structured_answer_instruction()

    def _generate_answer_with_usage(
        self,
        llm_provider: LLMProviderPort,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
        history: list[tuple[str, str]] | None = None,
        response_format: dict | None = None,
    ) -> tuple[str, LLMUsageMetrics]:
        started_at = perf_counter()
        # Only pass response_format when set, so providers/mocks with the older
        # 5-arg generate() signature keep working (structured output is opt-in).
        if response_format is not None:
            raw = llm_provider.generate(
                prompt, images or None, temperature, think, history, response_format
            )
            # A schema-constrained answer is JSON — unwrap it to the Markdown body,
            # then still strip any stray source_path echo as a belt-and-braces guard.
            raw = structured_answer_text(raw)
        else:
            raw = llm_provider.generate(prompt, images or None, temperature, think, history)
        answer = strip_source_path_echo(raw)
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

    def _relevance_threshold(
        self,
        index_status: WorkspaceIndexStatus | None = None,
        answer_mode: str | None = None,
    ) -> float:
        # Explicit env override always wins (ops/debugging escape hatch).
        override = os.environ.get(RELEVANCE_THRESHOLD_ENV_VAR)
        if override:
            try:
                return float(override)
            except ValueError:
                pass
        if getattr(self.embedding_provider, "provider_name", "") == "fake":
            return FAKE_EMBEDDING_RELEVANCE_THRESHOLD
        # Prefer a floor calibrated to this embedding model's own score scale (set at
        # index time). Sit just below it (floor − margin, clamped): matches beat the
        # background, chit-chat sits within it. Golden-set validated this separates
        # the two where the old flat 0.38 cap could not. Falls back to the hardcoded
        # default for indexes built before calibration existed, or too small to
        # sample a trustworthy floor.
        probe_ceiling = (
            getattr(index_status, "relevance_probe_ceiling", None)
            if index_status is not None
            else None
        )
        if probe_ceiling is not None:
            # The chit-chat ceiling is the honest anchor: it is how high neutral,
            # off-topic questions actually score against *this* corpus. The bar
            # sits just above it — below it, small talk is admitted by
            # construction. It used to be applied through min(), on the assumption
            # that the floor was always the stricter of the two; a corpus where the
            # floor clamped to 0.6 (bar 0.5) while chit-chat reached 0.559 proved
            # that assumption false and let "What is Google's stock price today?"
            # be answered from the project's files. An anchor that can only ever
            # lower the bar is not an anchor.
            base = max(
                RELEVANCE_FLOOR_MIN,
                min(RELEVANCE_FLOOR_MAX, probe_ceiling + RELEVANCE_PROBE_MARGIN),
            )
        elif index_status is not None and index_status.relevance_floor is not None:
            # No ceiling measured (an index built before probes existed, or too
            # small to sample): fall back to the noise floor, sitting just below it
            # — real matches beat the background, unrelated text sits within it.
            base = max(
                RELEVANCE_FLOOR_MIN,
                min(RELEVANCE_FLOOR_MAX, index_status.relevance_floor - RELEVANCE_FLOOR_MARGIN),
            )
        else:
            base = DEFAULT_RELEVANCE_THRESHOLD
        # The answer mode scales strictness: Only-from-sources raises the floor so it
        # declines honestly on weak matches; Deep dive lowers it to consider more.
        scaled = base * answer_mode_tuning(answer_mode).threshold_scale
        return max(0.05, min(0.9, scaled))

    def _answer_general_conversation(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
        extra_warnings: list[RagQualityWarning] | None = None,
        project_context_missing: bool = False,
    ) -> WorkspaceQuestionAnswer:
        prompt = build_general_chat_prompt(
            question=request.question,
            skill_instructions=request.skill_instructions,
            current_time=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
            attached_section=build_attached_documents_section(
                request.question, request.attached_documents
            ),
            assistant_identity=f"{llm_provider.provider_name}/{llm_provider.model_name}",
            project_context_missing=project_context_missing,
            user_style_directive=self._user_style_directive(),
        )
        # A project-looking question with no confident context: warn the user the
        # answer isn't grounded (the prompt already tells the model to abstain).
        warnings = list(extra_warnings or [])
        if project_context_missing and looks_project_specific(request.question):
            warnings.append(PROJECT_NOT_FOUND_WARNING)
        extra_warnings = warnings
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
        force: bool = False,
        corrective: bool = False,
    ) -> str:
        """Best-effort LLM rewrite of the retrieval query (opt-in via env).

        Asks the already-loaded answer model to distil the question into search
        terms, then merges the result with the original wording. Any error, empty,
        or degenerate reply falls back to ``base_query``, so retrieval is never
        worse than the no-rewrite path. ``force`` runs the rewrite even when the
        env toggle is off — used by the one-shot corrective retrieval (CRAG-lite).
        ``corrective`` uses a prompt that asks for *different* terms, so the
        corrective pass doesn't just reproduce the query that already failed.
        """
        if not self.enable_query_rewrite and not force:
            return base_query
        prior_terms = "\n".join(
            content
            for role, content in self._conversation_history(request)
            if role == "user" and content.strip()
        )
        build_prompt = (
            build_corrective_query_rewrite_prompt if corrective else build_query_rewrite_prompt
        )
        prompt = build_prompt(request.question, prior_terms=prior_terms or None)
        try:
            raw = llm_provider.generate(prompt, None, 0.0, False, None)
        except Exception:  # noqa: BLE001 - rewrite is optional, never fail the ask
            return base_query
        rewritten = parse_rewritten_query(raw, request.question)
        return merge_queries(base_query, rewritten)

    def _indexed_paths(self, workspace_id: str) -> list[str]:
        """Every file currently indexed for the workspace, from the manifest."""
        repo = self.index_manifest_repository
        if repo is None:
            return []
        try:
            return sorted(repo.get(workspace_id) or {})
        except Exception:  # noqa: BLE001 — a missing manifest disables the jump, nothing more
            return []

    def _chunks_of(self, workspace_id: str, source_path: str) -> list[ContextSearchResult]:
        """One file's chunks as context, ready to be placed. The score is a
        placeholder — ``follow_supersession`` replaces it with the score of the
        page that pointed here, so the successor ranks where its predecessor did."""
        try:
            chunks = self.vector_store.get_source_chunks(workspace_id, source_path)
        except Exception:  # noqa: BLE001 — a file we can't read is a file we don't add
            return []
        return [
            ContextSearchResult(
                chunk_id=chunk.chunk_id,
                source_path=source_path,
                content=chunk.content,
                score=0.0,
                metadata={},
            )
            for chunk in chunks
        ]

    def _follow_supersession(
        self,
        workspace_id: str,
        context_results: list[ContextSearchResult],
    ) -> list[ContextSearchResult]:
        """Add the successor of any retrieved page that declares itself replaced.

        The page names its own replacement — "Superseded by [[ADR-08] …]" is an
        address, and the file it addresses is sitting in the same index. Fetching
        it is a lookup, not a guess: no embeddings, no model.

        This is not a nicety. Telling a model a decision was superseded while
        showing it only the dead page is worse than saying nothing: on 2026-07-15
        it answered with a storage technology that appeared in none of its sources,
        having been told a replacement existed and left to imagine it. The cure is
        to hand over the replacement.

        One hop, only where the page points. If the successor is itself superseded,
        its own status line will say so the next time it is retrieved — chasing a
        chain is how a context window fills with history.
        """
        return follow_supersession(
            context_results,
            self._indexed_paths(workspace_id),
            lambda path: self._chunks_of(workspace_id, path),
            source_status_line,
        )

    def _full_project_context(self, workspace_id: str) -> list[ContextSearchResult]:
        """Every indexed chunk of every file, ordered by file then position — the
        whole project as context. Used only when it provably fits the window.
        Returns [] (→ fall back to retrieval) if the manifest or chunks are
        unavailable."""
        repo = self.index_manifest_repository
        if repo is None:
            return []
        try:
            manifest = repo.get(workspace_id) or {}
        except Exception:  # noqa: BLE001 — fail-open to retrieval
            return []
        results: list[ContextSearchResult] = []
        for source_path in sorted(manifest):
            try:
                chunks = self.vector_store.get_source_chunks(workspace_id, source_path)
            except Exception:  # noqa: BLE001 — skip a file we can't read, keep the rest
                continue
            for chunk in chunks:
                results.append(
                    ContextSearchResult(
                        chunk_id=chunk.chunk_id,
                        source_path=source_path,
                        content=chunk.content,
                        score=1.0,
                        metadata={},
                    )
                )
        return results

    def _maybe_full_project_context(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort | None,
    ) -> list[ContextSearchResult] | None:
        """Small-project full-context mode: if the entire index provably fits the
        model's window, return all files as context (retrieval-free, citations
        intact). Returns None when the project is too big or the feature is off, so
        the caller proceeds with normal retrieval."""
        if self.index_manifest_repository is None:
            return None
        try:
            status = self.index_status_repository.get(request.workspace_id)
        except Exception:  # noqa: BLE001 — fail-open to retrieval
            return None
        chunks_count = getattr(status, "chunks_count", 0) if status else 0
        context_window = getattr(llm_provider, "context_window", None)
        if not project_fits_whole_context(chunks_count, context_window):
            return None
        full = self._full_project_context(request.workspace_id)
        return full or None

    def _expand_parents(
        self,
        workspace_id: str,
        results: list[ContextSearchResult],
    ) -> list[ContextSearchResult]:
        """Small-to-big: grow each retrieved chunk with its file neighbours so the
        model sees enough surrounding context (a matched function body regains its
        signature/imports). Deterministic and fail-open — any lookup error leaves the
        retrieved chunks untouched."""
        if not results:
            return results
        try:
            return expand_to_parents(
                results,
                lambda source_path: self.vector_store.get_source_chunks(workspace_id, source_path),
            )
        except Exception:  # noqa: BLE001 — expansion is optional, never fail the ask
            return results

    def _corrective_retrieval(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort | None,
    ) -> list[ContextSearchResult] | None:
        """CRAG-lite: one bounded corrective retrieval with a forced LLM query
        rewrite (~73% of RAG failures are retrieval, not generation). Returns the
        new expanded context, or None if it can't run or comes back empty. Skipped
        only for obvious chit-chat (not gated on looks_project_specific, which says
        False for most real project questions and would starve the corrective pass);
        deterministic control flow, fully fail-open."""
        if llm_provider is None or looks_general_chat(request.question):
            return None
        try:
            results = self._search_context(
                request, llm_provider, force_rewrite=True, corrective_rewrite=True
            )
        except Exception:  # noqa: BLE001 — correction is optional, never fail the ask
            return None
        return results or None

    def _corrective_regeneration(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort,
        prompt_history: list[tuple[str, str]],
        current_warnings: list[RagQualityWarning],
        current_best_score: float,
    ) -> dict | None:
        """CRAG-lite trigger (b): when the answer has hard grounding warnings, try
        ONE corrective retrieval and regenerate — but keep the new answer only if it
        strictly reduces hard grounding warnings AND the corrective retrieval scored
        higher than the original. Returns the replacement bundle or None (keep the
        original). Bounded to a single extra retrieval + generation."""
        hard = _hard_grounding_warnings(current_warnings)
        if not hard:
            return None
        corrected = self._corrective_retrieval(request, llm_provider)
        corrected_best = _best_score(corrected)
        if not corrected or corrected_best <= current_best_score:
            return None
        context_results, prompt, memory_used, facts_used, context_used = self._grounded_prompt(
            request, llm_provider, corrected, prompt_history
        )
        try:
            answer, usage = self._generate_answer_with_usage(
                llm_provider,
                prompt,
                request.images,
                request.temperature,
                request.think,
                prompt_history,
            )
        except RuntimeError:
            return None
        sources = _sources_of(context_results)
        warnings = evaluate_rag_answer(
            question=request.question,
            answer=answer,
            sources=sources,
            source_contents=[result.content for result in context_results],
        )
        if len(_hard_grounding_warnings(warnings)) >= len(hard):
            return None  # the retry didn't actually improve grounding — keep original
        return {
            "answer": answer,
            "sources": sources,
            "context_results": context_results,
            "warnings": warnings,
            "usage": usage,
            "memory_used": memory_used,
            "facts_used": facts_used,
            "context_used": context_used,
        }

    def _search_context(
        self,
        request: AskWorkspaceQuestionInput,
        llm_provider: LLMProviderPort | None = None,
        force_rewrite: bool = False,
        corrective_rewrite: bool = False,
    ) -> list[ContextSearchResult]:
        if request.limit <= 0 or not request.question.strip():
            return []

        # Small-project full-context mode: when the whole index provably fits the
        # window, feed every file instead of retrieving — on a small project the
        # retriever can only add the risk of missing the right file. Citations stay
        # intact (each chunk keeps its source_path); fit_context_results downstream
        # is still the overflow guard.
        #
        # Gated to skip obvious chit-chat: full-context bypasses the relevance
        # threshold (its results carry an artificial score), so without this gate
        # "what time is it" on a tiny project would come back with the whole repo
        # attached. Using NOT looks_general_chat (rather than looks_project_specific)
        # is deliberate — most real project questions look generic to the project
        # detector, so this lets full-context fire for them while still excluding
        # the small, well-detected chit-chat class.
        if not looks_general_chat(request.question):
            full_context = self._maybe_full_project_context(request, llm_provider)
            if full_context is not None:
                return full_context

        # Expand the follow-up with recent conversation terms so retrieval lands
        # on the files the dialogue is about ("disable it" -> "...ecs...disable it").
        retrieval_query = self._retrieval_query(request)
        # Deterministic domain-synonym expansion (csp↔content-security-policy,
        # k8s↔kubernetes, dev↔development, …): bridges the vocabulary gap between
        # how the user asks and how the code is written, before any LLM rewrite.
        # Pure and always-on — it only adds tokens, never removes the user's.
        retrieval_query = expand_query_synonyms(retrieval_query)
        if llm_provider is not None:
            retrieval_query = self._rewrite_query(
                retrieval_query,
                request,
                llm_provider,
                force=force_rewrite,
                corrective=corrective_rewrite,
            )
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
            # Don't let one file's chunks fill the whole context (starving other
            # relevant files); cap per source before the reranker picks.
            candidates = limit_per_source(candidates)
            if len(candidates) <= request.limit:
                return self._expand_parents(
                    request.workspace_id, _strip_embeddings(candidates[: request.limit])
                )
            order = self.reranker.rerank(
                retrieval_query, [result.content for result in candidates], request.limit
            )
            reranked = [candidates[i] for i in order if 0 <= i < len(candidates)]
            return self._expand_parents(
                request.workspace_id,
                _strip_embeddings((reranked or candidates)[: request.limit]),
            )

        # Default path (no reranker): fetch a wider pool and pick a relevant-but-
        # diverse subset with MMR, so the budgeted context covers more of the
        # codebase instead of near-duplicate top hits. The answer mode scales how
        # broad that context is (Deep dive pulls more; others baseline).
        chunk_scale = answer_mode_tuning(request.answer_mode).chunk_scale
        target = max(request.limit, round(_ANSWER_CHUNK_TARGET * chunk_scale))
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
        # Cap chunks-per-file before MMR so the diverse subset spans more files
        # rather than several near-duplicate slices of one dominant document.
        candidates = limit_per_source(candidates)
        return self._expand_parents(
            request.workspace_id,
            _strip_embeddings(mmr_select(query_embedding, candidates, target)),
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
