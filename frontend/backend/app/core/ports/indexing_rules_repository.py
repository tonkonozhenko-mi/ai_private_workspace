from typing import Protocol

from app.core.domain.indexing_rules import IndexingRulesProfile


class IndexingRulesRepositoryPort(Protocol):
    def get(self, workspace_id: str) -> IndexingRulesProfile | None:
        """Return saved indexing rules for workspace, if present."""

    def save(self, profile: IndexingRulesProfile) -> IndexingRulesProfile:
        """Persist indexing rules for workspace."""


IndexingRulesRepository = IndexingRulesRepositoryPort
