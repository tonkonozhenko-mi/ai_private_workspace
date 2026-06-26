import hashlib
from dataclasses import dataclass


def content_hash(text: str) -> str:
    """Stable content fingerprint for a file, used to tell whether it changed
    since it was last indexed (incremental re-index). Independent of mtime."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


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
class IncrementalIndexResult:
    """Outcome of an incremental (changed-files-only) re-index."""

    workspace_id: str
    reindexed_files: int
    removed_files: int
    unchanged_files: int
    chunks_indexed: int
    indexed_files_count: int  # total in the index after the update
    chunks_count: int  # total in the index after the update
    documents: list[IndexedDocumentSummary]  # the files that were (re)indexed


@dataclass(frozen=True)
class ContextSearchResult:
    chunk_id: str
    source_path: str
    content: str
    score: float
    metadata: dict[str, str]
