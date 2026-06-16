from fastapi.testclient import TestClient

from app.main import app


def test_macos_packaged_app_smoke_preflight_contract() -> None:
    client = TestClient(app)

    response = client.get("/runtime/macos-packaged-app-smoke-preflight")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ready_after_local_frozen_build", "ok"}
    assert payload["check_script"] == "scripts/check_macos_packaged_app_smoke_preflight.sh"
    assert payload["desktop_shell"] == "Tauri + React"
    item_ids = {item["id"] for item in payload["preflight_items"]}
    assert "tauri-cli-script" in item_ids
    assert "tauri-cli-lockfile" in item_ids
    assert "health-readiness" in item_ids
    commands = {command["command"] for command in payload["validation_commands"]}
    assert (
        "cd frontend && npm ci && npm run build && cargo check --manifest-path src-tauri/Cargo.toml && npm run tauri dev"
        in commands
    )
    assert any(
        "React/frontend does not execute shell commands" in rule for rule in payload["safety_rules"]
    )
