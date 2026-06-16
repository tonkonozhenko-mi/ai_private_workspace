from typing import Protocol

from app.core.domain.project_understanding import ProjectUnderstanding


class ProjectUnderstandingRepositoryPort(Protocol):
    def save(self, understanding: ProjectUnderstanding) -> ProjectUnderstanding:
        """Persist (upsert) the latest understanding for a workspace."""

    def get(self, workspace_id: str) -> ProjectUnderstanding | None:
        """Return the latest cached understanding for a workspace, if present."""
