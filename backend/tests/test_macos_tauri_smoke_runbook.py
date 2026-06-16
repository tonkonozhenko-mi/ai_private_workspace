from fastapi.testclient import TestClient

from app.main import app


def test_macos_tauri_smoke_runbook_endpoint_returns_safe_local_runbook() -> None:
    client = TestClient(app)

    response = client.get("/runtime/macos-tauri-smoke-runbook")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ready_for_local_macos_smoke", "blocked"}
    # Assert a runbook doc path is returned without hardcoding the exact
    # filename, so the doc can be renamed/removed without breaking this test.
    assert payload["runbook_doc"].endswith(".md")
    assert payload["check_script"] == "scripts/check_macos_tauri_smoke_runbook.sh"
    assert payload["platform"].startswith("macOS")
    assert any(step["id"] == "build-frozen-backend" for step in payload["smoke_steps"])
    assert any(step["id"] == "tauri-dev-smoke" for step in payload["smoke_steps"])
    assert any(
        "frontend" in rule.lower() and "shell" in rule.lower() for rule in payload["safety_rules"]
    )
    assert any("PID-owned" in rule for rule in payload["safety_rules"])
    assert any(
        command["command"] == "scripts/check_macos_tauri_smoke_runbook.sh"
        for command in payload["validation_commands"]
    )
