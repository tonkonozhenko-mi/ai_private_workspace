"""Run a retrieval-quality eval over a workspace's index.

For each golden case, run the same retrieval Ask uses and score which source
files came back. Deterministic given a fixed index + embedder — a stable
regression guard for RAG tuning. No LLM is involved (retrieval only).
"""

from dataclasses import dataclass, field

from app.core.domain.answer_eval import EvalCase, EvalReport, aggregate, score_case
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.search_workspace_context import (
    SearchWorkspaceContextInput,
    SearchWorkspaceContextUseCase,
)


@dataclass(frozen=True)
class RunRetrievalEvalInput:
    workspace_id: str
    cases: list[EvalCase] = field(default_factory=list)
    limit: int = 5


class RunRetrievalEvalWorkspaceNotFoundError(ValueError):
    pass


class RunRetrievalEvalUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        embedding_provider: EmbeddingProviderPort,
        vector_store: VectorStorePort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def execute(self, request: RunRetrievalEvalInput) -> EvalReport:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise RunRetrievalEvalWorkspaceNotFoundError("Workspace not found")

        search = SearchWorkspaceContextUseCase(
            self.workspace_repository, self.embedding_provider, self.vector_store
        )
        scores = []
        for case in request.cases:
            results = search.execute(
                SearchWorkspaceContextInput(
                    workspace_id=request.workspace_id,
                    query=case.question,
                    limit=request.limit,
                )
            )
            retrieved = [r.source_path for r in results]
            top_score = max((r.score for r in results), default=0.0)
            scores.append(score_case(case, retrieved, top_score=top_score))
        return aggregate(scores)
