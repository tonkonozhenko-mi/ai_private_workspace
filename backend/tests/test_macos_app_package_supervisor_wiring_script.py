from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "package_macos_app_foundation.sh"


def test_macos_package_launcher_is_wired_to_supervisor_contract() -> None:
    content = SCRIPT.read_text()

    assert "macos-app-launcher.log" in content
    assert "backend.pid" in content
    assert "health_ready" in content
    assert "port_busy" in content
    assert "Refusing to kill an unknown process" in content
    assert "AI_WORKSPACE_APP_DATA_DIR" in content
    assert "python3 -m uvicorn app.main:app --host" in content


def test_macos_package_script_excludes_runtime_data() -> None:
    content = SCRIPT.read_text()

    assert "--exclude '.ai-workbench/'" in content
    assert "--exclude '*.db'" in content
    assert "--exclude '*.sqlite'" in content
    assert "--exclude '.venv/'" in content
