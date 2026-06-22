"""Create and edit project groups.

Membership operations are delegated to the pure helpers in the domain so this use
case stays a thin coordinator over the repository. Member workspaces are never
created or deleted here — a group only references them.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.domain.project_group import (
    ProjectGroup,
    add_member,
    remove_member,
    rename_group,
    set_members,
)
from app.core.ports.project_group_repository import ProjectGroupRepositoryPort


class ProjectGroupNotFoundError(ValueError):
    pass


class ProjectGroupValidationError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ManageProjectGroupsUseCase:
    def __init__(self, repository: ProjectGroupRepositoryPort) -> None:
        self.repository = repository

    def create(self, name: str, workspace_ids: list[str] | None = None) -> ProjectGroup:
        cleaned = (name or "").strip()
        if not cleaned:
            raise ProjectGroupValidationError("A group needs a name.")
        group = ProjectGroup(
            id=uuid.uuid4().hex,
            name=cleaned,
            workspace_ids=(),
            created_at=_now_iso(),
        )
        group = set_members(group, workspace_ids or [])
        return self.repository.add(group)

    def list(self) -> list[ProjectGroup]:
        return self.repository.list()

    def get(self, group_id: str) -> ProjectGroup:
        group = self.repository.get(group_id)
        if group is None:
            raise ProjectGroupNotFoundError("Group not found")
        return group

    def rename(self, group_id: str, name: str) -> ProjectGroup:
        if not (name or "").strip():
            raise ProjectGroupValidationError("A group needs a name.")
        group = self.get(group_id)
        return self.repository.update(rename_group(group, name))

    def add_member(self, group_id: str, workspace_id: str) -> ProjectGroup:
        group = self.get(group_id)
        return self.repository.update(add_member(group, workspace_id))

    def remove_member(self, group_id: str, workspace_id: str) -> ProjectGroup:
        group = self.get(group_id)
        return self.repository.update(remove_member(group, workspace_id))

    def set_members(self, group_id: str, workspace_ids: list[str]) -> ProjectGroup:
        group = self.get(group_id)
        return self.repository.update(set_members(group, workspace_ids))

    def delete(self, group_id: str) -> None:
        self.repository.delete(group_id)
