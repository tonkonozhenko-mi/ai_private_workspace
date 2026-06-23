from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_guided_model_setup_returns_recommended_defaults(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/models/setup-guide")

    assert response.status_code == 200
    guide = response.json()
    assert guide["workspace_id"] == workspace["id"]
    assert guide["llm"]["model_type"] == "llm"
    assert guide["embedding"]["model_type"] == "embedding"
    assert guide["llm"]["options"][0]["model"] == "qwen3:4b"
    assert guide["llm"]["options"][0]["recommended"] is True
    assert guide["embedding"]["options"][0]["model"] == "nomic-embed-text"
    assert "does not install" in " ".join(guide["safety_notes"])
    assert "first launch" in " ".join(guide["packaging_notes"])


def test_guided_model_setup_rejects_unknown_workspace() -> None:
    response = client.get("/workspaces/missing-workspace/models/setup-guide")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _create_workspace(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "main.tf").write_text('resource "null_resource" "x" {}')
    response = client.post(
        "/workspaces",
        json={
            "name": "Guided Setup Workspace",
            "project_path": str(project_dir),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
