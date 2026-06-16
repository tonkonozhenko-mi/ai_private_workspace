from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_summary_returns_compact_fields_and_top_recommendation(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/models/dashboard/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["workspace_id"] == workspace["id"]
    assert summary["overall_status"] == "needs_model_selection"
    assert summary["primary_next_action_id"] == "select_llm_model"
    assert summary["primary_next_action_title"] == "Select an LLM model"
    assert summary["selected_llm"] is None
    assert summary["selected_embedding"] is None
    assert summary["active_llm"] == "fake/fake-llm"
    assert summary["active_embedding"] == "fake/fake-embedding"
    assert summary["can_ask_with_selected_llm"] is False
    assert summary["can_search_with_selected_embedding"] is False
    assert summary["selected_embedding_matches_active_runtime"] is False
    assert summary["embedding_index_status"] == "not_indexed"
    assert summary["embedding_plan_status"] == "not_selected"
    assert summary["top_recommended_model"] == "ollama/qwen2.5-coder"
    assert isinstance(summary["top_recommended_model_score"], int)
    assert summary["performance_models_count"] == 0
    assert summary["notes"] == [
        "Workspace models dashboard summary is read-only.",
        "Use the detailed workspace models dashboard for full diagnostics.",
    ]


def test_summary_formats_selected_models_and_ready_state(tmp_path) -> None:
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

    summary = client.get(f"/workspaces/{workspace['id']}/models/dashboard/summary").json()

    assert summary["overall_status"] == "ready"
    assert summary["primary_next_action_id"] == "ask_with_selected_llm"
    assert summary["selected_llm"] == "fake/fake-llm"
    assert summary["selected_embedding"] == "fake/fake-embedding"
    assert summary["can_ask_with_selected_llm"] is True
    assert summary["can_search_with_selected_embedding"] is True
    assert summary["selected_embedding_matches_active_runtime"] is True
    assert summary["embedding_index_status"] == "indexed"
    assert summary["embedding_plan_status"] == "ready"


def test_summary_distinguishes_selected_embedding_from_unbuilt_context(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
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

    summary = client.get(f"/workspaces/{workspace['id']}/models/dashboard/summary").json()

    assert summary["overall_status"] == "needs_context_index"
    assert summary["primary_next_action_id"] == "reindex_workspace"
    assert summary["primary_next_action_title"] == "Build context with selected search model"
    assert summary["selected_embedding_matches_active_runtime"] is True
    assert summary["embedding_index_status"] == "not_indexed"
    assert summary["embedding_plan_status"] == "needs_index"


def test_warnings_count_is_derived_from_detailed_dashboard(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200
    assert (
        _select(
            workspace["id"],
            "ollama",
            "nomic-embed-text",
            "embedding",
        ).status_code
        == 200
    )

    detailed = client.get(f"/workspaces/{workspace['id']}/models/dashboard").json()
    summary = client.get(f"/workspaces/{workspace['id']}/models/dashboard/summary").json()
    expected_warnings = (
        sum(
            len(recommendation["warnings"])
            for recommendation in detailed["recommendations"]["recommendations"]
        )
        + len(detailed["embedding_indexing_plan"]["warnings"])
        + sum(
            capability["status"] != "ready" for capability in detailed["usage_plan"]["capabilities"]
        )
    )

    assert summary["warnings_count"] == expected_warnings
    assert summary["warnings_count"] > 0


def test_summary_is_read_only_and_detailed_dashboard_still_works(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    timeline_before = client.get(f"/workspaces/{workspace['id']}/timeline").json()

    summary_response = client.get(f"/workspaces/{workspace['id']}/models/dashboard/summary")
    detailed_response = client.get(f"/workspaces/{workspace['id']}/models/dashboard")

    assert summary_response.status_code == 200
    assert detailed_response.status_code == 200
    detailed = detailed_response.json()
    assert "selection" in detailed
    assert "selection_status" in detailed
    assert "usage_plan" in detailed
    assert "embedding_indexing_plan" in detailed
    assert "recommendations" in detailed
    assert "performance_summary" in detailed
    assert client.get(f"/workspaces/{workspace['id']}/timeline").json() == timeline_before


def test_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/models/dashboard/summary")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _select(workspace_id: str, provider: str, model: str, model_type: str):
    return client.put(
        f"/workspaces/{workspace_id}/models/selection",
        json={
            "provider": provider,
            "model": model,
            "model_type": model_type,
            "selected_reason": "Models dashboard summary test.",
        },
    )


def _create_indexed_workspace(project_path: Path) -> dict:
    (project_path / "README.md").write_text(
        "# Models dashboard summary\n\nmodelssummarytoken provides context.",
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
            "name": "Workspace Models Dashboard Summary",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
