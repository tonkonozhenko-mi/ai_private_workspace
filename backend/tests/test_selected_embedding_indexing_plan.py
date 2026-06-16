from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_no_selected_embedding_returns_not_selected(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/models/embedding-indexing-plan")

    assert response.status_code == 200
    result = response.json()
    assert result["selected_provider"] is None
    assert result["selected_model"] is None
    assert result["active_provider"] == "fake"
    assert result["active_model"] == "fake-embedding"
    assert result["index_status"] == "not_indexed"
    assert result["plan_status"] == "not_selected"
    assert result["can_index_now"] is False
    assert result["can_search_now"] is False
    assert result["requires_backend_restart"] is False
    assert result["requires_reindex"] is False
    assert result["requires_new_vector_collection"] is False
    assert result["recommended_actions"] == ["Select an embedding model for this workspace."]


def test_selected_embedding_matching_active_and_indexed_returns_ready(
    tmp_path,
) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    assert (
        _select_embedding(
            workspace["id"],
            "fake",
            "fake-embedding",
        ).status_code
        == 200
    )
    timeline_before = client.get(f"/workspaces/{workspace['id']}/timeline").json()

    response = client.get(f"/workspaces/{workspace['id']}/models/embedding-indexing-plan")

    assert response.status_code == 200
    result = response.json()
    assert result["plan_status"] == "ready"
    assert result["index_status"] == "indexed"
    assert result["can_index_now"] is True
    assert result["can_search_now"] is True
    assert result["requires_backend_restart"] is False
    assert result["requires_reindex"] is False
    assert result["requires_new_vector_collection"] is False
    assert result["recommended_actions"] == [
        "Ask a workspace question or search workspace context."
    ]
    assert client.get(f"/workspaces/{workspace['id']}/timeline").json() == timeline_before


def test_selected_embedding_matching_active_but_not_indexed_needs_index(
    tmp_path,
) -> None:
    workspace = _create_workspace(tmp_path)
    assert (
        _select_embedding(
            workspace["id"],
            "fake",
            "fake-embedding",
        ).status_code
        == 200
    )

    result = client.get(f"/workspaces/{workspace['id']}/models/embedding-indexing-plan").json()

    assert result["plan_status"] == "needs_index"
    assert result["can_index_now"] is True
    assert result["can_search_now"] is False
    assert result["requires_backend_restart"] is False
    assert result["requires_reindex"] is True
    assert result["requires_new_vector_collection"] is False
    assert result["recommended_actions"] == [
        "Index workspace context with the selected embedding model."
    ]


def test_selected_embedding_mismatch_requires_restart_reindex_and_collection(
    tmp_path,
) -> None:
    workspace = _create_workspace(tmp_path)
    assert (
        _select_embedding(
            workspace["id"],
            "ollama",
            "nomic-embed-text",
        ).status_code
        == 200
    )

    result = client.get(f"/workspaces/{workspace['id']}/models/embedding-indexing-plan").json()

    assert result["selected_provider"] == "ollama"
    assert result["selected_model"] == "nomic-embed-text"
    assert result["active_provider"] == "fake"
    assert result["active_model"] == "fake-embedding"
    assert result["plan_status"] == "runtime_mismatch"
    assert result["can_index_now"] is False
    assert result["can_search_now"] is False
    assert result["requires_backend_restart"] is True
    assert result["requires_reindex"] is True
    assert result["requires_new_vector_collection"] is True
    assert result["recommended_actions"] == [
        ("Restart backend with the selected embedding provider and model configuration."),
        "Reindex workspace context after restart.",
    ]
    assert result["warnings"] == [
        "Selected embedding cannot be used until active runtime matches it."
    ]
    assert any("different vector space" in note for note in result["notes"])


def test_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/models/embedding-indexing-plan")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _select_embedding(workspace_id: str, provider: str, model: str):
    return client.put(
        f"/workspaces/{workspace_id}/models/selection",
        json={
            "provider": provider,
            "model": model,
            "model_type": "embedding",
            "selected_reason": "Embedding indexing plan test.",
        },
    )


def _create_indexed_workspace(project_path: Path) -> dict:
    (project_path / "README.md").write_text(
        "# Embedding plan\n\nembeddingplantoken provides context.",
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
            "name": "Selected Embedding Indexing Plan Workspace",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
