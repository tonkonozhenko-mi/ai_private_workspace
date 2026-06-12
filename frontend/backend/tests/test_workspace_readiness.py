from pathlib import Path

from fastapi.testclient import TestClient

from app.api.dependencies import index_status_repository
from app.core.domain.index_status import WorkspaceIndexStatus
from app.main import app


client = TestClient(app)


def test_workspace_without_scan_needs_setup(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/readiness")

    assert response.status_code == 200
    readiness = response.json()
    assert readiness["status"] == "needs_setup"
    assert readiness["can_scan"] is True
    assert readiness["can_analyze"] is False
    assert readiness["can_index"] is False
    assert readiness["can_ask"] is False
    assert readiness["can_execute_commands"] is True
    assert "Run project scan." in readiness["recommended_next_steps"]
    assert _capability(readiness, "project_scan")["available"] is True
    assert _capability(readiness, "deterministic_analysis")["available"] is False
    assert _capability(readiness, "local_command_execution")["available"] is False


def test_workspace_with_scan_recommends_indexing(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Readiness")
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/readiness")

    assert response.status_code == 200
    readiness = response.json()
    assert readiness["status"] == "needs_setup"
    assert readiness["can_analyze"] is True
    assert readiness["can_index"] is True
    assert readiness["can_ask"] is False
    assert "Index workspace context." in readiness["recommended_next_steps"]
    assert _capability(readiness, "project_overview_report")["available"] is True
    assert _capability(readiness, "workspace_indexing")["available"] is True


def test_indexed_workspace_is_ready_and_can_ask(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Ready\n\nReadiness context.")
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200
    index_response = client.post(f"/workspaces/{workspace['id']}/index")
    assert index_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/readiness")

    assert response.status_code == 200
    readiness = response.json()
    assert readiness["status"] == "ready"
    assert readiness["can_ask"] is True
    assert (
        "Ask a workspace question or generate project overview."
        in readiness["recommended_next_steps"]
    )
    assert (
        "Reindex workspace context after API restart when using the in-memory "
        "vector store."
        in readiness["recommended_next_steps"]
    )
    assert _capability(readiness, "workspace_ask")["available"] is True


def test_failed_index_status_returns_degraded(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    index_status_repository.save(
        WorkspaceIndexStatus(
            workspace_id=workspace["id"],
            status="failed",
            indexed_files_count=0,
            chunks_count=0,
            skipped_files_count=0,
            last_indexed_at="2026-01-01T00:00:00+00:00",
            last_error="Embedding provider unavailable",
        )
    )

    response = client.get(f"/workspaces/{workspace['id']}/readiness")

    assert response.status_code == 200
    readiness = response.json()
    assert readiness["status"] == "degraded"
    assert readiness["can_ask"] is False
    assert (
        "Review the failed index status and retry workspace indexing."
        in readiness["recommended_next_steps"]
    )


def test_pending_command_adds_review_recommendation(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    command_response = client.post(
        f"/workspaces/{workspace['id']}/commands",
        json={
            "command": "git status",
            "cwd": str(tmp_path),
            "reason": "Check repository state",
        },
    )
    assert command_response.status_code == 201

    response = client.get(f"/workspaces/{workspace['id']}/readiness")

    assert response.status_code == 200
    assert (
        "Review pending command approvals."
        in response.json()["recommended_next_steps"]
    )


def test_readiness_includes_provider_configuration(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/readiness")

    assert response.status_code == 200
    configuration = response.json()["configuration"]
    assert configuration["VECTOR_STORE"] == "memory"
    assert configuration["EMBEDDING_PROVIDER"] == "fake"
    assert configuration["LLM_PROVIDER"] == "fake"
    assert configuration["COMMAND_RUNNER"] == "fake"
    assert configuration["QDRANT_COLLECTION"] == "ai_workbench_chunks"
    assert configuration["OLLAMA_EMBEDDING_MODEL"] == "nomic-embed-text"
    assert configuration["OLLAMA_LLM_MODEL"] == "llama3.2"
    assert configuration["VECTOR_STORE_PATH"].endswith("/data/vector_store.db")
    assert (
        "Use Qdrant for persistent vector search across restarts."
        in response.json()["recommended_next_steps"]
    )
    assert (
        "Enable Ollama LLM provider for real local answers."
        in response.json()["recommended_next_steps"]
    )


def test_readiness_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/readiness")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _capability(readiness: dict, capability_id: str) -> dict:
    return next(
        capability
        for capability in readiness["capabilities"]
        if capability["id"] == capability_id
    )


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Readiness Workspace",
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
