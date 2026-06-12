from fastapi.testclient import TestClient

from app.main import app


def test_packaged_app_frontend_bootstrap_endpoint_reports_ready_contract() -> None:
    client = TestClient(app)

    response = client.get("/runtime/packaged-app-frontend-bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["milestone"] == "Task 260 — packaged app frontend starts app-owned backend"
    assert "did not invoke the Tauri app-owned backend startup" in payload["root_cause"]
    item_ids = {item["id"] for item in payload["readiness_items"]}
    assert "tauri-runtime-helper" in item_ids
    assert "app-bootstrap-before-load" in item_ids
    assert "health-readiness" in item_ids
    commands = {item["command"] for item in payload["validation_commands"]}
    assert "scripts/check_packaged_app_frontend_bootstrap.sh" in commands


def test_packaged_app_frontend_bootstrap_source_files_contain_required_hooks() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    app_tsx = (root / "frontend/src/App.tsx").read_text(encoding="utf-8")
    helper = (root / "frontend/src/desktopRuntime.ts").read_text(encoding="utf-8")
    lib_rs = (root / "frontend/src-tauri/src/lib.rs").read_text(encoding="utf-8")

    assert "ensureAppOwnedBackendRuntime" in app_tsx
    assert "startDesktopRuntimeAndLoadWorkspaces" in app_tsx
    assert "__TAURI__" in helper
    assert "start_app_owned_backend_runtime" in helper
    assert "start_app_owned_backend_runtime" in lib_rs
    assert "GET /health HTTP/1.1" in lib_rs
