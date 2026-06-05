from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    id: str
    workspace_id: str
    source_path: str
    chunk_index: int
    content: str
    token_estimate: int
    metadata: dict[str, str]


@dataclass(frozen=True)
class IndexedDocumentSummary:
    source_path: str
    chunks_count: int


@dataclass(frozen=True)
class WorkspaceIndexResult:
    workspace_id: str
    indexed_files_count: int
    chunks_count: int
    skipped_files_count: int
    documents: list[IndexedDocumentSummary]


@dataclass(frozen=True)
class ContextSearchResult:
    chunk_id: str
    source_path: str
    content: str
    score: float
    metadata: dict[str, str]
