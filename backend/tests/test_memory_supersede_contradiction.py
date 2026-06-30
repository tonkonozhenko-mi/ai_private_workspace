"""Supersede link (#2/#3) + contradiction detection. Pure + sqlite; no LLM."""

from app.adapters.memory.in_memory_project_memory_repository import (
    InMemoryProjectMemoryRepository,
)
from app.adapters.memory.sqlite_project_memory_repository import (
    SQLiteProjectMemoryRepository,
)
from app.core.domain.project_memory import (
    MemoryItem,
    MemoryKind,
    MemoryStatus,
    contradiction_candidates,
)
from app.core.use_cases.manage_project_memory import (
    AddMemoryInput,
    AddMemoryUseCase,
    FindContradictionsUseCase,
)


def _item(id_, text, kind=MemoryKind.NOTE, status=MemoryStatus.ACTIVE):
    return MemoryItem(
        id=id_,
        workspace_id="w",
        kind=kind,
        text=text,
        source="user",
        created_at="2026-01-01T00:00:00+00:00",
        status=status,
    )


# -- contradiction detection ------------------------------------------------


def test_marker_plus_overlap_flags_candidate():
    items = [_item("a", "the billing service uses stripe")]
    # Marker ("no longer") + ≥2 shared subject tokens (billing, service, stripe).
    ids = contradiction_candidates("the billing service no longer uses stripe", items)
    assert ids == ["a"]


def test_no_marker_means_no_contradiction():
    items = [_item("a", "production is named prod")]
    # A plain restatement with no negation/replacement marker isn't a contradiction.
    assert contradiction_candidates("production has a database", items) == []


def test_correction_kind_needs_no_marker():
    items = [_item("a", "production is named prod")]
    ids = contradiction_candidates("production prod", items, is_correction=True)
    assert ids == ["a"]


def test_low_overlap_is_ignored():
    items = [_item("a", "the billing service uses stripe")]
    # Marker present but nothing in common → not a contradiction.
    assert contradiction_candidates("the cache is no longer redis", items) == []


def test_obsolete_and_handbook_excluded():
    items = [
        _item("old", "production is named prod", status=MemoryStatus.OBSOLETE),
        _item("hb", "production is named prod", kind=MemoryKind.HANDBOOK),
    ]
    assert contradiction_candidates("production is actually prd", items) == []


# -- supersede flow ---------------------------------------------------------


def test_supersede_obsoletes_target_and_links():
    repo = InMemoryProjectMemoryRepository()
    uc = AddMemoryUseCase(repo)
    old = uc.execute(AddMemoryInput(workspace_id="w", text="prod is named prod"))
    new = uc.execute(
        AddMemoryInput(
            workspace_id="w",
            text="prod is actually called prd",
            kind=MemoryKind.CORRECTION,
            supersedes=old.id,
        )
    )
    assert new.supersedes_id == old.id
    by_id = {i.id: i for i in repo.list("w")}
    assert by_id[old.id].status == MemoryStatus.OBSOLETE  # retired
    assert by_id[new.id].status == MemoryStatus.ACTIVE


def test_supersede_bad_id_does_not_fail_add():
    repo = InMemoryProjectMemoryRepository()
    item = AddMemoryUseCase(repo).execute(
        AddMemoryInput(workspace_id="w", text="note", supersedes="does-not-exist")
    )
    assert item.supersedes_id == "does-not-exist"
    assert len(repo.list("w")) == 1


def test_find_contradictions_use_case_returns_items():
    repo = InMemoryProjectMemoryRepository()
    uc = AddMemoryUseCase(repo)
    uc.execute(AddMemoryInput(workspace_id="w", text="production is named prod"))
    found = FindContradictionsUseCase(repo).execute(
        "w", "production is actually called prd", MemoryKind.CORRECTION
    )
    assert len(found) == 1
    assert "named prod" in found[0].text


def test_sqlite_persists_supersedes_id(tmp_path):
    repo = SQLiteProjectMemoryRepository(tmp_path / "mem.db")
    uc = AddMemoryUseCase(repo)
    old = uc.execute(AddMemoryInput(workspace_id="w", text="old value here"))
    uc.execute(
        AddMemoryInput(workspace_id="w", text="new replacement value", supersedes=old.id)
    )
    by_id = {i.id: i for i in repo.list("w")}
    new = next(i for i in by_id.values() if i.supersedes_id)
    assert new.supersedes_id == old.id
    assert by_id[old.id].status == MemoryStatus.OBSOLETE
