from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prepare_macos_backend_runtime.sh"
PACKAGE_SCRIPT = ROOT / "scripts" / "package_macos_app_foundation.sh"


def test_backend_runtime_prepare_script_generates_manifest_safely() -> None:
    content = SCRIPT.read_text()

    assert "AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.txt" in content
    assert "Requirements SHA256" in content
    assert "backend/.ai-workbench/" in content
    assert "*.db" in content
    assert "frontend/node_modules/" in content
    assert (
        "Runtime preparation does not start scan/index/rebuild/MCP/agent/model downloads" in content
    )


def test_macos_package_script_uses_runtime_manifest_preflight() -> None:
    content = PACKAGE_SCRIPT.read_text()

    assert "RUNTIME_MANIFEST" in content
    assert "prepare_macos_backend_runtime.sh" in content
    assert "AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.txt" in content
    assert 'cp "$RUNTIME_MANIFEST"' in content
