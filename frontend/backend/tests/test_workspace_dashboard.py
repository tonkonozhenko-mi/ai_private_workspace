from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_new_workspace_dashboard_returns_scan_as_primary_action(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/dashboard")

    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["workspace_id"] == workspace["id"]
    assert dashboard["workspace_name"] == workspace["name"]
    assert dashboard["assistant_mode"] == "devops"
    assert dashboard["status"] == "needs_setup"
    assert dashboard["primary_next_action_id"] == "scan_project"
    assert dashboard["primary_next_action_title"] == "Run project scan"
    assert dashboard["quick_start"]["status"] == "new"


def test_indexed_workspace_dashboard_returns_ask_as_primary_action(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "# Dashboard\n\nIndexed dashboard context.")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/dashboard")

    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["status"] == "ready"
    assert dashboard["quick_start"]["status"] == "indexed"
    assert dashboard["primary_next_action_id"] == "ask_first_question"
    assert dashboard["primary_next_action_title"] == "Ask first workspace question"
    assert dashboard["readiness"]["can_ask"] is True


def test_dashboard_includes_all_workspace_main_screen_sections(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/dashboard")

    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["summary"]["workspace_id"] == workspace["id"]
    assert dashboard["readiness"]["workspace_id"] == workspace["id"]
    assert dashboard["quick_start"]["workspace_id"] == workspace["id"]
    assert dashboard["assistant_recommendation"]["workspace_id"] == workspace["id"]
    assert dashboard["assistant_recommendation"]["profile"]["id"] == "devops"
    assert dashboard["runtime_health"]["status"] == "ok"
    assert dashboard["models_summary"]["workspace_id"] == workspace["id"]
    assert dashboard["models_summary"]["overall_status"] == "needs_model_selection"
    assert dashboard["models_summary"]["primary_next_action_id"] == "select_llm_model"
    assert dashboard["models_summary"]["selected_llm"] is None
    assert dashboard["models_summary"]["selected_embedding"] is None
    assert dashboard["models_summary"]["top_recommended_model"]
    assert dashboard["recent_events"]
    assert dashboard["recent_events"][0]["event_type"] == "workspace_created"
    assert len(dashboard["recent_events"]) <= 5


def test_dashboard_read_does_not_mutate_workspace_activity(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    workspace_id = workspace["id"]
    timeline_before = client.get(f"/workspaces/{workspace_id}/timeline").json()

    assert client.get(f"/workspaces/{workspace_id}/dashboard").status_code == 200

    assert client.get(f"/workspaces/{workspace_id}/timeline").json() == timeline_before
    assert client.get(f"/workspaces/{workspace_id}/commands").json() == []
    assert client.get(f"/workspaces/{workspace_id}/scan").status_code == 404
    assert client.get(f"/workspaces/{workspace_id}/index/status").json()["status"] == (
        "not_indexed"
    )


def test_dashboard_models_summary_reflects_selected_models(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/dashboard")

    assert response.status_code == 200
    models_summary = response.json()["models_summary"]
    assert models_summary["selected_llm"] == "fake/fake-llm"
    assert models_summary["selected_embedding"] is None
    assert models_summary["can_ask_with_selected_llm"] is True
    assert models_summary["primary_next_action_id"] == "select_embedding_model"


def test_dashboard_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/dashboard")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Dashboard Workspace",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()


def _select(workspace_id: str, provider: str, model: str, model_type: str):
    return client.put(
        f"/workspaces/{workspace_id}/models/selection",
        json={
            "provider": provider,
            "model": model,
            "model_type": model_type,
            "selected_reason": "Main dashboard models summary test.",
        },
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
