from dataclasses import replace

from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.main import app

client = TestClient(app)


def test_model_download_execution_capability_is_disabled_by_default() -> None:
    response = client.get("/models/local-download-execution-capability")

    assert response.status_code == 200
    body = response.json()
    assert body["execution_enabled"] is False
    assert body["status"] == "disabled"
    assert "disabled by default" in body["disabled_reason"]


def test_model_download_run_is_blocked_when_execution_disabled(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    draft = client.post(
        "/models/local-install-drafts",
        json={
            "workspace_id": workspace["id"],
            "provider": "ollama",
            "model": "nomic-embed-text",
            "model_type": "embedding",
        },
    ).json()

    response = client.post(f"/models/local-install-drafts/{draft['command_proposal']['id']}/run")

    assert response.status_code == 400
    assert "disabled" in response.json()["detail"]


def test_model_download_run_rejects_unknown_command() -> None:
    response = client.post("/models/local-install-drafts/missing-command/run")

    assert response.status_code == 400
    assert "disabled" in response.json()["detail"]


def test_model_download_use_case_rejects_non_catalog_command(tmp_path) -> None:
    from app.api.dependencies import command_repository

    workspace = _create_workspace(tmp_path)
    draft = client.post(
        "/models/local-install-drafts",
        json={
            "workspace_id": workspace["id"],
            "provider": "ollama",
            "model": "nomic-embed-text",
            "model_type": "embedding",
        },
    ).json()
    command = command_repository.get(draft["command_proposal"]["id"])
    assert command is not None
    command_repository.update(replace(command, command="ollama pull not-in-catalog"))

    settings = get_settings()
    original = settings.MODEL_DOWNLOAD_EXECUTION_ENABLED
    original_runner = settings.COMMAND_RUNNER
    settings.MODEL_DOWNLOAD_EXECUTION_ENABLED = True
    settings.COMMAND_RUNNER = "local"
    try:
        response = client.post(
            f"/models/local-install-drafts/{draft['command_proposal']['id']}/run"
        )
    finally:
        settings.MODEL_DOWNLOAD_EXECUTION_ENABLED = original
        settings.COMMAND_RUNNER = original_runner

    assert response.status_code == 400
    assert "allowlist" in response.json()["detail"]


def _create_workspace(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "main.tf").write_text('resource "null_resource" "x" {}')
    response = client.post(
        "/workspaces",
        json={
            "name": "Model Download Execution Workspace",
            "project_path": str(project_dir),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
