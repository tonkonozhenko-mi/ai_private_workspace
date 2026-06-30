"""Batch: explicit context budget (#7), handbook tiering (#5), confidence
provenance (#6). Pure + sqlite; no LLM, no network."""

from app.adapters.memory.in_memory_project_memory_repository import (
    InMemoryProjectMemoryRepository,
)
from app.adapters.memory.sqlite_project_memory_repository import (
    SQLiteProjectMemoryRepository,
)
from app.core.domain.project_memory import (
    ConfidenceSource,
    MemoryItem,
    MemoryKind,
    MemorySource,
    confidence_explanation,
)
from app.core.use_cases.compose_project_context import (
    ComposeProjectContextUseCase,
    ContextBudget,
    _handbook_block,
    _trim,
)
from app.core.use_cases.manage_project_memory import AddMemoryInput, AddMemoryUseCase


class _NoGraph:
    def get_latest_graph(self, workspace_id):
        return None


# -- #7 budget --------------------------------------------------------------


def test_trim_adds_ellipsis_only_when_over_cap():
    assert _trim("short", 100) == "short"
    out = _trim("x" * 200, 50)
    assert out.endswith("…") and len(out) <= 54


def test_total_budget_caps_combined_context():
    repo = InMemoryProjectMemoryRepository()
    # A pile of long notes that would blow the window if unbounded.
    for i in range(20):
        repo.add(
            MemoryItem(
                id=f"m{i}",
                workspace_id="w",
                kind=MemoryKind.NOTE,
                text=f"deploy pipeline note {i} " + ("detail " * 40),
                source="user",
                created_at="2026-01-01T00:00:00+00:00",
            )
        )
    uc = ComposeProjectContextUseCase(repo, _NoGraph(), budget=ContextBudget(total=800))
    text = uc.compose("w", "deploy pipeline")
    assert len(text) <= 804  # total + " …"


# -- #5 handbook tiering ----------------------------------------------------


def test_handbook_small_when_query_unrelated():
    budget = ContextBudget(handbook_small=60, handbook_full=400)
    handbook = "First paragraph about services.\n\n" + ("Deep infra detail. " * 40)
    block = _handbook_block(handbook, "totally unrelated banana query", budget)
    body = block.split("\n", 1)[1]
    assert len(body) <= 64  # trimmed to the small cap


def test_handbook_full_when_query_overlaps():
    budget = ContextBudget(handbook_small=60, handbook_full=2000)
    handbook = "The project deploys services to staging and production via pipeline."
    block = _handbook_block(handbook, "how do services deploy to production pipeline", budget)
    # Enough overlap → the full handbook text is kept (not cut to the small cap).
    assert "staging and production" in block


def test_handbook_empty_returns_blank():
    assert _handbook_block("   ", "anything", ContextBudget()) == ""


# -- #6 confidence provenance ----------------------------------------------


def test_add_infers_confidence_source_from_origin():
    repo = InMemoryProjectMemoryRepository()
    uc = AddMemoryUseCase(repo)
    user_item = uc.execute(AddMemoryInput(workspace_id="w", text="prod is prd"))
    assert user_item.confidence_source == ConfidenceSource.USER
    auto_item = uc.execute(
        AddMemoryInput(workspace_id="w", text="auto note", source=MemorySource.AUTO)
    )
    assert auto_item.confidence_source == ConfidenceSource.AUTO


def test_explicit_confidence_source_wins():
    repo = InMemoryProjectMemoryRepository()
    uc = AddMemoryUseCase(repo)
    item = uc.execute(
        AddMemoryInput(
            workspace_id="w", text="tuned", confidence_source=ConfidenceSource.FEEDBACK
        )
    )
    assert item.confidence_source == ConfidenceSource.FEEDBACK


def test_explanation_is_human_readable():
    assert confidence_explanation(ConfidenceSource.USER) == "you recorded this"
    assert confidence_explanation("nonsense") == "default confidence"


def test_sqlite_persists_confidence_source(tmp_path):
    repo = SQLiteProjectMemoryRepository(tmp_path / "mem.db")
    AddMemoryUseCase(repo).execute(
        AddMemoryInput(workspace_id="w", text="note", source=MemorySource.USER)
    )
    (loaded,) = repo.list("w")
    assert loaded.confidence_source == ConfidenceSource.USER


def test_sqlite_legacy_rows_default_source(tmp_path):
    # A DB created before the column existed: insert a bare row, then reopen.
    import sqlite3

    db = tmp_path / "legacy.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE project_memory (id TEXT PRIMARY KEY, workspace_id TEXT, kind TEXT, "
        "text TEXT, source TEXT, created_at TEXT, pinned INTEGER DEFAULT 0)"
    )
    con.execute(
        "INSERT INTO project_memory VALUES ('x','w','note','old','user','2025-01-01T00:00:00',0)"
    )
    con.commit()
    con.close()
    repo = SQLiteProjectMemoryRepository(db)  # migration adds the column
    (loaded,) = repo.list("w")
    assert loaded.confidence_source == "default"
