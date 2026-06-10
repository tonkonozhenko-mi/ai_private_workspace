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
