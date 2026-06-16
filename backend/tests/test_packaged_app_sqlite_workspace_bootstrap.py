from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.adapters.memory.sqlite_workspace_repository import SQLiteWorkspaceRepository
from app.api.routes import workspaces as workspaces_routes
from app.config.settings import get_settings
from app.main import app

client = TestClient(app)


def test_repository_creates_missing_packaged_database_parent(tmp_path: Path) -> None:
    db_path = tmp_path / "AI Private Workspace" / "data" / "workspaces.db"

    repository = SQLiteWorkspaceRepository(db_path)

    assert repository.list() == []
    assert db_path.exists()


def test_repository_error_names_resolved_database_path(tmp_path: Path) -> None:
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("blocked")
    db_path = blocking_file / "workspaces.db"

    with pytest.raises(RuntimeError, match=str(db_path)):
        SQLiteWorkspaceRepository(db_path)


def test_settings_resolve_legacy_aliases_when_canonical_values_are_blank(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app_data_dir = tmp_path / "legacy-app-data"
    db_path = app_data_dir / "data" / "legacy-workspaces.db"
    get_settings.cache_clear()
    with monkeypatch.context() as context:
        context.setenv("APP_DATA_DIR", " ")
        context.setenv("WORKSPACE_DB_PATH", "")
        context.setenv("AI_WORKSPACE_APP_DATA_DIR", str(app_data_dir))
        context.setenv("AI_WORKBENCH_DB_PATH", str(db_path))

        settings = get_settings()

        assert settings.app_data_dir == app_data_dir
        assert settings.workspace_db_path == db_path
        assert db_path.parent.exists()

    get_settings.cache_clear()
    get_settings()


def test_workspace_overview_works_with_fresh_packaged_database_parent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "packaged-app" / "data" / "workspaces.db"
    repository = SQLiteWorkspaceRepository(db_path)
    monkeypatch.setattr(workspaces_routes, "workspace_repository", repository)

    response = client.get("/workspaces/overview")

    assert response.status_code == 200
    assert response.json() == {"total_workspaces": 0, "items": []}


def test_packaged_tauri_origin_can_preflight_workspace_overview() -> None:
    response = client.options(
        "/workspaces/overview",
        headers={
            "Origin": "http://tauri.localhost",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://tauri.localhost"


def test_packaged_runtime_source_contracts() -> None:
    root = Path(__file__).resolve().parents[2]
    tauri_source = (root / "frontend/src-tauri/src/lib.rs").read_text()
    entrypoint = (root / "backend/packaging/pyinstaller_backend_entrypoint.py").read_text()
    tauri_config = (root / "frontend/src-tauri/tauri.conf.json").read_text()

    assert "fs::create_dir_all(data_dir())" in tauri_source
    assert '.env("APP_DATA_DIR", app_data_dir())' in tauri_source
    assert '.env("WORKSPACE_DB_PATH", workspace_db_path())' in tauri_source
    assert "Resolved workspace database path" in tauri_source
    assert "/workspaces/overview returned HTTP 200" in tauri_source
    assert "AI Private Workspace app-owned backend start" in tauri_source
    assert "tauri::RunEvent::Exit" in tauri_source
    assert "libc::kill(pid as i32, libc::SIGTERM)" in tauri_source
    assert 'default=app_data_dir / "data" / "workspaces.db"' in entrypoint
    assert '"identifier": "local.ai-private-workspace"' in tauri_config
    assert '"identifier": "local.ai-private-workspace.app"' not in tauri_config
