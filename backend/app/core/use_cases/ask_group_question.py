"""Ask one question across every repository in a group.

Strategy (deterministic retrieval, one LLM call):
  1. Embed the question once.
  2. Search each member's own vector store, capped per repo so a single large
     repo can't crowd the others out of the context window.
  3. Merge the tagged candidates by score and keep the global top-K.
  4. Answer from that merged context with sources attributed to their repo.

Each member stays a normal workspace underneath — this use case only fans out
retrieval and stitches the results together.
"""

from __future__ import annotations

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


class AskGroupQuestionUseCase:
    def __init__(
        self,
        group_repository: ProjectGroupRepositoryPort,
        workspace_repository: WorkspaceRepositoryPort,
        embedding_provider: EmbeddingProviderPort,
        vector_store: VectorStorePort,
        llm_provider_factory: LLMProviderFactoryPort,
        index_status_repository: IndexStatusRepositoryPort | None = None,
    ) -> None:
        self.group_repository = group_repository
        self.workspace_repository = workspace_repository
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.llm_provider_factory = llm_provider_factory
        self.index_status_repository = index_status_repository

    def execute(self, request: AskGroupQuestionInput) -> GroupQuestionAnswer:
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

        # Prefix each source path with its repo so the model cites "repo/path"
        # and the returned sources stay auditable per repository.
        labelled = [
            replace(t.result, source_path=f"{t.workspace_name}/{t.result.source_path}")
            for t in selected
        ]
        prompt = build_workspace_question_prompt(
            question=request.question,
            context_results=labelled,
            assistant_identity=f"{llm_provider.provider_name}/{llm_provider.model_name}",
        )
        try:
            answer = llm_provider.generate(prompt, None, None, None, None)
        except RuntimeError as exc:
            return GroupQuestionAnswer(
                group_id=group.id,
                question=request.question,
                answer=(
                    "The selected local model could not answer right now. Check that "
                    "the local model engine is running and a model is installed."
                ),
                contributions=self._contributions(members),
                llm_provider=llm_provider.provider_name,
                llm_model=llm_provider.model_name,
                diagnostic_code="selected_llm_runtime_unavailable",
                diagnostic_message=str(exc),
            )

        sources = [
            GroupAnswerSource(
                workspace_id=t.workspace_id,
                workspace_name=t.workspace_name,
                chunk_id=t.result.chunk_id,
                source_path=t.result.source_path,
                score=t.result.score,
                preview=t.result.content[:200],
            )
            for t in selected
        ]
        return GroupQuestionAnswer(
            group_id=group.id,
            question=request.question,
            answer=answer,
            sources=sources,
            contributions=self._contributions(members),
            used_context_chunks=len(selected),
            llm_provider=llm_provider.provider_name,
            llm_model=llm_provider.model_name,
        )

    def _resolve_members(self, workspace_ids: tuple[str, ...]) -> list[_Member]:
        members: list[_Member] = []
        for workspace_id in workspace_ids:
            workspace = self.workspace_repository.get(workspace_id)
            if workspace is None:
                continue
            indexed = self._is_indexed(workspace_id)
            members.append(_Member(workspace_id=workspace_id, name=workspace.name, indexed=indexed))
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

    def _create_llm_provider(self, request: AskGroupQuestionInput):
        try:
            return self.llm_provider_factory.create(
                provider=request.llm_provider_override,
                model=request.llm_model_override,
            )
        except LLMProviderFactoryError as exc:
            raise AskGroupQuestionValidationError(str(exc)) from exc
