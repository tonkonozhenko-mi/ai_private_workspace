from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_llm_switch_does_not_require_reindex() -> None:
    response = _switching_plan(
        model_type="llm",
        current_provider="ollama",
        current_model="llama3.2",
        target_provider="ollama",
        target_model="qwen2.5-coder",
    )

    assert response.status_code == 200
    plan = response.json()
    assert plan["requires_reindex"] is False
    assert plan["requires_new_vector_collection"] is False
    assert plan["can_switch_without_reindex"] is True
    assert plan["requires_backend_restart"] is True
    assert {impact["area"] for impact in plan["impacts"]} == {
        "answer_generation",
        "retrieval",
        "vector_index",
    }


def test_embedding_switch_requires_reindex_and_new_collection() -> None:
    response = _switching_plan(
        model_type="embedding",
        current_provider="fake",
        current_model="fake-embedding",
        target_provider="ollama",
        target_model="nomic-embed-text",
    )

    assert response.status_code == 200
    plan = response.json()
    assert plan["requires_reindex"] is True
    assert plan["requires_new_vector_collection"] is True
    assert plan["can_switch_without_reindex"] is False
    assert "Reindex workspace context." in plan["recommended_actions"]


def test_unknown_target_returns_metadata_validation_note() -> None:
    response = _switching_plan(
        model_type="llm",
        current_provider="fake",
        current_model="fake-llm",
        target_provider="ollama",
        target_model="unknown-model",
    )

    assert response.status_code == 200
    assert (
        "Target model is not in catalog; validate metadata before use."
        in response.json()["notes"]
    )


def test_switching_plan_validates_optional_workspace() -> None:
    workspace = client.post(
        "/workspaces",
        json={
            "name": "Switch Plan Workspace",
            "project_path": "/tmp/switch-plan-workspace",
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    ).json()

    valid_response = _switching_plan(
        model_type="llm",
        current_provider="fake",
        current_model="fake-llm",
        target_provider="ollama",
        target_model="llama3.2",
        workspace_id=workspace["id"],
    )
    missing_response = _switching_plan(
        model_type="llm",
        current_provider="fake",
        current_model="fake-llm",
        target_provider="ollama",
        target_model="llama3.2",
        workspace_id="missing-workspace",
    )

    assert valid_response.status_code == 200
    assert valid_response.json()["workspace_id"] == workspace["id"]
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Workspace not found"


def test_invalid_model_type_returns_clear_error() -> None:
    response = _switching_plan(
        model_type="reranker",
        current_provider="fake",
        current_model="current",
        target_provider="fake",
        target_model="target",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown model type: reranker"


def test_known_embedding_dimension_adds_collection_note() -> None:
    response = _switching_plan(
        model_type="embedding",
        current_provider="fake",
        current_model="fake-embedding",
        target_provider="ollama",
        target_model="nomic-embed-text",
    )

    notes = response.json()["notes"]
    assert any("Target embedding dimension is 768" in note for note in notes)
    assert any("dimension aware" in note for note in notes)


def _switching_plan(
    *,
    model_type: str,
    current_provider: str,
    current_model: str,
    target_provider: str,
    target_model: str,
    workspace_id: str | None = None,
):
    return client.post(
        "/models/switching-plan",
        json={
            "model_type": model_type,
            "current_provider": current_provider,
            "current_model": current_model,
            "target_provider": target_provider,
            "target_model": target_model,
            "workspace_id": workspace_id,
        },
    )
