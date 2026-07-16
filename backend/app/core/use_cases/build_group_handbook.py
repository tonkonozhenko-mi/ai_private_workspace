"""(Re)generate and store a group's deterministic handbook, and tell whether the
stored one has fallen behind its members.

The handbook is derived from the aggregated overview and stored as the group's
singleton handbook memory (keyed by the group id, exactly like a workspace's
handbook is keyed by its workspace id). Ask then picks it up as group context.

It also records what it read: each member's index timestamp at the moment it was
written, in its own provenance field. That snapshot is the only state a group
keeps about its members — everything else about a member (its changes, its scan
history, its index) belongs to that member's workspace and is read from there.
Whether the handbook is behind is then arithmetic on marks, and it is only ever a
question we answer, never an action we take: rebuilding costs a person's time on
a model, so a person decides.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.domain.group_handbook import build_group_handbook
from app.core.domain.group_handbook_provenance import (
    format_index_snapshot,
    handbook_lag,
    has_index_snapshot,
    parse_index_snapshot,
)
from app.core.domain.project_memory import MemoryItem, MemoryKind, MemorySource
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.project_group_repository import ProjectGroupRepositoryPort
from app.core.ports.project_memory_repository import ProjectMemoryRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.build_group_overview import (
    BuildGroupOverviewNotFoundError,
    BuildGroupOverviewUseCase,
)


class BuildGroupHandbookNotFoundError(ValueError):
    pass


class BuildGroupHandbookUseCase:
    def __init__(
        self,
        overview_use_case: BuildGroupOverviewUseCase,
        memory_repository: ProjectMemoryRepositoryPort,
        group_repository: ProjectGroupRepositoryPort | None = None,
        index_status_repository: IndexStatusRepositoryPort | None = None,
    ) -> None:
        self.overview_use_case = overview_use_case
        self.memory_repository = memory_repository
        # Optional: without them the handbook is built exactly as before, simply
        # without a provenance line — and then it never claims to be current.
        self.group_repository = group_repository
        self.index_status_repository = index_status_repository

    def execute(self, group_id: str) -> str:
        try:
            overview = self.overview_use_case.execute(group_id)
        except BuildGroupOverviewNotFoundError as exc:
            raise BuildGroupHandbookNotFoundError(str(exc)) from exc

        text = build_group_handbook(overview)
        # Singleton: replace any previous handbook for this group.
        self.memory_repository.delete_kind(group_id, MemoryKind.HANDBOOK)
        self.memory_repository.add(
            MemoryItem(
                id=str(uuid.uuid4()),
                workspace_id=group_id,
                kind=MemoryKind.HANDBOOK,
                text=text,
                source=MemorySource.AUTO,
                created_at=datetime.now(timezone.utc).isoformat(),
                pinned=True,
                grounding=format_index_snapshot(
                    current_index_marks(
                        self.group_repository, self.index_status_repository, group_id
                    )
                )
                or None,
            )
        )
        return text


def current_index_marks(
    group_repository: ProjectGroupRepositoryPort | None,
    index_status_repository: IndexStatusRepositoryPort | None,
    group_id: str,
) -> dict[str, str | None]:
    """Each member's index timestamp, right now. Two repository reads per member
    and no arithmetic of its own — the marks belong to the members."""
    if group_repository is None or index_status_repository is None:
        return {}
    group = group_repository.get(group_id)
    if group is None:
        return {}
    marks: dict[str, str | None] = {}
    for workspace_id in group.workspace_ids:
        status = index_status_repository.get(workspace_id)
        marks[workspace_id] = status.last_indexed_at if status is not None else None
    return marks


@dataclass(frozen=True)
class GroupHandbookFreshness:
    has_handbook: bool
    # Names, because this is read out to a person: "Built before the latest
    # changes in Wiki". Empty when the handbook is current, or when there is no
    # handbook to be current — absence of a badge means nothing to worry about.
    stale_members: tuple[str, ...] = ()


class GroupHandbookFreshnessUseCase:
    """Is the stored handbook older than what its members now know?

    Pure arithmetic on timestamps: no walk of any folder, no model, no writes.
    """

    def __init__(
        self,
        memory_repository: ProjectMemoryRepositoryPort,
        group_repository: ProjectGroupRepositoryPort,
        workspace_repository: WorkspaceRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
    ) -> None:
        self.memory_repository = memory_repository
        self.group_repository = group_repository
        self.workspace_repository = workspace_repository
        self.index_status_repository = index_status_repository

    def execute(self, group_id: str) -> GroupHandbookFreshness:
        handbook = next(
            (i for i in self.memory_repository.list(group_id) if i.kind == MemoryKind.HANDBOOK),
            None,
        )
        if handbook is None:
            return GroupHandbookFreshness(has_handbook=False)
        if not has_index_snapshot(handbook.grounding):
            return GroupHandbookFreshness(has_handbook=True)
        current = current_index_marks(self.group_repository, self.index_status_repository, group_id)
        behind = handbook_lag(parse_index_snapshot(handbook.grounding), current)
        return GroupHandbookFreshness(
            has_handbook=True,
            stale_members=tuple(self._name(workspace_id) for workspace_id in behind),
        )

    def _name(self, workspace_id: str) -> str:
        workspace = self.workspace_repository.get(workspace_id)
        return workspace.name if workspace is not None else workspace_id
