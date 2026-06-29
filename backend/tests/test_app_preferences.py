"""App preferences store: memory + sqlite adapters and the manage use case."""

from app.adapters.memory.in_memory_app_preferences_repository import (
    InMemoryAppPreferencesRepository,
)
from app.adapters.memory.sqlite_app_preferences_repository import (
    SQLiteAppPreferencesRepository,
)
from app.core.use_cases.manage_app_preferences import (
    AppPreferencesValidationError,
    ManageAppPreferencesUseCase,
)


def test_memory_repo_roundtrip():
    repo = InMemoryAppPreferencesRepository()
    assert repo.get() is None
    repo.save({"theme": "dark", "textSize": "large"})
    assert repo.get() == {"theme": "dark", "textSize": "large"}
    # Returned dict is a copy — mutating it must not change the store.
    got = repo.get()
    got["theme"] = "light"
    assert repo.get()["theme"] == "dark"


def test_sqlite_repo_roundtrip_and_persistence(tmp_path):
    db = tmp_path / "prefs.db"
    repo = SQLiteAppPreferencesRepository(db)
    assert repo.get() is None
    repo.save({"theme": "dark", "answerCreativity": "balanced"})
    assert repo.get()["answerCreativity"] == "balanced"
    # A fresh instance on the same file still sees it (durable, single row).
    repo2 = SQLiteAppPreferencesRepository(db)
    assert repo2.get()["theme"] == "dark"
    # Saving again replaces the single row (no duplicate rows).
    repo2.save({"theme": "light"})
    assert repo2.get() == {"theme": "light"}


def test_use_case_get_defaults_empty_and_update_merges():
    uc = ManageAppPreferencesUseCase(InMemoryAppPreferencesRepository())
    assert uc.get() == {}
    uc.update({"theme": "dark", "developerMode": True})
    # A later partial update keeps untouched keys.
    merged = uc.update({"theme": "light"})
    assert merged == {"theme": "light", "developerMode": True}
    assert uc.get() == {"theme": "light", "developerMode": True}


def test_use_case_rejects_non_object():
    uc = ManageAppPreferencesUseCase(InMemoryAppPreferencesRepository())
    try:
        uc.update(["not", "a", "dict"])  # type: ignore[arg-type]
        raise AssertionError("expected validation error")
    except AppPreferencesValidationError:
        pass
