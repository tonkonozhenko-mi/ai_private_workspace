from app.core.domain.workspace_storage import WorkspaceStorageBreakdown


_CATEGORY_KEYS = ("index", "conversations", "notes", "scan", "other")


class InMemoryWorkspaceStorageGateway:
    """No-op storage gateway for the in-memory backend used in tests.

    Storage accounting only makes sense against the SQLite files, so this
    variant simply reports an empty breakdown and ignores deletes.
    """

    def get_or_compute(self, workspace_id: str) -> WorkspaceStorageBreakdown:
        return self._empty(workspace_id)

    def get_cached(self, workspace_id: str) -> WorkspaceStorageBreakdown | None:
        return self._empty(workspace_id)

    def recompute(self, workspace_id: str) -> WorkspaceStorageBreakdown:
        return self._empty(workspace_id)

    def delete_workspace_data(self, workspace_id: str) -> None:
        return None

    def invalidate(self, workspace_id: str) -> None:
        return None

    @staticmethod
    def _empty(workspace_id: str) -> WorkspaceStorageBreakdown:
        return WorkspaceStorageBreakdown(
            workspace_id=workspace_id,
            total_bytes=0,
            categories={key: 0 for key in _CATEGORY_KEYS},
            computed_at=None,
        )
