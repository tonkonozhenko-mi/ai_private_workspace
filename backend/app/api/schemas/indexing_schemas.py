from pydantic import BaseModel

from app.core.domain.indexing import (
    ContextSearchResult,
    IncrementalIndexResult,
    IndexChangePreview,
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


class WorkspaceIncrementalIndexResponse(BaseModel):
    workspace_id: str
    reindexed_files: int
    removed_files: int
    unchanged_files: int
    chunks_indexed: int
    indexed_files_count: int
    chunks_count: int
    documents: list[IndexedDocumentSummaryResponse]


class WorkspaceIndexChangePreviewResponse(BaseModel):
    workspace_id: str
    has_index: bool
    changed_files: int
    new_files: int
    removed_files: int
    unchanged_files: int
    pending: int


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


def to_workspace_incremental_index_response(
    result: IncrementalIndexResult,
) -> WorkspaceIncrementalIndexResponse:
    return WorkspaceIncrementalIndexResponse(
        workspace_id=result.workspace_id,
        reindexed_files=result.reindexed_files,
        removed_files=result.removed_files,
        unchanged_files=result.unchanged_files,
        chunks_indexed=result.chunks_indexed,
        indexed_files_count=result.indexed_files_count,
        chunks_count=result.chunks_count,
        documents=[to_indexed_document_summary_response(document) for document in result.documents],
    )


def to_workspace_index_change_preview_response(
    result: IndexChangePreview,
) -> WorkspaceIndexChangePreviewResponse:
    return WorkspaceIndexChangePreviewResponse(
        workspace_id=result.workspace_id,
        has_index=result.has_index,
        changed_files=result.changed_files,
        new_files=result.new_files,
        removed_files=result.removed_files,
        unchanged_files=result.unchanged_files,
        pending=result.pending,
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
