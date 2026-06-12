from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_macos_packaged_app_smoke_result_endpoint() -> None:
    response = TestClient(app).get("/runtime/macos-packaged-app-smoke-result")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["check_script"] == "scripts/check_macos_packaged_app_smoke_result.sh"
    assert payload["packaged_app_path"].endswith("AI Private Workspace.app")
    assert any(item["id"] == "frozen-backend-smoke" and item["status"] == "ok" for item in payload["local_results"])
    assert any(item["id"] == "tauri-packaged-build" and item["status"] == "ok" for item in payload["local_results"])
    assert any("/health" in rule for rule in payload["safety_rules"])


def test_pyinstaller_runtime_check_accepts_current_entrypoint() -> None:
    script = (ROOT / "scripts/check_pyinstaller_backend_runtime.sh").read_text(encoding="utf-8")
    entrypoint = (ROOT / "backend/packaging/pyinstaller_backend_entrypoint.py").read_text(encoding="utf-8")

    assert "from app.main import app" in entrypoint
    assert "uvicorn.run(app" in entrypoint
    assert "from app.main import app" in script
    assert "uvicorn.run(app" in script
    assert "allowed generated locations" in script
    assert "frontend/src-tauri/target" in script


def test_macos_packaged_app_smoke_result_check_script() -> None:
    script = ROOT / "scripts/check_macos_packaged_app_smoke_result.sh"
    text = script.read_text(encoding="utf-8")

    assert script.exists()
    assert "AI Private Workspace.app" in text
    assert "Application startup complete" in text
    assert "Resources/frozen-backend-runtime" in text
    assert "GET /health HTTP/1.1" in text
