"""In-memory Project Group store (tests and the memory backend)."""

from app.core.domain.project_group import ProjectGroup


class InMemoryProjectGroupRepository:
    def __init__(self) -> None:
        self._groups: dict[str, ProjectGroup] = {}

    def add(self, group: ProjectGroup) -> ProjectGroup:
        self._groups[group.id] = group
        return group

    def get(self, group_id: str) -> ProjectGroup | None:
        return self._groups.get(group_id)

    def list(self) -> list[ProjectGroup]:
        return sorted(
            self._groups.values(),
            key=lambda g: (g.created_at, g.id),
            reverse=True,
        )

    def update(self, group: ProjectGroup) -> ProjectGroup:
        self._groups[group.id] = group
        return group

    def delete(self, group_id: str) -> None:
        self._groups.pop(group_id, None)
