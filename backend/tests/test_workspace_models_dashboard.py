from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_dashboard_aggregates_model_read_models_without_selections(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    timeline_before = client.get(f"/workspaces/{workspace['id']}/timeline").json()

    response = client.get(f"/workspaces/{workspace['id']}/models/dashboard")

    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["workspace_id"] == workspace["id"]
    assert dashboard["selected_llm_provider"] is None
    assert dashboard["selected_embedding_provider"] is None
    assert dashboard["overall_status"] == "needs_model_selection"
    assert dashboard["primary_next_action_id"] == "select_llm_model"
    assert dashboard["primary_next_action_title"] == "Select an LLM model"
    assert dashboard["selection"]["workspace_id"] == workspace["id"]
    assert dashboard["selection_status"]["workspace_id"] == workspace["id"]
    assert dashboard["usage_plan"]["workspace_id"] == workspace["id"]
    assert dashboard["embedding_indexing_plan"]["workspace_id"] == workspace["id"]
    assert dashboard["recommendations"]["workspace_id"] == workspace["id"]
    assert dashboard["recommendations"]["assistant_profile_id"] == "devops"
    assert dashboard["recommendations"]["laptop_profile_id"] == "balanced"
    assert dashboard["recommendations"]["task_type"] == "workspace_ask"
    assert dashboard["recommendations"]["model_type"] == "llm"
    assert dashboard["recommendations"]["recommendations"]
    assert dashboard["performance_summary"]["workspace_id"] == workspace["id"]
    assert dashboard["performance_summary"]["items"] == []
    assert client.get(f"/workspaces/{workspace['id']}/timeline").json() == timeline_before


def test_selected_llm_only_prompts_embedding_selection(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200

    dashboard = client.get(
        f"/workspaces/{workspace['id']}/models/dashboard"
    ).json()

    assert dashboard["selected_llm_provider"] == "fake"
    assert dashboard["selected_llm_model"] == "fake-llm"
    assert dashboard["selected_embedding_provider"] is None
    assert dashboard["usage_plan"]["can_ask_with_selected_llm"] is True
    assert dashboard["overall_status"] == "needs_model_selection"
    assert dashboard["primary_next_action_id"] == "select_embedding_model"
    assert dashboard["primary_next_action_title"] == "Select an embedding model"


def test_embedding_mismatch_requires_embedding_setup_and_restart(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200
    assert _select(
        workspace["id"],
        "ollama",
        "nomic-embed-text",
        "embedding",
    ).status_code == 200

    dashboard = client.get(
        f"/workspaces/{workspace['id']}/models/dashboard"
    ).json()

    assert dashboard["overall_status"] == "needs_embedding_setup"
    assert dashboard["usage_plan"]["can_ask_with_selected_llm"] is True
    assert dashboard["embedding_indexing_plan"]["plan_status"] == "runtime_mismatch"
    assert dashboard["primary_next_action_id"] == "restart_backend_for_embedding"
    assert (
        dashboard["primary_next_action_title"]
        == "Restart backend for selected embedding"
    )


def test_selected_llm_usable_but_matching_embedding_needs_index(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200
    assert _select(
        workspace["id"],
        "fake",
        "fake-embedding",
        "embedding",
    ).status_code == 200

    dashboard = client.get(
        f"/workspaces/{workspace['id']}/models/dashboard"
    ).json()

    assert dashboard["usage_plan"]["can_ask_with_selected_llm"] is True
    assert dashboard["usage_plan"]["can_search_with_selected_embedding"] is False
    assert dashboard["embedding_indexing_plan"]["plan_status"] == "needs_index"
    assert dashboard["overall_status"] == "needs_embedding_setup"
    assert dashboard["primary_next_action_id"] == "reindex_workspace"
    assert (
        dashboard["primary_next_action_title"]
        == "Index workspace with selected embedding"
    )


def test_ready_models_dashboard_uses_selected_ask_as_primary_action(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200
    assert _select(
        workspace["id"],
        "fake",
        "fake-embedding",
        "embedding",
    ).status_code == 200

    dashboard = client.get(
        f"/workspaces/{workspace['id']}/models/dashboard"
    ).json()

    assert dashboard["overall_status"] == "ready"
    assert dashboard["usage_plan"]["can_use_selected_models_fully"] is True
    assert dashboard["embedding_indexing_plan"]["plan_status"] == "ready"
    assert dashboard["primary_next_action_id"] == "ask_with_selected_llm"
    assert dashboard["primary_next_action_title"] == "Ask using selected LLM"


def test_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/models/dashboard")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _select(workspace_id: str, provider: str, model: str, model_type: str):
    return client.put(
        f"/workspaces/{workspace_id}/models/selection",
        json={
            "provider": provider,
            "model": model,
            "model_type": model_type,
            "selected_reason": "Models dashboard test selection.",
        },
    )


def _create_indexed_workspace(project_path: Path) -> dict:
    (project_path / "README.md").write_text(
        "# Models dashboard\n\nmodelsdashboardtoken provides context.",
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
            "name": "Workspace Models Dashboard",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
