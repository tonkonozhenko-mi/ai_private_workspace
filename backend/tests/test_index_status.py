from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.memory.sqlite_index_status_repository import SQLiteIndexStatusRepository
from app.core.domain.index_status import WorkspaceIndexStatus
from app.main import app


client = TestClient(app)


def test_workspace_without_index_returns_not_indexed(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/index/status")

    assert response.status_code == 200
    assert response.json() == {
        "workspace_id": workspace["id"],
        "status": "not_indexed",
        "indexed_files_count": 0,
        "chunks_count": 0,
        "skipped_files_count": 0,
        "last_indexed_at": None,
        "last_error": None,
    }


def test_indexing_workspace_saves_indexed_status(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Indexed\n\nIndex status token.")
    _write_text(tmp_path / "app.py", "print('hello')")
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    index_response = client.post(f"/workspaces/{workspace['id']}/index")
    assert index_response.status_code == 200
    index_result = index_response.json()

    response = client.get(f"/workspaces/{workspace['id']}/index/status")

    assert response.status_code == 200
    status = response.json()
    assert status["workspace_id"] == workspace["id"]
    assert status["status"] == "indexed"
    assert status["indexed_files_count"] == index_result["indexed_files_count"]
    assert status["chunks_count"] == index_result["chunks_count"]
    assert status["skipped_files_count"] == index_result["skipped_files_count"]
    assert status["last_indexed_at"]
    assert status["last_error"] is None


def test_index_status_survives_sqlite_repository_recreation(tmp_path) -> None:
    db_path = tmp_path / "workspaces.db"
    repository = SQLiteIndexStatusRepository(db_path)
    status = WorkspaceIndexStatus(
        workspace_id="workspace-1",
        status="indexed",
        indexed_files_count=2,
        chunks_count=4,
        skipped_files_count=1,
        last_indexed_at="2026-01-01T00:00:00+00:00",
        last_error=None,
    )

    repository.save(status)
    restarted_repository = SQLiteIndexStatusRepository(db_path)

    assert restarted_repository.get(status.workspace_id) == status


def test_workspace_summary_includes_index_status(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Indexed\n\nIndex summary token.")
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200
    index_response = client.post(f"/workspaces/{workspace['id']}/index")
    assert index_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/summary")

    assert response.status_code == 200
    index_status = response.json()["index_status"]
    assert index_status["workspace_id"] == workspace["id"]
    assert index_status["status"] == "indexed"
    assert index_status["indexed_files_count"] == 1
    assert index_status["chunks_count"] == 1
    assert index_status["last_indexed_at"]


def test_index_status_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/index/status")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Index Status Workspace",
            "project_path": str(project_path),
            "assistant_mode": "local",
            "privacy_mode": "private",
        },
    )

    assert response.status_code == 201
    return response.json()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
