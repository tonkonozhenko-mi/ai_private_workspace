from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_tauri_shell_scaffold_endpoint_is_read_only_and_safe() -> None:
    response = client.get("/runtime/tauri-shell-scaffold")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "scaffolded"
    assert payload["shell_path"] == "frontend/src-tauri"
    assert payload["scaffold_script"] == "scripts/prepare_tauri_shell_scaffold.sh"
    assert any(
        "Frontend React code still never executes shell commands" in rule
        for rule in payload["safety_rules"]
    )
    assert any("Model downloads remain backend-side" in rule for rule in payload["safety_rules"])
    assert any(
        file["path"] == "frontend/src-tauri/tauri.conf.json" for file in payload["generated_files"]
    )
    assert "final signed" in " ".join(payload["known_limitations"])


def test_tauri_shell_scaffold_is_documented_in_openapi() -> None:
    assert "/runtime/tauri-shell-scaffold" in app.openapi()["paths"]
