"""Memory lifecycle: obsolete exclusion + confidence/recency-weighted ranking."""

from datetime import datetime, timedelta, timezone

from app.adapters.memory.in_memory_project_memory_repository import (
    InMemoryProjectMemoryRepository,
)
from app.adapters.memory.sqlite_project_memory_repository import (
    SQLiteProjectMemoryRepository,
)
from app.core.domain.project_memory import (
    MemoryItem,
    MemoryStatus,
    select_relevant_memory,
)
from app.core.use_cases.manage_project_memory import (
    AddMemoryInput,
    AddMemoryUseCase,
    SetMemoryStatusUseCase,
)

NOW = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _item(id_, text, *, days_old=0, confidence=1.0, status="active", pinned=False):
    created = (NOW - timedelta(days=days_old)).isoformat()
    return MemoryItem(
        id=id_,
        workspace_id="w1",
        kind="note",
        text=text,
        source="user",
        created_at=created,
        pinned=pinned,
        confidence=confidence,
        status=status,
    )


def test_obsolete_memory_is_never_selected():
    items = [
        _item("a", "prod database is postgres", status=MemoryStatus.OBSOLETE),
        _item("b", "staging database is mysql"),
    ]
    picked = select_relevant_memory(items, "what database", now=NOW)
    ids = [i.id for i in picked]
    assert "a" not in ids  # obsolete excluded even though it matches
    assert "b" in ids


def test_confident_recent_outranks_old_uncertain():
    items = [
        _item("old", "deploy uses kubernetes", days_old=400, confidence=0.3),
        _item("new", "deploy uses kubernetes", days_old=1, confidence=1.0),
    ]
    picked = select_relevant_memory(items, "how do we deploy kubernetes", limit=1, now=NOW)
    assert picked[0].id == "new"


def test_pinned_bypasses_decay_and_ranks_first():
    items = [
        _item("pin", "unrelated pinned rule", days_old=900, pinned=True),
        _item("match", "deploy kubernetes", days_old=1),
    ]
    picked = select_relevant_memory(items, "kubernetes", now=NOW)
    assert picked[0].id == "pin"  # pinned always first


def test_sqlite_persists_lifecycle_fields(tmp_path):
    repo = SQLiteProjectMemoryRepository(tmp_path / "mem.db")
    repo.add(_item("x", "a fact", confidence=0.5))
    repo.set_status("w1", "x", MemoryStatus.OBSOLETE)
    again = SQLiteProjectMemoryRepository(tmp_path / "mem.db")
    item = again.list("w1")[0]
    assert item.confidence == 0.5
    assert item.status == MemoryStatus.OBSOLETE
    assert item.updated_at is not None


def test_use_case_add_clamps_confidence_and_set_status():
    repo = InMemoryProjectMemoryRepository()
    item = AddMemoryUseCase(repo).execute(
        AddMemoryInput(workspace_id="w1", text="note", confidence=5.0)
    )
    assert item.confidence == 1.0  # clamped
    SetMemoryStatusUseCase(repo).execute("w1", item.id, MemoryStatus.OBSOLETE)
    assert repo.list("w1")[0].status == MemoryStatus.OBSOLETE
