from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_delete_installed_model_is_gated_when_execution_disabled() -> None:
    # The deterministic test runtime keeps MODEL_DOWNLOAD_EXECUTION_ENABLED off,
    # so model management (including delete) must be refused before any Ollama call.
    response = client.post(
        "/models/local-install/delete",
        json={"name": "llama3.2:latest"},
    )
    assert response.status_code == 403


def test_delete_installed_model_requires_a_name() -> None:
    response = client.post("/models/local-install/delete", json={"name": ""})
    assert response.status_code == 422
