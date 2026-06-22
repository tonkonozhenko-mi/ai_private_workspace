"""Build (or rebuild) the deterministic project handbook and store it as the
singleton ``handbook`` memory item."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.domain.project_handbook import build_handbook
from app.core.domain.project_memory import MemoryItem, MemoryKind, MemorySource
from app.core.ports.project_graph_repository import ProjectGraphRepositoryPort
from app.core.ports.project_memory_repository import ProjectMemoryRepositoryPort


@dataclass(frozen=True)
class BuildHandbookInput:
    workspace_id: str


class BuildHandbookGraphRequiredError(ValueError):
    pass


class BuildProjectHandbookUseCase:
    def __init__(
        self,
        project_graph_repository: ProjectGraphRepositoryPort,
        memory_repository: ProjectMemoryRepositoryPort,
    ) -> None:
        self.project_graph_repository = project_graph_repository
        self.memory_repository = memory_repository

    def execute(self, request: BuildHandbookInput) -> str:
        graph = self.project_graph_repository.get_latest_graph(request.workspace_id)
        if graph is None:
            raise BuildHandbookGraphRequiredError("Build the project map first")
        text = build_handbook(graph)
        # Singleton: replace any previous handbook.
        self.memory_repository.delete_kind(request.workspace_id, MemoryKind.HANDBOOK)
        self.memory_repository.add(
            MemoryItem(
                id=str(uuid.uuid4()),
                workspace_id=request.workspace_id,
                kind=MemoryKind.HANDBOOK,
                text=text,
                source=MemorySource.AUTO,
                created_at=datetime.now(timezone.utc).isoformat(),
                pinned=True,
            )
        )
        return text
