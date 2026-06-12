from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_desktop_stack_contract.sh"


def test_desktop_stack_runtime_contract_locks_open_source_cross_platform_direction() -> None:
    response = client.get("/runtime/desktop-stack-runtime-contract")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted_for_v0.2"
    assert "Tauri" in payload["desktop_shell"]
    assert "macOS and Windows" in payload["summary"]
    assert any("open-source/free" in item for item in payload["stack_principles"])
    component_ids = {component["id"] for component in payload["selected_components"]}
    assert {"tauri", "react-vite", "fastapi", "sqlite-qdrant-ollama", "pyinstaller-first"}.issubset(component_ids)
    assert any("Electron" in item["title"] for item in payload["rejected_paths"])


def test_desktop_stack_runtime_contract_preserves_safety_rules() -> None:
    response = client.get("/runtime/desktop-stack-runtime-contract")

    assert response.status_code == 200
    payload = response.json()
    assert any("Frontend still cannot execute shell commands" in rule for rule in payload["safety_rules"])
    assert any("scan, index, rebuild, MCP, Agent, or model downloads" in rule for rule in payload["safety_rules"])
    assert any("only the staged app-owned backend runtime" in rule for rule in payload["staging_contract"])
    assert any(command["command"] == "scripts/check_desktop_stack_contract.sh" for command in payload["validation_commands"])


def test_desktop_stack_contract_script_is_static_and_safe() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert "AI Private Workspace desktop stack contract check" in content
    assert "/desktop-stack-runtime-contract" in content
    assert "backend_start_enabled: false" in content
    assert "uvicorn" not in content
    assert "ollama pull" not in content
    assert "npm run dev" not in content
