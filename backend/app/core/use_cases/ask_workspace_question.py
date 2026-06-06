from dataclasses import dataclass

from app.core.domain.indexing import ContextSearchResult
from app.core.domain.rag import RagSource, WorkspaceQuestionAnswer
from app.core.domain.rag_prompt import build_workspace_question_prompt
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.llm_provider import LLMProviderPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


NO_CONTEXT_ANSWER = "No indexed context was found for this workspace."


@dataclass(frozen=True)
class AskWorkspaceQuestionInput:
    workspace_id: str
    question: str
    limit: int = 5


class AskWorkspaceQuestionNotFoundError(ValueError):
    pass


class AskWorkspaceQuestionUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        embedding_provider: EmbeddingProviderPort,
        vector_store: VectorStorePort,
        llm_provider: LLMProviderPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.llm_provider = llm_provider

    def execute(
        self,
        request: AskWorkspaceQuestionInput,
    ) -> WorkspaceQuestionAnswer:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise AskWorkspaceQuestionNotFoundError("Workspace not found")

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
            answer = NO_CONTEXT_ANSWER
        else:
            prompt = build_workspace_question_prompt(
                question=request.question,
                context_results=context_results,
            )
            answer = self.llm_provider.generate(prompt)

        return WorkspaceQuestionAnswer(
            workspace_id=request.workspace_id,
            question=request.question,
            answer=answer,
            sources=sources,
            used_context_chunks=len(context_results),
            llm_provider=self.llm_provider.provider_name,
            llm_model=self.llm_provider.model_name,
        )

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
