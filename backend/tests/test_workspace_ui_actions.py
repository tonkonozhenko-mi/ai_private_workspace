from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_catalog_returns_expected_read_and_write_actions(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    timeline_before = client.get(f"/workspaces/{workspace['id']}/timeline").json()

    response = client.get(f"/workspaces/{workspace['id']}/ui-actions")

    assert response.status_code == 200
    catalog = response.json()
    actions = _actions_by_id(catalog)
    assert catalog["workspace_id"] == workspace["id"]
    assert {
        "scan_project",
        "index_workspace",
        "project_overview",
        "ask_workspace",
        "ask_selected_llm",
        "models_dashboard",
        "models_dashboard_summary",
        "model_selection",
        "model_usage_plan",
        "local_ai_activation_guide",
        "command_suggestions",
        "timeline",
    } == set(actions)
    assert actions["scan_project"]["method"] == "POST"
    assert actions["scan_project"]["mutates_data"] is True
    assert actions["ask_workspace"]["mutates_data"] is True
    assert actions["models_dashboard"]["mutates_data"] is False
    assert actions["timeline"]["endpoint"].endswith("/timeline?limit=20")
    assert client.get(f"/workspaces/{workspace['id']}/timeline").json() == timeline_before


def test_new_workspace_recommends_scan_and_blocks_index_and_ask(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    catalog = client.get(f"/workspaces/{workspace['id']}/ui-actions").json()
    actions = _actions_by_id(catalog)

    assert catalog["primary_action_id"] == "scan_project"
    assert actions["scan_project"]["status"] == "recommended"
    assert actions["scan_project"]["is_primary"] is True
    assert actions["index_workspace"]["status"] == "blocked"
    assert actions["ask_workspace"]["status"] == "blocked"
    assert actions["project_overview"]["status"] == "blocked"
    assert actions["command_suggestions"]["status"] == "blocked"


def test_selected_supported_llm_makes_ask_selected_available(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert (
        _select(
            workspace["id"],
            provider="fake",
            model="fake-llm",
            model_type="llm",
        ).status_code
        == 200
    )

    catalog = client.get(f"/workspaces/{workspace['id']}/ui-actions").json()
    actions = _actions_by_id(catalog)

    assert actions["ask_workspace"]["status"] == "blocked"
    assert actions["ask_selected_llm"]["status"] == "available"
    assert actions["ask_selected_llm"]["endpoint"] == (
        f"/workspaces/{workspace['id']}/ask-selected"
    )


def test_local_ai_activation_guide_is_recommended_when_model_setup_needed(
    tmp_path,
) -> None:
    workspace = _create_workspace(tmp_path)

    actions = _actions_by_id(client.get(f"/workspaces/{workspace['id']}/ui-actions").json())

    assert actions["local_ai_activation_guide"]["status"] == "recommended"
    assert actions["local_ai_activation_guide"]["mutates_data"] is False


def test_embedding_restart_need_overrides_generic_ask_primary_action(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    assert (
        _select(
            workspace["id"],
            provider="fake",
            model="fake-llm",
            model_type="llm",
        ).status_code
        == 200
    )
    assert (
        _select(
            workspace["id"],
            provider="ollama",
            model="nomic-embed-text",
            model_type="embedding",
        ).status_code
        == 200
    )

    catalog = client.get(f"/workspaces/{workspace['id']}/ui-actions").json()
    actions = _actions_by_id(catalog)

    assert catalog["primary_action_id"] == "local_ai_activation_guide"
    assert actions["local_ai_activation_guide"]["is_primary"] is True
    assert actions["local_ai_activation_guide"]["status"] == "recommended"
    assert actions["ask_workspace"]["is_primary"] is False


def test_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/ui-actions")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _actions_by_id(catalog: dict) -> dict[str, dict]:
    return {action["id"]: action for action in catalog["actions"]}


def _select(workspace_id: str, provider: str, model: str, model_type: str):
    return client.put(
        f"/workspaces/{workspace_id}/models/selection",
        json={
            "provider": provider,
            "model": model,
            "model_type": model_type,
            "selected_reason": "Workspace UI action catalog test.",
        },
    )


def _create_indexed_workspace(project_path: Path) -> dict:
    (project_path / "README.md").write_text(
        "# UI Actions\n\nIndexed UI action context.",
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
            "name": "Workspace UI Actions",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
