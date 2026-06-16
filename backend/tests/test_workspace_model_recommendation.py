from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_uses_workspace_assistant_mode_and_returns_catalog_without_history(
    tmp_path,
) -> None:
    workspace = _create_workspace(tmp_path, assistant_mode="devops")

    response = _recommend(workspace["id"], assistant_profile_id=None)

    assert response.status_code == 200
    result = response.json()
    assert result["workspace_id"] == workspace["id"]
    assert result["assistant_profile_id"] == "devops"
    assert result["recommendations"][0]["model"]["id"] == "ollama-qwen2.5-coder"
    assert all(
        recommendation["performance_score"] is None for recommendation in result["recommendations"]
    )
    assert all(
        "No workspace performance history for this model yet." in recommendation["warnings"]
        for recommendation in result["recommendations"]
    )
    fake = _recommendation(result["recommendations"], "fake-llm")
    assert fake["final_score"] == fake["catalog_score"] - 30
    assert (
        "-30: Fake/testing provider is not recommended for real workspace usage." in fake["reasons"]
    )


def test_workspace_history_improves_rated_preferred_model(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    run = _run_fake_experiment(workspace["id"])
    for rating in (5, 5, 4):
        response = client.post(
            f"/models/experiments/{run['id']}/ratings",
            json={
                "provider": "fake",
                "model": "fake-llm",
                "rating": rating,
                "is_preferred": True,
                "tags": ["useful", "fast"],
            },
        )
        assert response.status_code == 201

    response = _recommend(workspace["id"], assistant_profile_id=None)

    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    fake = _recommendation(recommendations, "fake-llm")
    qwen = _recommendation(recommendations, "ollama-qwen2.5-coder")
    assert fake["performance_score"] is not None
    assert fake["final_score"] > fake["catalog_score"]
    assert (
        "-30: Fake/testing provider is not recommended for real workspace usage." in fake["reasons"]
    )
    assert any(
        warning == "Fake model is intended for development/testing only."
        for warning in fake["warnings"]
    )
    assert fake["historical_signals"]["experiments_count"] == "1"
    assert fake["historical_signals"]["ratings_count"] == "3"
    assert fake["historical_signals"]["preferred_votes"] == "3"
    assert any("Workspace average user rating" in reason for reason in fake["reasons"])
    assert any("workspace preferred votes" in reason for reason in fake["reasons"])
    assert "No workspace performance history for this model yet." not in fake["warnings"]
    assert qwen["performance_score"] is None
    assert "No workspace performance history for this model yet." in qwen["warnings"]
    assert recommendations[0]["model"]["id"] == "ollama-qwen2.5-coder"
    assert qwen["final_score"] > fake["final_score"]


def test_unknown_workspace_and_invalid_model_type_are_rejected(tmp_path) -> None:
    unknown_workspace = _recommend("missing-workspace", assistant_profile_id="devops")
    workspace = _create_workspace(tmp_path, assistant_mode="devops")
    invalid_type = _recommend(
        workspace["id"],
        assistant_profile_id=None,
        model_type="reranker",
    )

    assert unknown_workspace.status_code == 404
    assert unknown_workspace.json()["detail"] == "Workspace not found"
    assert invalid_type.status_code == 400
    assert invalid_type.json()["detail"] == "Unknown model type: reranker"


def _recommend(
    workspace_id: str,
    *,
    assistant_profile_id: str | None,
    model_type: str = "llm",
):
    return client.post(
        f"/workspaces/{workspace_id}/models/recommend",
        json={
            "assistant_profile_id": assistant_profile_id,
            "laptop_profile_id": "balanced",
            "task_type": "workspace_ask",
            "model_type": model_type,
        },
    )


def _recommendation(recommendations: list[dict], model_id: str) -> dict:
    return next(
        recommendation
        for recommendation in recommendations
        if recommendation["model"]["id"] == model_id
    )


def _create_indexed_workspace(project_path: Path) -> dict:
    (project_path / "README.md").write_text(
        "# Recommendation\n\nrecommendationcontexttoken provides shared context.",
        encoding="utf-8",
    )
    workspace = _create_workspace(project_path, assistant_mode="devops")
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200
    return workspace


def _create_workspace(project_path: Path, *, assistant_mode: str) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Recommendation Workspace",
            "project_path": str(project_path),
            "assistant_mode": assistant_mode,
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()


def _run_fake_experiment(workspace_id: str) -> dict:
    response = client.post(
        "/models/experiments/run",
        json={
            "workspace_id": workspace_id,
            "question": "Explain recommendationcontexttoken",
            "candidates": [{"provider": "fake", "model": "fake-llm"}],
        },
    )
    assert response.status_code == 200
    return response.json()
