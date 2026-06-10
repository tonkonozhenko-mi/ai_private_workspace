from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_macos_launcher_exists_and_is_safe_copy_explicit() -> None:
    launcher = PROJECT_ROOT / "scripts" / "launch_macos.command"

    assert launcher.exists()
    assert launcher.stat().st_mode & 0o111

    content = launcher.read_text()
    assert "Start AI Private Workspace now?" in content
    assert "start_backend.sh" in content
    assert "start_frontend.sh" in content
    assert "does not pull models" in content
    assert "does not scan" in content
    assert "does not run MCP tools" in content
    assert "npm ci" in content
    assert "pip install -r requirements.txt" in content

    forbidden_auto_actions = [
        "ollama pull",
        "/scan",
        "/index",
        "git pull",
    ]
    for forbidden in forbidden_auto_actions:
        assert forbidden not in content


def test_macos_launcher_documentation_exists() -> None:
    doc = PROJECT_ROOT / "docs" / "MACOS_LAUNCHER.md"

    assert doc.exists()
    content = doc.read_text()
    assert "scripts/launch_macos.command" in content
    assert "does not pull Ollama models" in content
    assert "does not scan or index projects" in content
    assert "Finder shortcut" in content
