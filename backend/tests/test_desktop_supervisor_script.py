from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "desktop_supervisor_contract.sh"


def test_desktop_supervisor_script_exists_and_is_safe_bridge():
    assert SCRIPT.exists()
    content = SCRIPT.read_text(encoding="utf-8")
    assert "127.0.0.1" in content
    assert "/health" in content
    assert "BACKEND_PID" in content
    assert "desktop-supervisor.log" in content
    assert "backend.log" in content
    assert "MODEL_DOWNLOAD_EXECUTION_ENABLED" not in content
    assert "ollama pull" not in content
    assert "pkill" not in content
    assert "kill -9" not in content
    assert 'kill "$BACKEND_PID"' in content
