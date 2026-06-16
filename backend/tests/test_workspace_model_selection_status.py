from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_no_selection_returns_not_configured(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/models/selection/status")

    assert response.status_code == 200
    result = response.json()
    assert result["overall_status"] == "not_configured"
    assert result["llm_status"]["status"] == "not_selected"
    assert result["llm_status"]["active_provider"] == "fake"
    assert result["llm_status"]["active_model"] == "fake-llm"
    assert result["embedding_status"]["status"] == "not_selected"
    assert result["embedding_status"]["active_provider"] == "fake"
    assert result["embedding_status"]["active_model"] == "fake-embedding"
    assert result["recommended_actions"] == [
        "Select an LLM for this workspace.",
        "Select an embedding model for this workspace.",
    ]


def test_selected_llm_matching_active_fake_runtime_is_ready(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200

    result = client.get(f"/workspaces/{workspace['id']}/models/selection/status").json()

    assert result["llm_status"]["status"] == "ready"
    assert result["llm_status"]["matches_active_runtime"] is True
    assert result["llm_status"]["requires_backend_restart"] is False
    assert result["llm_status"]["requires_reindex"] is False
    assert result["overall_status"] == "ready"


def test_selected_llm_mismatch_requires_backend_restart(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert (
        _select(
            workspace["id"],
            "ollama",
            "qwen2.5-coder",
            "llm",
        ).status_code
        == 200
    )

    result = client.get(f"/workspaces/{workspace['id']}/models/selection/status").json()

    assert result["llm_status"]["status"] == "runtime_mismatch"
    assert result["llm_status"]["requires_backend_restart"] is True
    assert result["llm_status"]["requires_reindex"] is False
    assert result["overall_status"] == "runtime_mismatch"
    assert (
        "Restart backend with the selected LLM provider and model configuration."
        in result["recommended_actions"]
    )


def test_selected_embedding_mismatch_requires_restart_and_reindex(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert (
        _select(
            workspace["id"],
            "ollama",
            "nomic-embed-text",
            "embedding",
        ).status_code
        == 200
    )

    result = client.get(f"/workspaces/{workspace['id']}/models/selection/status").json()

    assert result["embedding_status"]["status"] == "runtime_mismatch"
    assert result["embedding_status"]["requires_backend_restart"] is True
    assert result["embedding_status"]["requires_reindex"] is True
    assert result["overall_status"] == "requires_reindex"
    assert (
        "Restart backend with the selected embedding provider and model configuration."
        in result["recommended_actions"]
    )
    assert (
        "Reindex workspace context with the selected embedding model."
        in result["recommended_actions"]
    )


def test_selected_embedding_match_without_index_requires_reindex(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert (
        _select(
            workspace["id"],
            "fake",
            "fake-embedding",
            "embedding",
        ).status_code
        == 200
    )

    result = client.get(f"/workspaces/{workspace['id']}/models/selection/status").json()

    assert result["embedding_status"]["matches_active_runtime"] is True
    assert result["embedding_status"]["status"] == "requires_reindex"
    assert result["embedding_status"]["requires_backend_restart"] is False
    assert result["embedding_status"]["requires_reindex"] is True
    assert result["overall_status"] == "requires_reindex"


def test_matching_selected_models_and_index_are_ready(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200
    assert (
        _select(
            workspace["id"],
            "fake",
            "fake-embedding",
            "embedding",
        ).status_code
        == 200
    )
    timeline_before = client.get(f"/workspaces/{workspace['id']}/timeline").json()

    response = client.get(f"/workspaces/{workspace['id']}/models/selection/status")

    assert response.status_code == 200
    result = response.json()
    assert result["llm_status"]["status"] == "ready"
    assert result["embedding_status"]["status"] == "ready"
    assert result["overall_status"] == "ready"
    assert result["recommended_actions"] == ["Ask a workspace question."]
    assert client.get(f"/workspaces/{workspace['id']}/timeline").json() == timeline_before


def test_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/models/selection/status")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _select(workspace_id: str, provider: str, model: str, model_type: str):
    return client.put(
        f"/workspaces/{workspace_id}/models/selection",
        json={
            "provider": provider,
            "model": model,
            "model_type": model_type,
            "selected_reason": "Status test selection.",
        },
    )


def _create_indexed_workspace(project_path: Path) -> dict:
    (project_path / "README.md").write_text(
        "# Selection status\n\nselectionstatustoken provides context.",
        encoding="utf-8",
    )
    workspace = _create_workspace(project_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200
    return workspace


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Selection Status Workspace",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
