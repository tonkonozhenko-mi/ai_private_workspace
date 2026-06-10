from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_mcp_catalog_lists_safe_templates() -> None:
    response = client.get("/mcp/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["safety_note"].startswith("MCP servers can expose powerful")
    template_ids = {template["id"] for template in payload["templates"]}
    assert "filesystem-readonly" in template_ids
    assert "git-readonly" in template_ids
    assert "shell-proposed-commands" in template_ids
    filesystem = next(template for template in payload["templates"] if template["id"] == "filesystem-readonly")
    assert filesystem["risk_level"] == "read_only"
    assert "read_file" in filesystem["example_tools"]


def test_mcp_config_preview_is_disabled_by_default() -> None:
    response = client.post(
        "/mcp/config-preview",
        json={
            "template_id": "filesystem-readonly",
            "workspace_id": "workspace-1",
            "project_path": "/tmp/project",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["allowed_by_default"] is False
    assert payload["env"]["PROJECT_PATH"] == "/tmp/project"
    server = payload["config_json"]["mcpServers"]["filesystem-readonly"]
    assert server["disabled"] is True
    assert server["riskLevel"] == "read_only"
    assert "The frontend never starts MCP servers or executes tools." in payload["guardrails"]


def test_mcp_connection_check_is_manual_copy_only() -> None:
    response = client.post(
        "/mcp/connection-check",
        json={"template_id": "git-readonly"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "manual_check_required"
    assert payload["copy_commands"]
    assert payload["safety_note"].startswith("This is a copy-only")


def test_mcp_config_preview_unknown_template_returns_404() -> None:
    response = client.post(
        "/mcp/config-preview",
        json={"template_id": "missing-template"},
    )

    assert response.status_code == 404


def _create_workspace_for_mcp() -> str:
    response = client.post(
        "/workspaces",
        json={
            "name": "MCP Workspace",
            "project_path": "/tmp/mcp-workspace",
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_workspace_mcp_config_can_be_saved_reviewed_and_listed() -> None:
    workspace_id = _create_workspace_for_mcp()

    create_response = client.post(
        f"/mcp/workspaces/{workspace_id}/configs",
        json={"template_id": "filesystem-readonly", "project_path": "/tmp/mcp-workspace"},
    )

    assert create_response.status_code == 200
    config = create_response.json()
    assert config["workspace_id"] == workspace_id
    assert config["enabled"] is False
    assert config["reviewed"] is False
    assert config["status"] == "disabled"
    assert "read_file" in config["available_tools"]

    preview_response = client.post(
        f"/mcp/workspaces/{workspace_id}/configs/{config['id']}/approval-preview",
        json={"approved_tools": ["read_file", "list_directory"]},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["approved_tools"] == ["read_file", "list_directory"]
    assert preview["safety_note"].startswith("Approval stores intent")

    update_response = client.patch(
        f"/mcp/workspaces/{workspace_id}/configs/{config['id']}",
        json={"enabled": True, "reviewed": True, "approved_tools": ["read_file", "list_directory"]},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["enabled"] is True
    assert updated["reviewed"] is True
    assert updated["status"] == "ready_for_planning"
    assert updated["approved_tools_count"] == 2

    inventory_response = client.get(f"/mcp/workspaces/{workspace_id}/tool-inventory")
    assert inventory_response.status_code == 200
    inventory = inventory_response.json()
    assert inventory["agent_readiness"] == "planning_ready"
    assert inventory["approved_tools_count"] == 2
    assert any(tool["tool"] == "read_file" and tool["status"] == "approved" for tool in inventory["tools"])

    list_response = client.get(f"/mcp/workspaces/{workspace_id}/configs")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["items"]] == [config["id"]]


def test_workspace_mcp_config_rejects_unknown_workspace() -> None:
    response = client.post(
        "/mcp/workspaces/missing/configs",
        json={"template_id": "filesystem-readonly"},
    )

    assert response.status_code == 404
