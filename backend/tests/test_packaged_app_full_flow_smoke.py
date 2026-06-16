import logging
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.memory.sqlite_index_status_repository import SQLiteIndexStatusRepository
from app.adapters.memory.sqlite_project_scan_repository import SQLiteProjectScanRepository
from app.adapters.memory.sqlite_workspace_repository import SQLiteWorkspaceRepository
from app.config.settings import get_settings
from app.main import app

client = TestClient(app)
PACKAGED_ORIGIN = "http://tauri.localhost"


def test_packaged_create_scan_index_ask_and_restart_persistence(
    tmp_path: Path,
    caplog,
) -> None:
    caplog.set_level(logging.INFO)
    project_path = tmp_path / "packaged-full-flow-project"
    project_path.mkdir()
    (project_path / "README.md").write_text(
        "# Packaged full flow\n\nThis local project documents the packaged product smoke.",
        encoding="utf-8",
    )

    created = client.post(
        "/workspaces",
        json={
            "name": "Packaged Full Flow",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert created.status_code == 201
    workspace_id = created.json()["id"]

    overview = client.get("/workspaces/overview")
    assert overview.status_code == 200
    assert workspace_id in {item["workspace_id"] for item in overview.json()["items"]}

    scan_job = _run_job(workspace_id, "scan")
    assert scan_job["status"] == "completed"
    assert scan_job["result_summary"]["scanned_files"] == "1"

    index_job = _run_job(workspace_id, "index")
    assert index_job["status"] == "completed"
    assert index_job["result_summary"]["chunks_count"] == "1"

    selected = client.put(
        f"/workspaces/{workspace_id}/models/selection",
        json={
            "provider": "fake",
            "model": "fake-llm",
            "model_type": "llm",
            "selected_reason": "Deterministic packaged full-flow smoke.",
        },
    )
    assert selected.status_code == 200

    asked = client.post(
        f"/workspaces/{workspace_id}/ask-selected",
        json={"question": "What is this project about?", "limit": 3},
    )
    assert asked.status_code == 200
    answer = asked.json()
    assert answer["llm_provider"] == "fake"
    assert answer["llm_model"] == "fake-llm"
    assert answer["diagnostic_code"] is None
    assert answer["used_context_chunks"] == 1
    assert answer["sources"][0]["source_path"] == "README.md"

    db_path = get_settings().workspace_db_path
    restarted_workspace_repository = SQLiteWorkspaceRepository(db_path)
    restarted_scan_repository = SQLiteProjectScanRepository(db_path)
    restarted_index_status_repository = SQLiteIndexStatusRepository(db_path)

    assert restarted_workspace_repository.get(workspace_id) is not None
    assert restarted_scan_repository.get_latest_scan(workspace_id) is not None
    persisted_index = restarted_index_status_repository.get(workspace_id)
    assert persisted_index is not None
    assert persisted_index.status == "indexed"
    assert persisted_index.chunks_count == 1

    assert "workspace job started" in caplog.text
    assert "job_type=scan" in caplog.text
    assert "job_type=index" in caplog.text
    assert "workspace ask completed" in caplog.text
    assert "retrieved_chunks=1" in caplog.text


def test_packaged_full_flow_cors_preflight() -> None:
    workspace_id = "packaged-cors-contract"
    paths = [
        f"/workspaces/{workspace_id}/jobs/scan",
        f"/workspaces/{workspace_id}/jobs/index",
        f"/workspaces/{workspace_id}/ask-selected",
    ]

    for path in paths:
        response = client.options(
            path,
            headers={
                "Origin": PACKAGED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == PACKAGED_ORIGIN


def test_packaged_sqlite_restart_initialization_creates_missing_parent(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "app-owned" / "data" / "workspaces.db"

    repository = SQLiteWorkspaceRepository(db_path)

    assert repository.list() == []
    assert db_path.exists()


def _run_job(workspace_id: str, job_type: str) -> dict:
    started = client.post(f"/workspaces/{workspace_id}/jobs/{job_type}")
    assert started.status_code == 200
    job = started.json()

    deadline = time.monotonic() + 5
    while job["status"] not in {"completed", "failed", "cancelled"}:
        assert time.monotonic() < deadline
        time.sleep(0.01)
        polled = client.get(f"/workspaces/{workspace_id}/jobs/{job['job_id']}")
        assert polled.status_code == 200
        job = polled.json()

    return job
