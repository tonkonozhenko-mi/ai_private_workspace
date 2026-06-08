from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_explains_known_catalog_model_with_catalog_and_history_sections(
    tmp_path,
) -> None:
    workspace = _create_workspace(tmp_path)

    response = _explain(
        workspace["id"],
        provider="ollama",
        model="qwen2.5-coder",
        model_type="llm",
    )

    assert response.status_code == 200
    explanation = response.json()
    assert explanation["display_name"] == "Qwen 2.5 Coder"
    assert {section["title"] for section in explanation["sections"]} == {
        "Catalog fit",
        "Workspace history",
        "Switching impact",
        "Risks and limitations",
    }
    catalog_fit = _section(explanation, "Catalog fit")
    assert "Assistant profile devops is recommended." in catalog_fit["bullets"]
    assert "Laptop profile balanced is recommended." in catalog_fit["bullets"]
    assert any("Workspace-aware final score" in bullet for bullet in catalog_fit["bullets"])


def test_no_history_adds_warning_and_experiment_action(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    explanation = _explain(
        workspace["id"],
        provider="ollama",
        model="qwen2.5-coder",
        model_type="llm",
    ).json()

    assert "mostly from catalog metadata" in explanation["summary"]
    assert "No workspace performance history for this model yet." in explanation[
        "warnings"
    ]
    assert "Run a model experiment and rate the answer." in explanation[
        "recommended_actions"
    ]
    assert any(
        "Ensure Ollama model qwen2.5-coder is installed locally." == action
        for action in explanation["recommended_actions"]
    )


def test_explanation_includes_workspace_history_and_fake_warning(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    run = _run_fake_experiment(workspace["id"])
    rating = client.post(
        f"/models/experiments/{run['id']}/ratings",
        json={
            "provider": "fake",
            "model": "fake-llm",
            "rating": 5,
            "is_preferred": True,
            "tags": ["useful", "fast"],
        },
    )
    assert rating.status_code == 201

    explanation = _explain(
        workspace["id"],
        provider="fake",
        model="fake-llm",
        model_type="llm",
    ).json()

    assert "mainly for development/testing" in explanation["summary"]
    assert "Fake model is intended for development/testing only." in explanation[
        "warnings"
    ]
    history = _section(explanation, "Workspace history")
    assert "Experiments: 1." in history["bullets"]
    assert "Ratings: 1." in history["bullets"]
    assert "Average rating: 5.0." in history["bullets"]
    assert "Preferred votes: 1." in history["bullets"]
    assert "Common tags: fast, useful." in history["bullets"]


def test_embedding_explanation_requires_reindex(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    explanation = _explain(
        workspace["id"],
        provider="ollama",
        model="nomic-embed-text",
        model_type="embedding",
    ).json()

    switching = _section(explanation, "Switching impact")
    assert "Switching embedding models requires workspace reindexing." in switching[
        "bullets"
    ]
    assert "Review the model switching plan before reindexing." in explanation[
        "recommended_actions"
    ]


def test_unknown_model_still_returns_explanation_with_warning(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = _explain(
        workspace["id"],
        provider="custom",
        model="private-model",
        model_type="llm",
    )

    assert response.status_code == 200
    explanation = response.json()
    assert explanation["display_name"] is None
    assert "unknown to the current catalog" in explanation["summary"]
    assert "Model is not present in the current local model catalog." in explanation[
        "warnings"
    ]
    assert _section(explanation, "Catalog fit")["bullets"] == [
        "Model is not present in the current local model catalog."
    ]
    assert "Validate model metadata before use." in explanation["recommended_actions"]
    assert (
        "Configure a compatible provider adapter for custom."
        in explanation["recommended_actions"]
    )


def test_unknown_workspace_returns_404() -> None:
    response = _explain(
        "missing-workspace",
        provider="ollama",
        model="qwen2.5-coder",
        model_type="llm",
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _explain(
    workspace_id: str,
    *,
    provider: str,
    model: str,
    model_type: str,
):
    return client.post(
        f"/workspaces/{workspace_id}/models/explain",
        json={
            "provider": provider,
            "model": model,
            "model_type": model_type,
            "assistant_profile_id": None,
            "laptop_profile_id": "balanced",
            "task_type": "workspace_ask",
        },
    )


def _section(explanation: dict, title: str) -> dict:
    return next(
        section for section in explanation["sections"] if section["title"] == title
    )


def _create_indexed_workspace(project_path: Path) -> dict:
    (project_path / "README.md").write_text(
        "# Explanation\n\nexplanationcontexttoken provides shared context.",
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
            "name": "Explanation Workspace",
            "project_path": str(project_path),
            "assistant_mode": "devops",
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
            "question": "Explain explanationcontexttoken",
            "candidates": [{"provider": "fake", "model": "fake-llm"}],
        },
    )
    assert response.status_code == 200
    return response.json()
