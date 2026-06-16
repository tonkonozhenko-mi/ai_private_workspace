from fastapi.testclient import TestClient

from app.main import app


def test_packaged_app_frontend_bootstrap_endpoint_reports_ready_contract() -> None:
    client = TestClient(app)

    response = client.get("/runtime/packaged-app-frontend-bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert (
        payload["milestone"]
        == "Task 261 — packaged app Tauri invoke bridge and npm supply-chain policy"
    )
    assert "did not enable the global bridge" in payload["root_cause"]
    item_ids = {item["id"] for item in payload["readiness_items"]}
    assert "tauri-runtime-helper" in item_ids
    assert "app-bootstrap-before-load" in item_ids
    assert "health-readiness" in item_ids
    assert "tauri-global-bridge-enabled" in item_ids
    assert "npm-allow-scripts-policy" in item_ids
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
    tauri_conf = (root / "frontend/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    package_json = (root / "frontend/package.json").read_text(encoding="utf-8")

    assert "__TAURI__" in helper
    assert "__TAURI_INTERNALS__" in helper
    assert "tauriBridgeDiagnostic" in helper
    assert "start_app_owned_backend_runtime" in helper
    assert '"withGlobalTauri": true' in tauri_conf
    assert '"allowScripts"' in package_json
    assert '"esbuild": true' in package_json
    assert '"fsevents": true' in package_json
    assert "start_app_owned_backend_runtime" in lib_rs
    assert "GET /health HTTP/1.1" in lib_rs
