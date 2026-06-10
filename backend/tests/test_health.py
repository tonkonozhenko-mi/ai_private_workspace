from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_local_data_safety_reports_database_location() -> None:
    response = client.get("/runtime/local-data")

    assert response.status_code == 200
    body = response.json()
    assert body["repository"] in {"sqlite", "memory"}
    assert body["database_path"].endswith("workspaces.db")
    assert "backend/.ai-workbench" in body["safe_update_excludes"]
    assert "*.db" in body["safe_update_excludes"]
    assert isinstance(body["backup_hints"], list)



def test_startup_checklist_reports_read_only_steps() -> None:
    response = client.get("/runtime/startup-checklist")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "review", "blocked"}
    assert body["safe_to_continue"] in {True, False}
    assert "frontend only displays" in body["safety_note"].lower()
    item_ids = {item["id"] for item in body["items"]}
    assert {"python", "database", "local-data-protection", "models", "search-context"}.issubset(item_ids)
