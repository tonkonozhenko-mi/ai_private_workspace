"""Add / list / delete / pin project memory items."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.domain.project_memory import (
    ConfidenceSource,
    MemoryItem,
    MemoryKind,
    MemorySource,
    MemoryStatus,
    contradiction_candidates,
    memories_referencing_paths,
)
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
_ALLOWED_STATUSES = {MemoryStatus.ACTIVE, MemoryStatus.OBSOLETE}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Map who produced a memory onto where its confidence number came from, so the
# provenance is honest without the caller having to spell it out every time.
_SOURCE_TO_CONFIDENCE = {
    MemorySource.USER: ConfidenceSource.USER,
    MemorySource.AGENT: ConfidenceSource.AUTO,
    MemorySource.AUTO: ConfidenceSource.AUTO,
}


@dataclass(frozen=True)
class AddMemoryInput:
    workspace_id: str
    text: str
    kind: str = MemoryKind.NOTE
    source: str = MemorySource.USER
    pinned: bool = False
    confidence: float = 1.0
    # Optional explicit provenance; when left unset it's inferred from ``source``.
    confidence_source: str | None = None
    # Optional id of an earlier note this one replaces; that note is retired
    # (marked obsolete) so the correction cleanly supersedes what it corrects.
    supersedes: str | None = None


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
        confidence = min(1.0, max(0.0, request.confidence))
        confidence_source = request.confidence_source or _SOURCE_TO_CONFIDENCE.get(
            request.source, ConfidenceSource.DEFAULT
        )
        item = MemoryItem(
            id=str(uuid.uuid4()),
            workspace_id=request.workspace_id,
            kind=kind,
            text=text,
            source=request.source,
            created_at=_now_iso(),
            pinned=request.pinned,
            confidence=confidence,
            confidence_source=confidence_source,
            status=MemoryStatus.ACTIVE,
            supersedes_id=request.supersedes or None,
        )
        saved = self.repository.add(item)
        # Retire the note this one replaces: obsolete items stay for history but
        # are never recalled, so the project keeps one current answer, not two
        # conflicting ones. Best-effort — a bad id must not fail the add.
        if request.supersedes:
            try:
                self.repository.set_status(
                    request.workspace_id, request.supersedes, MemoryStatus.OBSOLETE
                )
            except Exception:  # noqa: BLE001 - superseding is best-effort
                pass
        return saved


class FindContradictionsUseCase:
    """Given a proposed note, return the existing active notes it likely
    contradicts or replaces, so the UI can offer to supersede them before the
    note is saved. Deterministic (token overlap + replacement markers); no LLM."""

    def __init__(self, repository: ProjectMemoryRepositoryPort) -> None:
        self.repository = repository

    def execute(
        self, workspace_id: str, text: str, kind: str = MemoryKind.NOTE
    ) -> list[MemoryItem]:
        text = (text or "").strip()
        if not text:
            return []
        items = self.repository.list(workspace_id)
        ids = set(
            contradiction_candidates(
                text, items, is_correction=(kind == MemoryKind.CORRECTION)
            )
        )
        return [i for i in items if i.id in ids]


class SetMemoryStatusUseCase:
    """Mark a memory item active or obsolete. Obsolete items stay in the store
    (visible in the UI) but are never injected into prompts."""

    def __init__(self, repository: ProjectMemoryRepositoryPort) -> None:
        self.repository = repository

    def execute(self, workspace_id: str, item_id: str, status: str) -> None:
        if status not in _ALLOWED_STATUSES:
            raise AddMemoryValidationError(f"Unknown memory status: {status}")
        self.repository.set_status(workspace_id, item_id, status)


class FlagStaleMemoriesUseCase:
    """Flag active memories that reference a file which just changed, so the user
    can confirm they are still true. Stale items are still recalled (they may be
    correct) but down-weighted in ranking. Best-effort: returns how many it flagged."""

    def __init__(self, repository: ProjectMemoryRepositoryPort) -> None:
        self.repository = repository

    def execute(self, workspace_id: str, changed_paths: list[str]) -> int:
        if not changed_paths:
            return 0
        items = self.repository.list(workspace_id)
        ids = memories_referencing_paths(items, changed_paths)
        for item_id in ids:
            self.repository.set_stale(workspace_id, item_id, True)
        return len(ids)


class SetMemoryStaleUseCase:
    """Set or clear a memory's stale flag. Clearing is the user's "still correct"
    confirmation after a referenced file changed."""

    def __init__(self, repository: ProjectMemoryRepositoryPort) -> None:
        self.repository = repository

    def execute(self, workspace_id: str, item_id: str, stale: bool) -> None:
        self.repository.set_stale(workspace_id, item_id, stale)


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
