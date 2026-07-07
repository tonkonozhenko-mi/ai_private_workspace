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
    # Abstention threshold calibrated to this embedding model's own score scale
    # (noise floor of random chunk pairs). None → fall back to the hardcoded default.
    relevance_floor: float | None = None
    # Empirical chit-chat ceiling: the highest similarity neutral probe queries reach
    # against this corpus, measured on the query↔chunk scale. A second calibration
    # anchor that keeps the abstention bar from sitting above off-topic scores on a
    # small, homogeneous index. None → the floor alone decides the threshold.
    relevance_probe_ceiling: float | None = None
