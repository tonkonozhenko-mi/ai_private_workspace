from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_desktop_runtime_preflight.sh"


def test_desktop_runtime_preflight_endpoint_is_read_only_and_safe() -> None:
    response = client.get("/runtime/desktop-runtime-preflight")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Desktop runtime preflight"
    assert payload["preflight_script"] == "scripts/check_desktop_runtime_preflight.sh"
    assert payload["runtime_manifest_path"].endswith("AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.txt")
    assert any(item["id"] == "runtime-manifest" for item in payload["items"])
    assert any(command["command"] == "scripts/check_desktop_runtime_preflight.sh" for command in payload["validation_commands"])
    assert any("read-only" in rule.lower() for rule in payload["safety_rules"])
    assert any("Frontend can display and copy commands only" in rule for rule in payload["safety_rules"])


def test_desktop_runtime_preflight_documents_blockers_and_pass_criteria() -> None:
    response = client.get("/runtime/desktop-runtime-preflight")

    assert response.status_code == 200
    payload = response.json()
    assert any("Runtime manifest" in criterion for criterion in payload["pass_criteria"])
    assert any("Missing backend/app/main.py" in condition for condition in payload["fail_fast_conditions"])
    assert any("Tauri-side read-only supervisor" in step for step in payload["next_steps"])


def test_desktop_runtime_preflight_script_is_safe_static_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert "AI Private Workspace desktop runtime preflight" in content
    assert "stage_backend_runtime.sh" in content
    assert "npm ci && npm run build" in content
    assert "package_macos_app_foundation.sh" in content
    assert "staging does not scan, index, rebuild" in content
    assert "uvicorn" not in content
    assert "ollama pull" not in content
