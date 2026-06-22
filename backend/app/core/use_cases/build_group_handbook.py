"""(Re)generate and store a group's deterministic handbook.

The handbook is derived from the aggregated overview and stored as the group's
singleton handbook memory (keyed by the group id, exactly like a workspace's
handbook is keyed by its workspace id). Ask then picks it up as group context.
"""

import uuid
from datetime import datetime, timezone

from app.core.domain.group_handbook import build_group_handbook
from app.core.domain.project_memory import MemoryItem, MemoryKind, MemorySource
from app.core.ports.project_memory_repository import ProjectMemoryRepositoryPort
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
    ) -> None:
        self.overview_use_case = overview_use_case
        self.memory_repository = memory_repository

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
            )
        )
        return text
