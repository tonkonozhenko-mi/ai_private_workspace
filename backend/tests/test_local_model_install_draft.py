from fastapi.testclient import TestClient

from app.api.routes import models as model_routes
from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.main import app

client = TestClient(app)


def test_local_model_install_draft_records_intent_without_execution(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.post(
        "/models/local-install-drafts",
        json={
            "workspace_id": workspace["id"],
            "provider": "ollama",
            "model": "nomic-embed-text",
            "model_type": "embedding",
        },
    )

    assert response.status_code == 201
    draft = response.json()
    assert draft["workspace_id"] == workspace["id"]
    assert draft["command"] == "ollama pull nomic-embed-text"
    assert draft["approval_required"] is True
    assert draft["execution_supported"] is False
    assert draft["status"] == "draft_created"
    assert draft["command_proposal"]["status"] == "pending"
    assert draft["command_proposal"]["policy_allowed"] is False
    assert draft["command_proposal"]["policy_mode"] == "manual_only"
    assert "does not download" in draft["safety_summary"]


def test_local_model_install_draft_registers_custom_ollama_model(
    tmp_path,
    monkeypatch,
) -> None:
    registry = ModelCatalogRegistry()
    monkeypatch.setattr(model_routes, "model_catalog_registry", registry)
    workspace = _create_workspace(tmp_path)

    response = client.post(
        "/models/local-install-drafts",
        json={
            "workspace_id": workspace["id"],
            "provider": "ollama",
            "model": "not-in-catalog",
            "model_type": "llm",
        },
    )

    assert response.status_code == 201
    assert response.json()["command"] == "ollama pull not-in-catalog"
    catalog = client.get("/models/catalog?provider=ollama&model_type=llm").json()
    assert "not-in-catalog" in {model["model_name"] for model in catalog}


def test_local_model_install_draft_rejects_unknown_workspace() -> None:
    response = client.post(
        "/models/local-install-drafts",
        json={
            "workspace_id": "missing-workspace",
            "provider": "ollama",
            "model": "llama3.2",
            "model_type": "llm",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _create_workspace(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "main.tf").write_text('resource "null_resource" "x" {}')
    response = client.post(
        "/workspaces",
        json={
            "name": "Model Install Draft Workspace",
            "project_path": str(project_dir),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
