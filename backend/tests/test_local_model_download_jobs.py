from time import sleep

from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.main import app


client = TestClient(app)


def test_model_download_job_is_blocked_when_execution_disabled(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    draft = _create_draft(workspace["id"])

    response = client.post(
        f"/models/local-install-drafts/{draft['command_proposal']['id']}/jobs"
    )

    assert response.status_code == 400
    assert "disabled" in response.json()["detail"]


def test_model_download_job_starts_background_status_and_finishes(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    draft = _create_draft(workspace["id"])

    settings = get_settings()
    original_enabled = settings.MODEL_DOWNLOAD_EXECUTION_ENABLED
    original_runner = settings.COMMAND_RUNNER
    settings.MODEL_DOWNLOAD_EXECUTION_ENABLED = True
    settings.COMMAND_RUNNER = "local"
    try:
        response = client.post(
            f"/models/local-install-drafts/{draft['command_proposal']['id']}/jobs"
        )
    finally:
        settings.MODEL_DOWNLOAD_EXECUTION_ENABLED = original_enabled
        settings.COMMAND_RUNNER = original_runner

    assert response.status_code == 202
    job = response.json()
    assert job["command_id"] == draft["command_proposal"]["id"]
    assert job["status"] in {"queued", "running", "succeeded"}
    assert job["command_proposal"]["policy_mode"] == "model_download_background_job"
    assert job["command_proposal"]["status"] == "approved"

    finished = _wait_for_job(job["id"])
    assert finished["status"] == "succeeded"
    assert finished["progress_percent"] == 100
    assert "Re-check installed models" in finished["progress_message"]
    assert finished["command_proposal"]["status"] == "executed"


def test_model_download_job_read_rejects_unknown_job() -> None:
    response = client.get("/models/local-download-jobs/missing-job")

    assert response.status_code == 404
    assert response.json()["detail"] == "Model download job not found"


def _wait_for_job(job_id: str):
    last = None
    for _ in range(30):
        read_response = client.get(f"/models/local-download-jobs/{job_id}")
        assert read_response.status_code == 200
        last = read_response.json()
        if last["status"] in {"succeeded", "failed"}:
            return last
        sleep(0.05)
    raise AssertionError(f"job did not finish: {last}")


def _create_draft(workspace_id: str):
    response = client.post(
        "/models/local-install-drafts",
        json={
            "workspace_id": workspace_id,
            "provider": "ollama",
            "model": "nomic-embed-text",
            "model_type": "embedding",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_workspace(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "main.tf").write_text('resource "null_resource" "x" {}')
    response = client.post(
        "/workspaces",
        json={
            "name": "Model Download Job Workspace",
            "project_path": str(project_dir),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
