from pathlib import Path

from app.adapters.memory.sqlite_workspace_repository import SQLiteWorkspaceRepository


def test_sqlite_repository_creates_parent_directory_before_connect(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "data" / "workspaces.db"
    repo = SQLiteWorkspaceRepository(db_path=db_path)

    assert repo.list() == []
    assert db_path.parent.exists()
    assert db_path.exists()


def test_tauri_runtime_sets_canonical_and_legacy_database_envs() -> None:
    root = Path(__file__).resolve().parents[2]
    content = (root / "frontend/src-tauri/src/lib.rs").read_text()

    assert '.env("APP_DATA_DIR", app_data_dir())' in content
    assert '.env("WORKSPACE_DB_PATH", workspace_db_path())' in content
    assert '.env("AI_WORKSPACE_APP_DATA_DIR", app_data_dir())' in content
    assert '.env("AI_WORKBENCH_DB_PATH", workspace_db_path())' in content
    assert "Port 8000 is already in use and /health is ready" in content
