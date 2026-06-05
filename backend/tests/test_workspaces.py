from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_list_and_get_workspace() -> None:
    payload = {
        "name": "Example Workspace",
        "project_path": "/tmp/example-project",
        "assistant_mode": "local",
        "privacy_mode": "private",
    }

    create_response = client.post("/workspaces", json=payload)

    assert create_response.status_code == 201
    created_workspace = create_response.json()
    assert created_workspace["id"]
    assert created_workspace["name"] == payload["name"]
    assert created_workspace["project_path"] == payload["project_path"]
    assert created_workspace["assistant_mode"] == payload["assistant_mode"]
    assert created_workspace["privacy_mode"] == payload["privacy_mode"]
    assert created_workspace["created_at"]

    list_response = client.get("/workspaces")

    assert list_response.status_code == 200
    workspace_ids = {workspace["id"] for workspace in list_response.json()}
    assert created_workspace["id"] in workspace_ids

    get_response = client.get(f"/workspaces/{created_workspace['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == created_workspace


def test_get_missing_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"
