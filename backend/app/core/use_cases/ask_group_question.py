"""Ask one question across every repository in a group.

Strategy (deterministic retrieval, one LLM call):
  1. Embed the question once.
  2. Search each member's own vector store, capped per repo so a single large
     repo can't crowd the others out of the context window.
  3. Merge the tagged candidates by score and keep the global top-K.
  4. Answer from that merged context with sources attributed to their repo.

Like the single-repo Ask, the answer can be grounded with project context
(handbook + memory + graph facts) composed across the members, can stream token
by token, and honours the reasoning/temperature controls. Each member stays a
normal workspace underneath — this use case only fans out retrieval and stitches
the results together.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field, replace

from app.core.domain.group_qa import (
    GroupAnswerSource,
    GroupQuestionAnswer,
    GroupRepoContribution,
)
from app.core.domain.indexing import ContextSearchResult
from app.core.domain.rag_prompt import build_workspace_question_prompt
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.llm_provider import LLMProviderPort
from app.core.ports.llm_provider_factory import (
    LLMProviderFactoryError,
    LLMProviderFactoryPort,
)
from app.core.ports.project_group_repository import ProjectGroupRepositoryPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort

NO_MEMBERS_ANSWER = (
    "This group has no repositories yet. Add one or more projects to the group, "
    "then ask again."
)
NO_CONTEXT_ANSWER = (
    "Nothing relevant was found across this group's repositories. Build the search "
    "context for its members (scan, then build) so their files can be searched."
)
_LLM_UNAVAILABLE_ANSWER = (
    "The selected local model could not answer right now. Check that the local "
    "model engine is running and a model is installed."
)
_CONTEXT_CHAR_BUDGET = 2000


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
class _Prepared:
    """Everything needed to generate, once retrieval + prompt are ready."""

    llm_provider: LLMProviderPort
    prompt: str
    selected: list[_Tagged]
    members: list[_Member]
    memory_used: int
    facts_used: int


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
    ) -> None:
        self.group_repository = group_repository
        self.workspace_repository = workspace_repository
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.llm_provider_factory = llm_provider_factory
        self.index_status_repository = index_status_repository
        # Optional shared project-context provider (handbook + memory + graph
        # facts) with compose_with_stats(workspace_id, query). None = no context.
        self.project_context_provider = project_context_provider

    # --- Public API ---

    def execute(self, request: AskGroupQuestionInput) -> GroupQuestionAnswer:
        prepared = self._prepare(request)
        if isinstance(prepared, GroupQuestionAnswer):
            return prepared
        try:
            answer = prepared.llm_provider.generate(
                prepared.prompt, None, request.temperature, request.think, None
            )
        except RuntimeError as exc:
            return self._runtime_error_answer(request, prepared, exc)
        return self._final_answer(request, prepared, answer)

    def execute_stream(
        self, request: AskGroupQuestionInput
    ) -> Iterator[GroupAskStreamEvent]:
        prepared = self._prepare(request)
        if isinstance(prepared, GroupQuestionAnswer):
            yield GroupAskStreamFinal(prepared)
            return

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
                answer = prepared.llm_provider.generate(
                    prepared.prompt, None, request.temperature, request.think, None
                )
                chunks.append(answer)
                yield GroupAskStreamDelta(answer)
        except RuntimeError as exc:
            yield GroupAskStreamFinal(self._runtime_error_answer(request, prepared, exc))
            return

        yield GroupAskStreamFinal(self._final_answer(request, prepared, "".join(chunks)))

    # --- Internal ---

    def _prepare(self, request: AskGroupQuestionInput) -> _Prepared | GroupQuestionAnswer:
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
        pool = self._gather_candidates(request, members)
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

        selected = sorted(pool, key=lambda t: t.result.score, reverse=True)[: request.limit]
        for member in members:
            member.chunks_used = sum(
                1 for t in selected if t.workspace_id == member.workspace_id
            )

        memory_section, memory_used, facts_used = self._project_context(
            group.id, members, request.question
        )
        labelled = [
            replace(t.result, source_path=f"{t.workspace_name}/{t.result.source_path}")
            for t in selected
        ]
        prompt = build_workspace_question_prompt(
            question=request.question,
            context_results=labelled,
            assistant_identity=f"{llm_provider.provider_name}/{llm_provider.model_name}",
            project_memory_section=memory_section,
        )
        return _Prepared(
            llm_provider=llm_provider,
            prompt=prompt,
            selected=selected,
            members=members,
            memory_used=memory_used,
            facts_used=facts_used,
        )

    def _final_answer(
        self, request: AskGroupQuestionInput, prepared: _Prepared, answer: str
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
        )

    def _runtime_error_answer(
        self, request: AskGroupQuestionInput, prepared: _Prepared, exc: Exception
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

    def _project_context(
        self, group_id: str, members: list[_Member], query: str
    ) -> tuple[str, int, int]:
        """Compose project context (handbook + memory + facts) for the group.

        Pulls the group's own notes and handbook (keyed by the group id) first,
        then each member's context. Best-effort: any provider error yields no
        context so answering never depends on it. Capped overall.
        """
        provider = self.project_context_provider
        if provider is None or not hasattr(provider, "compose_with_stats"):
            return "", 0, 0
        sections: list[str] = []
        memory_used = 0
        facts_used = 0
        # The group's own memory + handbook come first, labelled as the group.
        for label, scope_id in [("Group", group_id), *[(m.name, m.workspace_id) for m in members]]:
            try:
                text, stats = provider.compose_with_stats(scope_id, query)
            except Exception:  # noqa: BLE001 - context is optional, never fatal
                continue
            if text and text.strip():
                sections.append(f"# {label}\n{text.strip()}")
                memory_used += getattr(stats, "memory_items", 0)
                facts_used += getattr(stats, "graph_facts", 0)
        combined = "\n\n".join(sections)[:_CONTEXT_CHAR_BUDGET]
        return combined, memory_used, facts_used

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

    def _gather_candidates(
        self, request: AskGroupQuestionInput, members: list[_Member]
    ) -> list[_Tagged]:
        cap = max(1, request.per_repo_cap)
        query_embedding = self.embedding_provider.embed_text(request.question)
        pool: list[_Tagged] = []
        for member in members:
            if not member.indexed:
                continue
            candidates = self.vector_store.search(
                workspace_id=member.workspace_id,
                query_embedding=query_embedding,
                limit=cap,
                embedding_provider=self.embedding_provider.provider_name,
                embedding_model=self.embedding_provider.model_name,
                embedding_dimension=len(query_embedding),
                query_text=request.question,
            )
            for result in candidates[:cap]:
                pool.append(
                    _Tagged(
                        workspace_id=member.workspace_id,
                        workspace_name=member.name,
                        result=result,
                    )
                )
        return pool

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
