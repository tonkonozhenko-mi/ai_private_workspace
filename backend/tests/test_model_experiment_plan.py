from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_indexed_workspace_llm_comparison_requires_no_reindex(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)

    response = _experiment_plan(workspace["id"])

    assert response.status_code == 200
    plan = response.json()
    assert plan["experiment_type"] == "llm_comparison"
    assert plan["requires_reindex"] is False
    assert plan["can_compare_without_reindex"] is True
    assert plan["shared_context_strategy"] == (
        "Use the same indexed workspace context for all LLM candidates."
    )
    assert all(candidate["requires_reindex"] is False for candidate in plan["candidates"])
    assert all(candidate["requires_backend_restart"] is False for candidate in plan["candidates"])


def test_not_indexed_workspace_recommends_indexing_first(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    plan = _experiment_plan(workspace["id"]).json()

    assert plan["can_compare_without_reindex"] is False
    assert plan["recommended_actions"][0] == "Index workspace first."
    assert all(
        "Workspace is not indexed; shared context is unavailable." in candidate["warnings"]
        for candidate in plan["candidates"]
    )


def test_known_catalog_candidates_are_marked_known(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    plan = _experiment_plan(workspace["id"]).json()

    assert {
        (candidate["provider"], candidate["model"], candidate["known_in_catalog"])
        for candidate in plan["candidates"]
    } == {
        ("ollama", "llama3.2", True),
        ("ollama", "qwen2.5-coder", True),
    }
    assert {candidate["display_name"] for candidate in plan["candidates"]} == {
        "Llama 3.2",
        "Qwen 2.5 Coder",
    }


def test_unknown_candidate_produces_warnings(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = _experiment_plan(
        workspace["id"],
        candidates=[{"provider": "custom", "model": "private-model"}],
    )

    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["known_in_catalog"] is False
    assert candidate["display_name"] is None
    assert (
        "Model is not in catalog; validate metadata before experiment." in (candidate["warnings"])
    )
    assert "Provider custom requires a compatible LLM provider adapter." in candidate["warnings"]
    assert candidate["requires_backend_restart"] is True


def test_empty_question_returns_clear_error(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = _experiment_plan(workspace["id"], question="")

    assert response.status_code == 400
    assert response.json()["detail"] == "Question is required"


def test_invalid_experiment_type_returns_clear_error(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = _experiment_plan(workspace["id"], experiment_type="embedding_benchmark")

    assert response.status_code == 400
    assert response.json()["detail"] == ("Unknown experiment type: embedding_benchmark")


def test_unknown_workspace_returns_404() -> None:
    response = _experiment_plan("missing-workspace")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_experiment_plan_does_not_mutate_workspace_state(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    workspace_id = workspace["id"]
    workspace_before = client.get(f"/workspaces/{workspace_id}").json()
    index_before = client.get(f"/workspaces/{workspace_id}/index/status").json()
    timeline_before = client.get(f"/workspaces/{workspace_id}/timeline").json()

    assert _experiment_plan(workspace_id).status_code == 200

    assert client.get(f"/workspaces/{workspace_id}").json() == workspace_before
    assert client.get(f"/workspaces/{workspace_id}/index/status").json() == index_before
    assert client.get(f"/workspaces/{workspace_id}/timeline").json() == timeline_before


def _experiment_plan(
    workspace_id: str,
    *,
    question: str = "How is Terraform backend configured?",
    experiment_type: str = "llm_comparison",
    candidates: list[dict] | None = None,
):
    return client.post(
        "/models/experiments/plan",
        json={
            "workspace_id": workspace_id,
            "question": question,
            "experiment_type": experiment_type,
            "candidates": candidates
            or [
                {"provider": "ollama", "model": "llama3.2"},
                {"provider": "ollama", "model": "qwen2.5-coder"},
            ],
        },
    )


def _create_indexed_workspace(project_path: Path) -> dict:
    (project_path / "README.md").write_text(
        "# Experiment\n\nShared indexed context.",
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
            "name": "Model Experiment Workspace",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
