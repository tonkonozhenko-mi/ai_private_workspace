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
    # Abstention threshold calibrated to the embedding model (noise floor of random
    # chunk pairs); None when the index was too small to sample a trustworthy value.
    relevance_floor: float | None = None


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
    # Recalibrated abstention floor when enough chunks changed to resample; None when
    # too few changed (the caller keeps the previously-calibrated floor).
    relevance_floor: float | None = None


@dataclass(frozen=True)
class IndexChangePreview:
    """A cheap, embed-free count of what an incremental re-index would touch,
    so the UI can show "N files changed since the last index" and decide whether
    to auto-update."""

    workspace_id: str
    has_index: bool
    changed_files: int
    new_files: int
    removed_files: int
    unchanged_files: int

    @property
    def pending(self) -> int:
        return self.changed_files + self.new_files + self.removed_files


@dataclass(frozen=True)
class ContextSearchResult:
    chunk_id: str
    source_path: str
    content: str
    score: float
    metadata: dict[str, str]
