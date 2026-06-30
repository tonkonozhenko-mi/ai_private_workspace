"""Add / list / delete / pin project memory items."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.domain.project_memory import MemoryItem, MemoryKind, MemorySource
from app.core.ports.project_memory_repository import ProjectMemoryRepositoryPort

_ALLOWED_KINDS = {
    MemoryKind.NOTE,
    MemoryKind.DECISION,
    MemoryKind.CORRECTION,
    MemoryKind.FACT,
    MemoryKind.QA,
    MemoryKind.ARCHITECTURE_DECISION,
    MemoryKind.INCIDENT_SOLUTION,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AddMemoryInput:
    workspace_id: str
    text: str
    kind: str = MemoryKind.NOTE
    source: str = MemorySource.USER
    pinned: bool = False


class AddMemoryValidationError(ValueError):
    pass


class AddMemoryUseCase:
    def __init__(self, repository: ProjectMemoryRepositoryPort) -> None:
        self.repository = repository

    def execute(self, request: AddMemoryInput) -> MemoryItem:
        text = request.text.strip()
        if not text:
            raise AddMemoryValidationError("Memory text cannot be empty")
        if len(text) > 2000:
            text = text[:2000]
        kind = request.kind if request.kind in _ALLOWED_KINDS else MemoryKind.NOTE
        item = MemoryItem(
            id=str(uuid.uuid4()),
            workspace_id=request.workspace_id,
            kind=kind,
            text=text,
            source=request.source,
            created_at=_now_iso(),
            pinned=request.pinned,
        )
        return self.repository.add(item)


class ListMemoryUseCase:
    def __init__(self, repository: ProjectMemoryRepositoryPort) -> None:
        self.repository = repository

    def execute(self, workspace_id: str) -> list[MemoryItem]:
        return self.repository.list(workspace_id)


class DeleteMemoryUseCase:
    def __init__(self, repository: ProjectMemoryRepositoryPort) -> None:
        self.repository = repository

    def execute(self, workspace_id: str, item_id: str) -> None:
        self.repository.delete(workspace_id, item_id)


class SetMemoryPinnedUseCase:
    def __init__(self, repository: ProjectMemoryRepositoryPort) -> None:
        self.repository = repository

    def execute(self, workspace_id: str, item_id: str, pinned: bool) -> None:
        self.repository.set_pinned(workspace_id, item_id, pinned)
