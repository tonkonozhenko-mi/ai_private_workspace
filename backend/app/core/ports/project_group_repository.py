from typing import Protocol

from app.core.domain.project_group import ProjectGroup


class ProjectGroupRepositoryPort(Protocol):
    def add(self, group: ProjectGroup) -> ProjectGroup:
        """Persist a new group."""

    def get(self, group_id: str) -> ProjectGroup | None:
        """Return a group by id, or None when missing."""

    def list(self) -> list[ProjectGroup]:
        """All groups, newest first."""

    def update(self, group: ProjectGroup) -> ProjectGroup:
        """Persist changes to an existing group."""

    def delete(self, group_id: str) -> None:
        """Remove a group. Member workspaces are never deleted."""
