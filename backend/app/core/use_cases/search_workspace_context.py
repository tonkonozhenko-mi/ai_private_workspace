from dataclasses import dataclass

from app.core.domain.indexing import ContextSearchResult
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class SearchWorkspaceContextInput:
    workspace_id: str
    query: str
    limit: int = 5


class SearchWorkspaceContextNotFoundError(ValueError):
    pass


class SearchWorkspaceContextUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        embedding_provider: EmbeddingProviderPort,
        vector_store: VectorStorePort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def execute(
        self,
        request: SearchWorkspaceContextInput,
    ) -> list[ContextSearchResult]:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise SearchWorkspaceContextNotFoundError("Workspace not found")

        if request.limit <= 0 or not request.query.strip():
            return []

        query_embedding = self.embedding_provider.embed_text(request.query)
        return self.vector_store.search(
            workspace_id=request.workspace_id,
            query_embedding=query_embedding,
            limit=request.limit,
            embedding_provider=self.embedding_provider.provider_name,
            embedding_model=self.embedding_provider.model_name,
            embedding_dimension=len(query_embedding),
            query_text=request.query,
        )
