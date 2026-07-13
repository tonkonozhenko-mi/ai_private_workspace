"""Ask one question across every repository in a group — at full parity with the
single-repo Ask.

The group answer used to be a thin "fan out, merge by score, one LLM call". It now
runs the same quality pipeline the per-project Ask does, only fanned out across the
members:

  1. Route obvious chit-chat straight to a general answer (no retrieval).
  2. Build the retrieval query with the same deterministic synonym expansion and
     optional LLM rewrite.
  3. Retrieve from each member with per-source diversity caps + MMR (or the
     cross-encoder reranker when enabled) + parent-document expansion, capped per
     repo so one repo can't crowd out the others.
  4. Merge the tagged candidates, and if the best match is below the calibrated
     abstention floor, run one corrective retrieval before honestly answering from
     general knowledge instead of forcing a grounded answer.
  5. Fit the merged context to the model's real window (token budget), answer, then
     run the deterministic grounding checks — and, off the streaming path, one
     CRAG-lite corrective regeneration if the answer is poorly grounded.

Each member stays a normal workspace underneath; this use case only fans out and
stitches the results together, reusing the same domain pieces as the single Ask so
the two never drift apart again.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import datetime
from time import perf_counter

from app.core.domain.context_budget import chunk_token_budget, fit_context_results_by_tokens
from app.core.domain.group_qa import (
    GroupAnswerSource,
    GroupQuestionAnswer,
    GroupRepoContribution,
)
from app.core.domain.indexing import ContextSearchResult
from app.core.domain.llm_usage import build_llm_usage_metrics
from app.core.domain.mmr import mmr_select
from app.core.domain.parent_document import expand_to_parents
from app.core.domain.query_synonyms import expand_query_synonyms
from app.core.domain.question_intent import looks_general_chat, looks_project_specific
from app.core.domain.rag import RagQualityWarning, RagSource
from app.core.domain.rag_answer_cleanup import strip_source_path_echo
from app.core.domain.rag_answer_evaluator import evaluate_rag_answer
from app.core.domain.rag_prompt import (
    build_general_chat_prompt,
    build_workspace_question_prompt,
)
from app.core.domain.rag_query_rewrite import (
    build_corrective_query_rewrite_prompt,
    build_query_rewrite_prompt,
    merge_queries,
    parse_rewritten_query,
)
from app.core.domain.retrieval_diversity import limit_per_source
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.llm_provider import LLMProviderPort
from app.core.ports.llm_provider_factory import (
    LLMProviderFactoryError,
    LLMProviderFactoryPort,
)
from app.core.ports.project_group_repository import ProjectGroupRepositoryPort
from app.core.ports.reranker import RerankerPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.ask_workspace_question import (
    DEFAULT_RELEVANCE_THRESHOLD,
    FAKE_EMBEDDING_RELEVANCE_THRESHOLD,
    PROJECT_NOT_FOUND_WARNING,
    QUERY_REWRITE_ENV_VAR,
    RELEVANCE_FLOOR_MARGIN,
    RELEVANCE_FLOOR_MAX,
    RELEVANCE_FLOOR_MIN,
    RELEVANCE_PROBE_MARGIN,
    RELEVANCE_THRESHOLD_ENV_VAR,
    _hard_grounding_warnings,
    _strip_embeddings,
    _usage_kwargs,
)

NO_MEMBERS_ANSWER = (
    "This group has no repositories yet. Add one or more projects to the group, then ask again."
)
NO_CONTEXT_ANSWER = (
    "Nothing relevant was found across this group's repositories. Build the search "
    "context for its members (scan, then build) so their files can be searched."
)
_LLM_UNAVAILABLE_ANSWER = (
    "The selected local model could not answer right now. Check that the local "
    "model engine is running and a model is installed."
)
GENERAL_CHAT_DIAGNOSTIC_CODE = "answered_as_general_conversation"
GENERAL_CHAT_DIAGNOSTIC_MESSAGE = (
    "No repository in this group was relevant to this question, so it was answered "
    "as general conversation instead of from project context."
)

# Same candidate-pool sizing the single Ask uses for the MMR path.
_MMR_POOL = 24


class AskGroupQuestionNotFoundError(ValueError):
    pass


class AskGroupQuestionValidationError(ValueError):
    pass


@dataclass(frozen=True)
class AskGroupQuestionInput:
    group_id: str
    question: str
    limit: int = 6
    per_repo_cap: int = 3
    llm_provider_override: str | None = None
    llm_model_override: str | None = None
    temperature: float | None = None
    think: bool | None = None


@dataclass(frozen=True)
class GroupAskStreamDelta:
    """A chunk of answer text produced while streaming."""

    text: str


@dataclass(frozen=True)
class GroupAskStreamFinal:
    """The completed answer, emitted once after all deltas."""

    answer: GroupQuestionAnswer


GroupAskStreamEvent = GroupAskStreamDelta | GroupAskStreamFinal


@dataclass
class _Tagged:
    workspace_id: str
    workspace_name: str
    result: ContextSearchResult


@dataclass
class _Member:
    workspace_id: str
    name: str
    indexed: bool = False
    chunks_used: int = field(default=0)


@dataclass
class _Generation:
    """A plan to generate an answer, shared by execute() and execute_stream().

    ``mode`` is "chat" (general conversation, no sources) or "grounded" (answer from
    the merged project context). The grounded fields carry everything needed to
    finish: the fitted context (tagged for repo attribution and labelled for the
    prompt/grounding), the counts, and the best retrieval score for the CRAG gate.
    """

    llm_provider: LLMProviderPort
    mode: str
    prompt: str
    members: list[_Member]
    diagnostic_code: str | None = None
    diagnostic_message: str | None = None
    extra_warnings: list[RagQualityWarning] = field(default_factory=list)
    selected: list[_Tagged] = field(default_factory=list)
    labelled: list[ContextSearchResult] = field(default_factory=list)
    memory_used: int = 0
    facts_used: int = 0
    best_score: float = 0.0
    corrected_retrieval: bool = False


class AskGroupQuestionUseCase:
    def __init__(
        self,
        group_repository: ProjectGroupRepositoryPort,
        workspace_repository: WorkspaceRepositoryPort,
        embedding_provider: EmbeddingProviderPort,
        vector_store: VectorStorePort,
        llm_provider_factory: LLMProviderFactoryPort,
        index_status_repository: IndexStatusRepositoryPort | None = None,
        project_context_provider=None,
        reranker: RerankerPort | None = None,
        rerank_candidates: int = 30,
        enable_query_rewrite: bool | None = None,
    ) -> None:
        self.group_repository = group_repository
        self.workspace_repository = workspace_repository
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.llm_provider_factory = llm_provider_factory
        self.index_status_repository = index_status_repository
        # Optional shared project-context provider (handbook + memory + graph
        # facts) with compose_with_stats(scope_id, query). None = no context.
        self.project_context_provider = project_context_provider
        # Optional cross-encoder precision pass, shared with the single Ask. None or
        # a disabled reranker → plain hybrid retrieval, exactly as before.
        self.reranker = reranker
        self.rerank_candidates = rerank_candidates
        # Optional LLM query rewrite before retrieval. Same precedence as the single
        # Ask: explicit env override wins; otherwise default ON when a reranker is
        # active (the user already opted into the extra latency), OFF for plain
        # hybrid retrieval.
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

    # --- Public API ---

    def execute(self, request: AskGroupQuestionInput) -> GroupQuestionAnswer:
        prepared = self._prepare(request)
        if isinstance(prepared, GroupQuestionAnswer):
            return prepared
        try:
            answer, usage = self._generate(request, prepared)
        except RuntimeError as exc:
            return self._runtime_error_answer(request, prepared, exc)

        if prepared.mode != "grounded":
            return self._chat_answer(request, prepared, answer, usage)

        warnings = self._grounding_warnings(request, prepared, answer)
        if not prepared.corrected_retrieval:
            regen = self._corrective_regeneration(request, prepared, warnings)
            if regen is not None:
                prepared, answer, usage, warnings = regen
        return self._grounded_answer(request, prepared, answer, usage, warnings)

    def execute_stream(self, request: AskGroupQuestionInput) -> Iterator[GroupAskStreamEvent]:
        prepared = self._prepare(request)
        if isinstance(prepared, GroupQuestionAnswer):
            yield GroupAskStreamFinal(prepared)
            return

        answer, usage, failed = yield from self._stream_generate(request, prepared)
        if failed is not None:
            yield GroupAskStreamFinal(self._runtime_error_answer(request, prepared, failed))
            return

        if prepared.mode != "grounded":
            yield GroupAskStreamFinal(self._chat_answer(request, prepared, answer, usage))
            return
        # Streaming applies only the pre-generation correction (CRAG trigger a);
        # a post-answer regenerate can't rewind tokens already streamed.
        warnings = self._grounding_warnings(request, prepared, answer)
        yield GroupAskStreamFinal(self._grounded_answer(request, prepared, answer, usage, warnings))

    # --- Preparation (retrieval + routing + threshold) ---

    def _prepare(self, request: AskGroupQuestionInput) -> _Generation | GroupQuestionAnswer:
        if not request.question.strip():
            raise AskGroupQuestionValidationError("A question is required.")
        group = self.group_repository.get(request.group_id)
        if group is None:
            raise AskGroupQuestionNotFoundError("Group not found")

        members = self._resolve_members(group.workspace_ids)
        if not members:
            return GroupQuestionAnswer(
                group_id=group.id,
                question=request.question,
                answer=NO_MEMBERS_ANSWER,
                diagnostic_code="group_empty",
            )

        llm_provider = self._create_llm_provider(request)

        # Obvious chit-chat: answer directly, no retrieval across any repo.
        if looks_general_chat(request.question):
            return _Generation(
                llm_provider=llm_provider,
                mode="chat",
                prompt=self._general_prompt(request, llm_provider, project_context_missing=False),
                members=members,
                diagnostic_code=GENERAL_CHAT_DIAGNOSTIC_CODE,
                diagnostic_message=GENERAL_CHAT_DIAGNOSTIC_MESSAGE,
            )

        pool = self._gather(request, members, llm_provider, force_rewrite=False)
        if not pool:
            return GroupQuestionAnswer(
                group_id=group.id,
                question=request.question,
                answer=NO_CONTEXT_ANSWER,
                contributions=self._contributions(members),
                llm_provider=llm_provider.provider_name,
                llm_model=llm_provider.model_name,
                diagnostic_code="group_no_context",
            )

        merged = sorted(pool, key=lambda t: t.result.score, reverse=True)
        best_score = merged[0].result.score
        threshold = self._group_threshold(members)
        corrected = False
        if best_score < threshold:
            # CRAG-lite trigger (a): one corrective retrieval (forced, differentiated
            # rewrite) before abstaining across the whole group.
            cpool = self._gather(request, members, llm_provider, force_rewrite=True)
            cbest = max((t.result.score for t in cpool), default=0.0)
            if cpool and cbest >= threshold:
                merged = sorted(cpool, key=lambda t: t.result.score, reverse=True)
                best_score = cbest
                corrected = True
            else:
                warnings = (
                    [PROJECT_NOT_FOUND_WARNING] if looks_project_specific(request.question) else []
                )
                return _Generation(
                    llm_provider=llm_provider,
                    mode="chat",
                    prompt=self._general_prompt(
                        request, llm_provider, project_context_missing=True
                    ),
                    members=members,
                    diagnostic_code=GENERAL_CHAT_DIAGNOSTIC_CODE,
                    diagnostic_message=GENERAL_CHAT_DIAGNOSTIC_MESSAGE,
                    extra_warnings=warnings,
                )

        return self._build_grounded(
            request, group.id, members, merged, best_score, corrected, llm_provider
        )

    def _build_grounded(
        self,
        request: AskGroupQuestionInput,
        group_id: str,
        members: list[_Member],
        merged: list[_Tagged],
        best_score: float,
        corrected: bool,
        llm_provider: LLMProviderPort,
    ) -> _Generation:
        selected = merged[: max(1, request.limit)]
        labelled_all = [
            replace(t.result, source_path=f"{t.workspace_name}/{t.result.source_path}")
            for t in selected
        ]
        memory_section, memory_used, facts_used = self._project_context(
            group_id, members, request.question
        )
        token_counter = getattr(llm_provider, "count_tokens", None)
        budget = chunk_token_budget(
            getattr(llm_provider, "context_window", None),
            memory_text=memory_section,
            history=[],
            # The question shares the window with the chunks; counting it is the
            # difference between a budget and a wish.
            question=request.question,
            token_counter=token_counter,
        )
        fitted_labelled = fit_context_results_by_tokens(labelled_all, budget, token_counter)
        fitted = selected[: len(fitted_labelled)]
        for member in members:
            member.chunks_used = sum(1 for t in fitted if t.workspace_id == member.workspace_id)
        prompt = build_workspace_question_prompt(
            question=request.question,
            context_results=fitted_labelled,
            assistant_identity=f"{llm_provider.provider_name}/{llm_provider.model_name}",
            project_memory_section=memory_section,
        )
        return _Generation(
            llm_provider=llm_provider,
            mode="grounded",
            prompt=prompt,
            members=members,
            selected=fitted,
            labelled=fitted_labelled,
            memory_used=memory_used,
            facts_used=facts_used,
            best_score=best_score,
            corrected_retrieval=corrected,
        )

    def _gather(
        self,
        request: AskGroupQuestionInput,
        members: list[_Member],
        llm_provider: LLMProviderPort | None,
        force_rewrite: bool,
    ) -> list[_Tagged]:
        retrieval_query = expand_query_synonyms(request.question)
        if llm_provider is not None and (self.enable_query_rewrite or force_rewrite):
            retrieval_query = self._rewrite_query(
                request.question, retrieval_query, llm_provider, corrective=force_rewrite
            )
        query_embedding = self.embedding_provider.embed_text(retrieval_query)
        cap = max(1, request.per_repo_cap)
        pool: list[_Tagged] = []
        for member in members:
            if not member.indexed:
                continue
            for result in self._retrieve_member(
                member.workspace_id, query_embedding, retrieval_query, cap
            ):
                pool.append(
                    _Tagged(
                        workspace_id=member.workspace_id,
                        workspace_name=member.name,
                        result=result,
                    )
                )
        return pool

    def _retrieve_member(
        self,
        workspace_id: str,
        query_embedding: list[float],
        retrieval_query: str,
        cap: int,
    ) -> list[ContextSearchResult]:
        """One member's retrieval, mirroring the single Ask: per-source diversity
        cap then MMR (or the reranker), then parent-document expansion. Capped to
        ``cap`` so no single repo dominates the merged context."""
        rerank = self.reranker is not None and self.reranker.enabled
        if rerank:
            candidates = self.vector_store.search(
                workspace_id=workspace_id,
                query_embedding=query_embedding,
                limit=max(cap, self.rerank_candidates),
                embedding_provider=self.embedding_provider.provider_name,
                embedding_model=self.embedding_provider.model_name,
                embedding_dimension=len(query_embedding),
                query_text=retrieval_query,
            )
            candidates = limit_per_source(candidates)
            if len(candidates) > cap:
                order = self.reranker.rerank(retrieval_query, [c.content for c in candidates], cap)
                reranked = [candidates[i] for i in order if 0 <= i < len(candidates)]
                candidates = reranked or candidates
            picked = candidates[:cap]
        else:
            pool = max(cap * 3, _MMR_POOL)
            candidates = self.vector_store.search(
                workspace_id=workspace_id,
                query_embedding=query_embedding,
                limit=pool,
                embedding_provider=self.embedding_provider.provider_name,
                embedding_model=self.embedding_provider.model_name,
                embedding_dimension=len(query_embedding),
                query_text=retrieval_query,
            )
            candidates = limit_per_source(candidates)
            picked = mmr_select(query_embedding, candidates, cap)
        return _strip_embeddings(self._expand_parents(workspace_id, picked))

    def _expand_parents(
        self, workspace_id: str, results: list[ContextSearchResult]
    ) -> list[ContextSearchResult]:
        if not results:
            return results
        try:
            return expand_to_parents(
                results,
                lambda source_path: self.vector_store.get_source_chunks(workspace_id, source_path),
            )
        except Exception:  # noqa: BLE001 — expansion is optional, never fail the ask
            return results

    def _rewrite_query(
        self,
        question: str,
        base_query: str,
        llm_provider: LLMProviderPort,
        corrective: bool,
    ) -> str:
        build = build_corrective_query_rewrite_prompt if corrective else build_query_rewrite_prompt
        prompt = build(question, prior_terms=None)
        try:
            raw = llm_provider.generate(prompt, None, 0.0, False, None)
        except Exception:  # noqa: BLE001 - rewrite is optional, never fail the ask
            return base_query
        return merge_queries(base_query, parse_rewritten_query(raw, question))

    def _group_threshold(self, members: list[_Member]) -> float:
        """The abstention floor for the group: the strictest of its indexed members'
        calibrated thresholds (all members share one embedding model, so their score
        scales are comparable)."""
        override = os.environ.get(RELEVANCE_THRESHOLD_ENV_VAR)
        if override:
            try:
                return float(override)
            except ValueError:
                pass
        if getattr(self.embedding_provider, "provider_name", "") == "fake":
            return FAKE_EMBEDDING_RELEVANCE_THRESHOLD
        thresholds = [self._member_threshold(m.workspace_id) for m in members if m.indexed]
        return max(thresholds) if thresholds else DEFAULT_RELEVANCE_THRESHOLD

    def _member_threshold(self, workspace_id: str) -> float:
        floor = None
        probe_ceiling = None
        if self.index_status_repository is not None:
            status = self.index_status_repository.get(workspace_id)
            floor = getattr(status, "relevance_floor", None)
            probe_ceiling = getattr(status, "relevance_probe_ceiling", None)
        if floor is None:
            return DEFAULT_RELEVANCE_THRESHOLD
        base = max(RELEVANCE_FLOOR_MIN, min(RELEVANCE_FLOOR_MAX, floor - RELEVANCE_FLOOR_MARGIN))
        # Same second anchor as single-project Ask: cap the bar just above the
        # empirical chit-chat ceiling. min() means it can only lower a member's
        # threshold, never raise it.
        if probe_ceiling is not None:
            base = max(RELEVANCE_FLOOR_MIN, min(base, probe_ceiling + RELEVANCE_PROBE_MARGIN))
        return base

    # --- Generation ---

    def _generate(
        self, request: AskGroupQuestionInput, prepared: _Generation
    ) -> tuple[str, object | None]:
        started_at = perf_counter()
        raw = prepared.llm_provider.generate(
            prepared.prompt, None, request.temperature, request.think, None
        )
        answer = strip_source_path_echo(raw)
        usage = build_llm_usage_metrics(
            prompt=prepared.prompt,
            completion=answer,
            latency_ms=max(0, round((perf_counter() - started_at) * 1000)),
            provider=prepared.llm_provider.provider_name,
            model=prepared.llm_provider.model_name,
            **_usage_kwargs(prepared.llm_provider),
        )
        return answer, usage

    def _stream_generate(
        self, request: AskGroupQuestionInput, prepared: _Generation
    ) -> Iterator[GroupAskStreamEvent]:
        """Yield token deltas and return ``(answer, usage, error)``; ``error`` is an
        exception on failure, else None."""
        started_at = perf_counter()
        chunks: list[str] = []
        stream = getattr(prepared.llm_provider, "generate_stream", None)
        try:
            if callable(stream):
                for delta in stream(
                    prepared.prompt, None, request.temperature, request.think, None
                ):
                    if not delta:
                        continue
                    chunks.append(delta)
                    yield GroupAskStreamDelta(delta)
            else:
                text = prepared.llm_provider.generate(
                    prepared.prompt, None, request.temperature, request.think, None
                )
                chunks.append(text)
                yield GroupAskStreamDelta(text)
        except RuntimeError as exc:
            return "", None, exc

        answer = strip_source_path_echo("".join(chunks))
        usage = build_llm_usage_metrics(
            prompt=prepared.prompt,
            completion=answer,
            latency_ms=max(0, round((perf_counter() - started_at) * 1000)),
            provider=prepared.llm_provider.provider_name,
            model=prepared.llm_provider.model_name,
            **_usage_kwargs(prepared.llm_provider),
        )
        return answer, usage, None

    def _grounding_warnings(
        self, request: AskGroupQuestionInput, prepared: _Generation, answer: str
    ) -> list[RagQualityWarning]:
        rag_sources = [
            RagSource(
                chunk_id=r.chunk_id,
                source_path=r.source_path,
                score=r.score,
                preview=r.content[:200],
            )
            for r in prepared.labelled
        ]
        return evaluate_rag_answer(
            question=request.question,
            answer=answer,
            sources=rag_sources,
            source_contents=[r.content for r in prepared.labelled],
        )

    def _corrective_regeneration(
        self,
        request: AskGroupQuestionInput,
        prepared: _Generation,
        current_warnings: list[RagQualityWarning],
    ) -> tuple[_Generation, str, object | None, list[RagQualityWarning]] | None:
        """CRAG-lite trigger (b): when the grounded answer has hard grounding
        warnings, run one corrective retrieval + regeneration, keeping it only if it
        strictly reduces hard warnings and the corrective retrieval scored higher."""
        hard = _hard_grounding_warnings(current_warnings)
        if not hard:
            return None
        cpool = self._gather(request, prepared.members, prepared.llm_provider, force_rewrite=True)
        cbest = max((t.result.score for t in cpool), default=0.0)
        if not cpool or cbest <= prepared.best_score:
            return None
        merged = sorted(cpool, key=lambda t: t.result.score, reverse=True)
        regen = self._build_grounded(
            request,
            request.group_id,
            prepared.members,
            merged,
            cbest,
            True,
            prepared.llm_provider,
        )
        try:
            answer, usage = self._generate(request, regen)
        except RuntimeError:
            return None
        warnings = self._grounding_warnings(request, regen, answer)
        if len(_hard_grounding_warnings(warnings)) >= len(hard):
            return None  # the retry didn't actually improve grounding — keep original
        return regen, answer, usage, warnings

    # --- Answer assembly ---

    def _chat_answer(
        self, request: AskGroupQuestionInput, prepared: _Generation, answer: str, usage
    ) -> GroupQuestionAnswer:
        return GroupQuestionAnswer(
            group_id=request.group_id,
            question=request.question,
            answer=answer,
            contributions=self._contributions(prepared.members),
            llm_provider=prepared.llm_provider.provider_name,
            llm_model=prepared.llm_provider.model_name,
            diagnostic_code=prepared.diagnostic_code,
            diagnostic_message=prepared.diagnostic_message,
            quality_warnings=list(prepared.extra_warnings),
            usage=usage,
        )

    def _grounded_answer(
        self,
        request: AskGroupQuestionInput,
        prepared: _Generation,
        answer: str,
        usage,
        warnings: list[RagQualityWarning],
    ) -> GroupQuestionAnswer:
        sources = [
            GroupAnswerSource(
                workspace_id=t.workspace_id,
                workspace_name=t.workspace_name,
                chunk_id=t.result.chunk_id,
                source_path=t.result.source_path,
                score=t.result.score,
                preview=t.result.content[:200],
            )
            for t in prepared.selected
        ]
        return GroupQuestionAnswer(
            group_id=request.group_id,
            question=request.question,
            answer=answer,
            sources=sources,
            contributions=self._contributions(prepared.members),
            used_context_chunks=len(prepared.selected),
            llm_provider=prepared.llm_provider.provider_name,
            llm_model=prepared.llm_provider.model_name,
            memory_used=prepared.memory_used,
            facts_used=prepared.facts_used,
            quality_warnings=warnings,
            usage=usage,
        )

    def _runtime_error_answer(
        self, request: AskGroupQuestionInput, prepared: _Generation, exc: Exception
    ) -> GroupQuestionAnswer:
        return GroupQuestionAnswer(
            group_id=request.group_id,
            question=request.question,
            answer=_LLM_UNAVAILABLE_ANSWER,
            contributions=self._contributions(prepared.members),
            llm_provider=prepared.llm_provider.provider_name,
            llm_model=prepared.llm_provider.model_name,
            diagnostic_code="selected_llm_runtime_unavailable",
            diagnostic_message=str(exc),
        )

    def _general_prompt(
        self,
        request: AskGroupQuestionInput,
        llm_provider: LLMProviderPort,
        project_context_missing: bool,
    ) -> str:
        return build_general_chat_prompt(
            question=request.question,
            skill_instructions=[],
            current_time=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
            attached_section="",
            assistant_identity=f"{llm_provider.provider_name}/{llm_provider.model_name}",
            project_context_missing=project_context_missing,
        )

    # --- Members + context ---

    def _project_context(
        self, group_id: str, members: list[_Member], query: str
    ) -> tuple[str, int, int]:
        """Compose project context (handbook + memory + facts) for the group: the
        group's own notes/handbook first, then each member's. Best-effort and
        capped, so answering never depends on it."""
        provider = self.project_context_provider
        if provider is None or not hasattr(provider, "compose_with_stats"):
            return "", 0, 0
        sections: list[str] = []
        memory_used = 0
        facts_used = 0
        for label, scope_id in [("Group", group_id), *[(m.name, m.workspace_id) for m in members]]:
            try:
                text, stats = provider.compose_with_stats(scope_id, query)
            except Exception:  # noqa: BLE001 - context is optional, never fatal
                continue
            if text and text.strip():
                sections.append(f"# {label}\n{text.strip()}")
                memory_used += getattr(stats, "memory_items", 0)
                facts_used += getattr(stats, "graph_facts", 0)
        return "\n\n".join(sections), memory_used, facts_used

    def _resolve_members(self, workspace_ids: tuple[str, ...]) -> list[_Member]:
        members: list[_Member] = []
        for workspace_id in workspace_ids:
            workspace = self.workspace_repository.get(workspace_id)
            if workspace is None:
                continue
            members.append(
                _Member(
                    workspace_id=workspace_id,
                    name=workspace.name,
                    indexed=self._is_indexed(workspace_id),
                )
            )
        return members

    def _is_indexed(self, workspace_id: str) -> bool:
        if self.index_status_repository is None:
            return True
        status = self.index_status_repository.get(workspace_id)
        return status is not None and status.status != "not_indexed"

    @staticmethod
    def _contributions(members: list[_Member]) -> list[GroupRepoContribution]:
        return [
            GroupRepoContribution(
                workspace_id=m.workspace_id,
                workspace_name=m.name,
                indexed=m.indexed,
                chunks_used=m.chunks_used,
            )
            for m in members
        ]

    def _create_llm_provider(self, request: AskGroupQuestionInput) -> LLMProviderPort:
        try:
            return self.llm_provider_factory.create(
                provider=request.llm_provider_override,
                model=request.llm_model_override,
            )
        except LLMProviderFactoryError as exc:
            raise AskGroupQuestionValidationError(str(exc)) from exc
