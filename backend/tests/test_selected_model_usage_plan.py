from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_no_selections_cannot_use_selected_models(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/models/usage-plan")

    assert response.status_code == 200
    result = response.json()
    assert result["can_ask_with_selected_llm"] is False
    assert result["can_index_with_selected_embedding"] is False
    assert result["can_search_with_selected_embedding"] is False
    assert result["can_use_selected_models_fully"] is False
    assert result["selected_llm_provider"] is None
    assert result["selected_embedding_provider"] is None
    assert result["index_status"] == "not_indexed"
    assert result["recommended_actions"][:2] == [
        "Select an LLM for this workspace.",
        "Select an embedding model for this workspace.",
    ]
    assert {capability["status"] for capability in result["capabilities"]} == {
        "not_selected"
    }


def test_selected_fake_llm_on_fake_runtime_can_ask(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200

    result = client.get(
        f"/workspaces/{workspace['id']}/models/usage-plan"
    ).json()

    assert result["can_ask_with_selected_llm"] is True
    assert result["active_llm_provider"] == "fake"
    assert result["active_llm_model"] == "fake-llm"
    assert _capability(result, "ask_with_selected_llm")["status"] == "ready"


def test_selected_ollama_llm_while_active_fake_can_ask_via_override(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(
        workspace["id"],
        "ollama",
        "qwen2.5-coder",
        "llm",
    ).status_code == 200

    result = client.get(
        f"/workspaces/{workspace['id']}/models/usage-plan"
    ).json()

    assert result["selected_llm_provider"] == "ollama"
    assert result["active_llm_provider"] == "fake"
    assert result["can_ask_with_selected_llm"] is True
    assert "per-request" in _capability(result, "ask_with_selected_llm")["reason"]
    assert not any("Restart backend with the selected LLM" in action for action in result["recommended_actions"])


def test_selected_unsupported_llm_cannot_ask(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(
        workspace["id"],
        "custom",
        "private-model",
        "llm",
    ).status_code == 200

    result = client.get(
        f"/workspaces/{workspace['id']}/models/usage-plan"
    ).json()

    assert result["can_ask_with_selected_llm"] is False
    capability = _capability(result, "ask_with_selected_llm")
    assert capability["status"] == "blocked"
    assert "not supported" in capability["reason"]
    assert result["recommended_actions"][0].startswith(
        "Select an embedding model"
    )
    assert any(
        "Configure a compatible LLM provider adapter" in action
        for action in result["recommended_actions"]
    )


def test_selected_embedding_matching_active_and_indexed_can_search(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    assert _select(
        workspace["id"],
        "fake",
        "fake-embedding",
        "embedding",
    ).status_code == 200

    result = client.get(
        f"/workspaces/{workspace['id']}/models/usage-plan"
    ).json()

    assert result["can_index_with_selected_embedding"] is True
    assert result["can_search_with_selected_embedding"] is True
    assert _capability(result, "search_with_selected_embedding")["status"] == "ready"


def test_selected_embedding_matching_active_but_not_indexed_needs_index(
    tmp_path,
) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(
        workspace["id"],
        "fake",
        "fake-embedding",
        "embedding",
    ).status_code == 200

    result = client.get(
        f"/workspaces/{workspace['id']}/models/usage-plan"
    ).json()

    assert result["can_index_with_selected_embedding"] is True
    assert result["can_search_with_selected_embedding"] is False
    assert _capability(result, "search_with_selected_embedding")["status"] == "needs_action"
    assert (
        "Reindex workspace context with the selected embedding model."
        in result["recommended_actions"]
    )


def test_selected_embedding_mismatch_needs_restart_and_reindex(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(
        workspace["id"],
        "ollama",
        "nomic-embed-text",
        "embedding",
    ).status_code == 200

    result = client.get(
        f"/workspaces/{workspace['id']}/models/usage-plan"
    ).json()

    assert result["can_index_with_selected_embedding"] is False
    assert result["can_search_with_selected_embedding"] is False
    assert _capability(result, "index_with_selected_embedding")["status"] == "needs_action"
    assert result["recommended_actions"][-2:] == [
        (
            "Restart backend with the selected embedding provider and model "
            "configuration."
        ),
        "Reindex workspace context with the selected embedding model.",
    ]


def test_can_use_selected_models_fully_only_when_both_are_usable(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200
    assert _select(
        workspace["id"],
        "fake",
        "fake-embedding",
        "embedding",
    ).status_code == 200
    timeline_before = client.get(f"/workspaces/{workspace['id']}/timeline").json()

    response = client.get(f"/workspaces/{workspace['id']}/models/usage-plan")

    assert response.status_code == 200
    result = response.json()
    assert result["can_ask_with_selected_llm"] is True
    assert result["can_search_with_selected_embedding"] is True
    assert result["can_use_selected_models_fully"] is True
    assert result["recommended_actions"] == [
        "Ask a workspace question using the selected LLM per-request override."
    ]
    assert client.get(f"/workspaces/{workspace['id']}/timeline").json() == timeline_before


def test_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/models/usage-plan")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _capability(result: dict, capability_id: str) -> dict:
    return next(
        capability
        for capability in result["capabilities"]
        if capability["id"] == capability_id
    )


def _select(workspace_id: str, provider: str, model: str, model_type: str):
    return client.put(
        f"/workspaces/{workspace_id}/models/selection",
        json={
            "provider": provider,
            "model": model,
            "model_type": model_type,
            "selected_reason": "Usage plan test selection.",
        },
    )


def _create_indexed_workspace(project_path: Path) -> dict:
    (project_path / "README.md").write_text(
        "# Usage plan\n\nusagemodelplantoken provides context.",
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
            "name": "Selected Model Usage Plan Workspace",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
