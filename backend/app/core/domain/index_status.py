from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceIndexStatus:
    workspace_id: str
    status: str
    indexed_files_count: int
    chunks_count: int
    skipped_files_count: int
    last_indexed_at: str | None
    last_error: str | None
    # The embedding model that built this index. Lets a later switch to a different
    # search model be detected as stale, so a reindex is prompted only when needed.
    embedding_model: str | None = None
