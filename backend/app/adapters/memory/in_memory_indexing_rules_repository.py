from threading import Lock

from app.core.domain.indexing_rules import IndexingRulesProfile


class InMemoryIndexingRulesRepository:
    def __init__(self) -> None:
        self._profiles: dict[str, IndexingRulesProfile] = {}
        self._lock = Lock()

    def get(self, workspace_id: str) -> IndexingRulesProfile | None:
        with self._lock:
            return self._profiles.get(workspace_id)

    def save(self, profile: IndexingRulesProfile) -> IndexingRulesProfile:
        with self._lock:
            self._profiles[profile.workspace_id] = profile
        return profile
