from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_windows_supervisor_contract_documents_safe_lifecycle() -> None:
    content = (ROOT / "scripts" / "windows_supervisor_contract.ps1").read_text()

    assert "LOCALAPPDATA" in content
    assert "127.0.0.1" in content
    assert "Do not kill unknown processes" in content
    assert "backend.pid" in content
    assert "windows-supervisor.log" in content
    assert "scan/index/rebuild/MCP/agent/model downloads" in content


def test_windows_package_foundation_manifest_excludes_runtime_data() -> None:
    content = (ROOT / "scripts" / "package_windows_app_foundation.ps1").read_text()

    assert "AI_PRIVATE_WORKSPACE_WINDOWS_PACKAGE_MANIFEST" in content
    assert "Excluded runtime/build data" in content
    assert "backend/.ai-workbench" in content
    assert "*.sqlite" in content
    assert "node_modules" in content


def test_windows_packaging_validation_helper_is_safe() -> None:
    content = (ROOT / "scripts" / "prepare_windows_packaging_foundation.sh").read_text()

    assert "windows_supervisor_contract.ps1" in content
    assert "package_windows_app_foundation.ps1" in content
    assert "PowerShell scripts are source-controlled contracts" in content
    assert "pwsh" not in content.lower()
    assert "powershell" not in content.lower().replace(
        "powershell scripts are source-controlled contracts", ""
    )
