from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_first_launch_readiness_is_read_only_and_packaging_ready() -> None:
    response = client.get("/runtime/first-launch-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "review", "blocked"}
    assert body["checklist"]
    item_ids = {item["id"] for item in body["checklist"]}
    assert {
        "backend-runtime",
        "workspace-data",
        "local-ai-models",
        "search-context-store",
        "macos-launcher",
        "desktop-shortcut",
    }.issubset(item_ids)
    assert "read-only" in body["safety_note"].lower()
    assert "never installs models" in body["safety_note"].lower()
    assert any("launch_macos.command" in command["command"] for command in body["copy_commands"])
    assert any(
        "create_macos_shortcut.sh" in command["command"] for command in body["copy_commands"]
    )
