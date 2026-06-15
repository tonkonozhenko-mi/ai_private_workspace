from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkspaceStorageBreakdown:
    """Approximate on-disk footprint of a workspace inside the app's databases.

    Sizes are byte estimates derived from the textual content stored per
    workspace (SUM of column lengths), grouped into user-facing categories.
    The project's own files on disk are never counted - only the app's
    internal index, conversation history, scan and notes data.
    """

    workspace_id: str
    total_bytes: int
    categories: dict[str, int] = field(default_factory=dict)
    computed_at: str | None = None
