from fastapi.testclient import TestClient

import app.api.routes.models as models_route
from app.main import app


client = TestClient(app)


class FakeOllamaResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("bad status")

    def json(self) -> dict:
        return self.payload


def test_local_model_install_status_reports_installed_models(monkeypatch) -> None:
    def fake_get(url: str, timeout: int):
        assert url.endswith("/api/tags")
        return FakeOllamaResponse(
            {
                "models": [
                    {"name": "llama3.2:latest", "size": 2_000_000_000},
                    {"name": "nomic-embed-text:latest", "size": 300_000_000},
                ]
            }
        )

    monkeypatch.setattr(models_route.httpx, "get", fake_get)

    response = client.get("/models/local-install-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime_reachable"] is True
    assert payload["installed_count"] == 2
    statuses = {item["model"]: item["status"] for item in payload["items"]}
    assert statuses["llama3.2"] == "installed"
    assert statuses["nomic-embed-text"] == "installed"


def test_local_model_install_status_is_read_only_when_ollama_unreachable(monkeypatch) -> None:
    def fake_get(url: str, timeout: int):
        raise models_route.httpx.ConnectError("offline")

    monkeypatch.setattr(models_route.httpx, "get", fake_get)

    response = client.get("/models/local-install-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "runtime_unreachable"
    assert payload["runtime_reachable"] is False
    assert all(item["status"] == "unknown" for item in payload["items"])
    assert "never downloads" in " ".join(payload["safety_notes"]).lower()
