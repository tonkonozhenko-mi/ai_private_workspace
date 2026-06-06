from dataclasses import dataclass

from app.core.domain.indexing import ContextSearchResult
from app.core.domain.rag import RagSource, WorkspaceQuestionAnswer
from app.core.domain.rag_prompt import build_workspace_question_prompt
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.llm_provider import LLMProviderPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


WORKSPACE_NOT_INDEXED_ANSWER = (
    "This workspace has not been indexed yet. Run workspace indexing first."
)
WORKSPACE_NOT_INDEXED_MESSAGE = "No workspace index metadata was found."
INDEX_METADATA_WITHOUT_CHUNKS_ANSWER = (
    "No context chunks were found in the active vector store."
)
INDEX_METADATA_WITHOUT_CHUNKS_MESSAGE = (
    "Index metadata exists, but the active vector store returned no chunks. "
    "If VECTOR_STORE=memory, reindex after API restart. If VECTOR_STORE=qdrant, "
    "verify VECTOR_STORE, EMBEDDING_PROVIDER, model, and collection settings."
)
NO_RELEVANT_CONTEXT_ANSWER = "No relevant indexed context was found for this question."
NO_RELEVANT_CONTEXT_MESSAGE = (
    "The active vector store returned no context chunks for this question."
)


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
        index_status_repository: IndexStatusRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.llm_provider = llm_provider
        self.index_status_repository = index_status_repository

    def execute(
        self,
        request: AskWorkspaceQuestionInput,
    ) -> WorkspaceQuestionAnswer:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise AskWorkspaceQuestionNotFoundError("Workspace not found")

        index_status = self.index_status_repository.get(request.workspace_id)
        if index_status is None or index_status.status == "not_indexed":
            return self._diagnostic_answer(
                request=request,
                answer=WORKSPACE_NOT_INDEXED_ANSWER,
                diagnostic_code="workspace_not_indexed",
                diagnostic_message=WORKSPACE_NOT_INDEXED_MESSAGE,
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
                return self._diagnostic_answer(
                    request=request,
                    answer=INDEX_METADATA_WITHOUT_CHUNKS_ANSWER,
                    diagnostic_code="index_metadata_exists_but_no_chunks_found",
                    diagnostic_message=INDEX_METADATA_WITHOUT_CHUNKS_MESSAGE,
                )
            return self._diagnostic_answer(
                request=request,
                answer=NO_RELEVANT_CONTEXT_ANSWER,
                diagnostic_code="no_relevant_context_found",
                diagnostic_message=NO_RELEVANT_CONTEXT_MESSAGE,
            )

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
            diagnostic_code=None,
            diagnostic_message=None,
        )

    def _diagnostic_answer(
        self,
        request: AskWorkspaceQuestionInput,
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
            llm_provider=self.llm_provider.provider_name,
            llm_model=self.llm_provider.model_name,
            diagnostic_code=diagnostic_code,
            diagnostic_message=diagnostic_message,
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
