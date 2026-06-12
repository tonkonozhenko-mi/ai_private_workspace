from fastapi.testclient import TestClient

from app.main import app


def test_windows_packaging_foundation_is_read_only() -> None:
    client = TestClient(app)

    response = client.get("/runtime/windows-packaging-foundation")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "foundation"
    assert body["app_data_directory"] == "%LOCALAPPDATA%\\AI Private Workspace"
    assert body["logs_directory"].endswith("\\logs")
    assert body["backend_health_url"] == "http://127.0.0.1:8000/health"
    assert any("Never kill unknown processes" in rule for rule in body["safety_rules"])
    assert any(script["path"] == "scripts/windows_supervisor_contract.ps1" for script in body["scripts"])
    assert any(phase["id"] == "installer" for phase in body["implementation_phases"])


def test_windows_packaging_foundation_is_in_openapi() -> None:
    assert "/runtime/windows-packaging-foundation" in app.openapi()["paths"]
