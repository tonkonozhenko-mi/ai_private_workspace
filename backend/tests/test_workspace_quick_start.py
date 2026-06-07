from pathlib import Path

from fastapi.testclient import TestClient

from app.api.dependencies import (
    index_status_repository,
    project_scan_repository,
    workspace_repository,
)
from app.core.use_cases.get_workspace_quick_start import (
    GetWorkspaceQuickStartInput,
    GetWorkspaceQuickStartUseCase,
)
from app.main import app


client = TestClient(app)


def test_new_workspace_returns_scan_as_next_action(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/quick-start")

    assert response.status_code == 200
    quick_start = response.json()
    assert quick_start["status"] == "new"
    assert quick_start["next_action_id"] == "scan_project"
    assert quick_start["next_action_title"] == "Run project scan"
    assert _step(quick_start, "runtime_setup")["status"] == "optional"
    assert _step(quick_start, "scan_project")["status"] == "next"
    assert _step(quick_start, "review_detected_skills")["status"] == "blocked"
    assert _step(quick_start, "index_workspace")["status"] == "blocked"
    assert _step(quick_start, "ask_first_question")["status"] == "blocked"


def test_scanned_workspace_returns_index_as_next_action(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Quick Start")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/quick-start")

    assert response.status_code == 200
    quick_start = response.json()
    assert quick_start["status"] == "scanned"
    assert quick_start["next_action_id"] == "index_workspace"
    assert _step(quick_start, "scan_project")["status"] == "done"
    assert _step(quick_start, "scan_project")["action_id"] == "scan_project"
    assert _step(quick_start, "review_detected_skills")["status"] == "done"
    assert _step(quick_start, "index_workspace")["status"] == "next"
    assert _step(quick_start, "generate_project_overview")["status"] == "optional"


def test_indexed_workspace_with_fake_memory_runtime_is_indexed(tmp_path) -> None:
    workspace = _create_scanned_and_indexed_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/quick-start")

    assert response.status_code == 200
    quick_start = response.json()
    assert quick_start["status"] == "indexed"
    assert quick_start["next_action_id"] == "ask_first_question"
    assert _step(quick_start, "index_workspace")["status"] == "done"
    assert _step(quick_start, "index_workspace")["action_id"] == "index_workspace"
    assert _step(quick_start, "ask_first_question")["status"] == "next"
    assert any("in-memory vector store" in note for note in quick_start["notes"])
    assert any("fake LLM provider" in note for note in quick_start["notes"])


def test_indexed_workspace_with_qdrant_and_ollama_settings_is_ready(tmp_path) -> None:
    workspace = _create_scanned_and_indexed_workspace(tmp_path)

    quick_start = GetWorkspaceQuickStartUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        index_status_repository=index_status_repository,
        configuration={
            "VECTOR_STORE": "qdrant",
            "LLM_PROVIDER": "ollama",
        },
    ).execute(GetWorkspaceQuickStartInput(workspace_id=workspace["id"]))

    assert quick_start.status == "ready"
    assert quick_start.next_action_id == "ask_first_question"
    assert _domain_step(quick_start, "runtime_setup").status == "done"
    assert quick_start.notes == [
        "Quick Start reads persisted state only and never runs workspace actions."
    ]


def test_quick_start_steps_include_expected_endpoints(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    workspace_id = workspace["id"]

    quick_start = client.get(f"/workspaces/{workspace_id}/quick-start").json()

    assert _step(quick_start, "runtime_setup")["endpoint"] == (
        "POST /runtime/setup-guide"
    )
    assert _step(quick_start, "scan_project")["endpoint"] == (
        f"POST /workspaces/{workspace_id}/scan"
    )
    assert _step(quick_start, "review_detected_skills")["endpoint"] == (
        f"GET /workspaces/{workspace_id}/summary"
    )
    assert _step(quick_start, "index_workspace")["endpoint"] == (
        f"POST /workspaces/{workspace_id}/index"
    )
    assert _step(quick_start, "ask_first_question")["endpoint"] == (
        f"POST /workspaces/{workspace_id}/ask"
    )
    assert _step(quick_start, "generate_project_overview")["endpoint"] == (
        f"GET /workspaces/{workspace_id}/reports/project-overview"
    )


def test_quick_start_read_does_not_create_activity_or_commands(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    workspace_id = workspace["id"]
    timeline_before = client.get(f"/workspaces/{workspace_id}/timeline").json()

    assert client.get(f"/workspaces/{workspace_id}/quick-start").status_code == 200

    assert client.get(f"/workspaces/{workspace_id}/timeline").json() == timeline_before
    assert client.get(f"/workspaces/{workspace_id}/commands").json() == []


def test_quick_start_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/quick-start")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _create_scanned_and_indexed_workspace(project_path: Path) -> dict:
    _write_text(project_path / "README.md", "# Quick Start\n\nIndexed context.")
    workspace = _create_workspace(project_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200
    return workspace


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Quick Start Workspace",
            "project_path": str(project_path),
            "assistant_mode": "developer",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()


def _step(quick_start: dict, step_id: str) -> dict:
    return next(step for step in quick_start["steps"] if step["id"] == step_id)


def _domain_step(quick_start, step_id: str):
    return next(step for step in quick_start.steps if step.id == step_id)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
