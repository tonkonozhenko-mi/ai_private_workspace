"""Auto-stale: flag memories referencing a changed file; down-weight, not exclude."""

from types import SimpleNamespace

from app.adapters.memory.in_memory_project_memory_repository import (
    InMemoryProjectMemoryRepository,
)
from app.adapters.memory.sqlite_project_memory_repository import (
    SQLiteProjectMemoryRepository,
)
from app.core.domain.git_change_brief import GitChangeBrief
from app.core.domain.project_memory import (
    MemoryItem,
    memories_referencing_paths,
    select_relevant_memory,
)
from app.core.use_cases.manage_project_memory import (
    FlagStaleMemoriesUseCase,
    SetMemoryStaleUseCase,
)
from app.core.use_cases.record_git_history import (
    RecordGitHistoryInput,
    RecordGitHistoryUseCase,
)


def _item(id_, text, *, stale=False):
    return MemoryItem(
        id=id_, workspace_id="w1", kind="note", text=text, source="user",
        created_at="2026-06-30T00:00:00+00:00", stale=stale,
    )


def test_matcher_flags_only_memories_referencing_changed_files():
    items = [
        _item("a", "the s3 backend lives in infra/backend.tf"),
        _item("b", "prod is called prd here"),  # no file reference
    ]
    ids = memories_referencing_paths(items, ["infra/backend.tf", "README.md"])
    assert ids == ["a"]


def test_matcher_ignores_bare_words():
    # "backend" alone (no extension) must not match a changed path's word.
    items = [_item("a", "the backend handles auth")]
    assert memories_referencing_paths(items, ["app/backend/main.py"]) == []


def test_stale_item_is_downweighted_not_excluded():
    items = [
        _item("fresh", "deploy uses kubernetes"),
        _item("stale", "deploy uses kubernetes", stale=True),
    ]
    picked = select_relevant_memory(items, "how do we deploy kubernetes")
    ids = [i.id for i in picked]
    assert "stale" in ids  # still recalled
    assert ids[0] == "fresh"  # but ranked below the fresh one


def test_flag_and_clear_use_cases():
    repo = InMemoryProjectMemoryRepository()
    repo.add(_item("a", "see infra/backend.tf for the s3 setup"))
    repo.add(_item("b", "unrelated note"))
    flagged = FlagStaleMemoriesUseCase(repo).execute("w1", ["infra/backend.tf"])
    assert flagged == 1
    assert next(i for i in repo.list("w1") if i.id == "a").stale is True
    SetMemoryStaleUseCase(repo).execute("w1", "a", False)
    assert next(i for i in repo.list("w1") if i.id == "a").stale is False


def test_sqlite_persists_stale(tmp_path):
    repo = SQLiteProjectMemoryRepository(tmp_path / "m.db")
    repo.add(_item("a", "x"))
    repo.set_stale("w1", "a", True)
    again = SQLiteProjectMemoryRepository(tmp_path / "m.db")
    assert again.list("w1")[0].stale is True


def test_record_git_history_flags_stale_memories():
    mem = InMemoryProjectMemoryRepository()
    mem.add(_item("a", "the s3 backend is in infra/backend.tf"))

    class _Watch:
        def get_history_cursor(self, wid):
            return None

        def get_latest_digest(self, wid):
            return None

        def set_history_cursor(self, wid, head):
            pass

        def append_history(self, wid, entry):
            pass

    def _brief(wid, since):
        return GitChangeBrief(
            comparable=True, head="abc", commit_count=1, changed_paths=["infra/backend.tf"]
        )

    uc = RecordGitHistoryUseCase(
        workspace_repository=SimpleNamespace(get=lambda w: SimpleNamespace(id=w)),
        watch_repository=_Watch(),
        git_brief_provider=_brief,
        project_memory_repository=mem,
    )
    uc.execute(RecordGitHistoryInput(workspace_id="w1"))
    assert mem.list("w1")[0].stale is True
