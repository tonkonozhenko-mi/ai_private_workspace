"""Compaction: near-duplicate detection + review-first merge. Pure + in-memory."""

from app.adapters.memory.in_memory_project_memory_repository import (
    InMemoryProjectMemoryRepository,
)
from app.core.domain.project_memory import (
    MemoryItem,
    MemoryKind,
    MemoryStatus,
    find_duplicate_groups,
)
from app.core.use_cases.manage_project_memory import (
    FindMemoryDuplicatesUseCase,
    MergeMemoryDuplicatesUseCase,
)


def _item(id_, text, *, kind=MemoryKind.NOTE, status=MemoryStatus.ACTIVE):
    return MemoryItem(
        id=id_,
        workspace_id="w",
        kind=kind,
        text=text,
        source="user",
        created_at="2026-06-01T00:00:00+00:00",
        status=status,
    )


def test_near_duplicates_grouped():
    items = [
        _item("a", "production database runs on postgres in eu-central"),
        _item("b", "production database runs on postgres in eu central"),
        _item("c", "the billing service uses stripe for payments"),
    ]
    groups = find_duplicate_groups(items)
    assert len(groups) == 1
    assert set(groups[0]) == {"a", "b"}  # c is unrelated


def test_different_kinds_not_merged():
    items = [
        _item("a", "production is called prd", kind=MemoryKind.NOTE),
        _item("b", "production is called prd", kind=MemoryKind.CORRECTION),
    ]
    assert find_duplicate_groups(items) == []


def test_obsolete_and_guardrails_ignored():
    items = [
        _item("a", "deploy pipeline runs nightly", status=MemoryStatus.OBSOLETE),
        _item("b", "deploy pipeline runs nightly"),
        _item("g", "deploy pipeline runs nightly", kind=MemoryKind.GUARDRAIL),
    ]
    # Only one active non-guardrail note remains → no group.
    assert find_duplicate_groups(items) == []


def test_transitive_clustering():
    items = [
        _item("a", "the cache uses redis for sessions and tokens"),
        _item("b", "the cache uses redis for sessions and tokens now"),
        _item("c", "the cache uses redis for sessions and tokens today"),
    ]
    groups = find_duplicate_groups(items)
    assert len(groups) == 1
    assert set(groups[0]) == {"a", "b", "c"}


def test_merge_retires_dropped_keeps_one():
    repo = InMemoryProjectMemoryRepository()
    for i in ("a", "b", "c"):
        repo.add(_item(i, "production database runs on postgres in eu central"))
    groups = FindMemoryDuplicatesUseCase(repo).execute("w")
    assert len(groups) == 1
    ids = [i.id for i in groups[0]]
    keep, drop = ids[0], ids[1:]
    n = MergeMemoryDuplicatesUseCase(repo).execute("w", keep, drop)
    assert n == len(drop)
    by_id = {i.id: i for i in repo.list("w")}
    assert by_id[keep].status == MemoryStatus.ACTIVE
    for d in drop:
        assert by_id[d].status == MemoryStatus.OBSOLETE


def test_no_duplicates_returns_empty():
    repo = InMemoryProjectMemoryRepository()
    repo.add(_item("a", "one unique note about billing"))
    repo.add(_item("b", "another totally different note on caching"))
    assert FindMemoryDuplicatesUseCase(repo).execute("w") == []
