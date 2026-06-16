from pydantic import BaseModel

from app.core.domain.indexing import (
    ContextSearchResult,
    IndexedDocumentSummary,
    WorkspaceIndexResult,
)


class IndexedDocumentSummaryResponse(BaseModel):
    source_path: str
    chunks_count: int


class WorkspaceIndexResponse(BaseModel):
    workspace_id: str
    indexed_files_count: int
    chunks_count: int
    skipped_files_count: int
    documents: list[IndexedDocumentSummaryResponse]


class ContextSearchResultResponse(BaseModel):
    chunk_id: str
    source_path: str
    content: str
    score: float
    metadata: dict[str, str]


def to_indexed_document_summary_response(
    document: IndexedDocumentSummary,
) -> IndexedDocumentSummaryResponse:
    return IndexedDocumentSummaryResponse(
        source_path=document.source_path,
        chunks_count=document.chunks_count,
    )


def to_workspace_index_response(
    result: WorkspaceIndexResult,
) -> WorkspaceIndexResponse:
    return WorkspaceIndexResponse(
        workspace_id=result.workspace_id,
        indexed_files_count=result.indexed_files_count,
        chunks_count=result.chunks_count,
        skipped_files_count=result.skipped_files_count,
        documents=[to_indexed_document_summary_response(document) for document in result.documents],
    )


def to_context_search_result_response(
    result: ContextSearchResult,
) -> ContextSearchResultResponse:
    return ContextSearchResultResponse(
        chunk_id=result.chunk_id,
        source_path=result.source_path,
        content=result.content,
        score=result.score,
        metadata=result.metadata,
    )
