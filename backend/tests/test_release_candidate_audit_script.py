from pathlib import Path


def test_release_candidate_audit_script_exists_and_is_safe():
    script = Path(__file__).resolve().parents[2] / "scripts" / "audit_release_candidate.sh"
    content = script.read_text()

    assert script.exists()
    assert "backend/.ai-workbench" in content
    assert "*.sqlite" in content
    assert "node_modules" in content
    assert "backend/.venv" in content
    assert "*.tsbuildinfo" in content
    assert "bash -n" in content
    assert "kill -9" not in content
    assert "rm -rf" not in content
