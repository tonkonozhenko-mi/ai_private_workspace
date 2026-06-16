from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_packaging_toolchain_prerequisites_contract() -> None:
    client = TestClient(app)

    response = client.get("/runtime/packaging-toolchain-prerequisites")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["check_script"] == "scripts/check_packaging_toolchain_prerequisites.sh"
    assert payload["pyinstaller_dependency"] == "pyinstaller>=6.0,<7.0"
    assert any("brew install rust" in option for option in payload["cargo_install_options"])
    item_ids = {item["id"] for item in payload["prerequisite_items"]}
    assert {"pyinstaller-dependency", "pyinstaller-spec-path", "tauri-cli", "cargo"}.issubset(
        item_ids
    )
    commands = {command["command"] for command in payload["validation_commands"]}
    assert "scripts/check_packaging_toolchain_prerequisites.sh" in commands
    assert "cd frontend && cargo check --manifest-path src-tauri/Cargo.toml" in commands
    assert any(
        "Frontend still cannot execute shell commands" in rule for rule in payload["safety_rules"]
    )


def test_pyinstaller_dependency_is_declared_for_local_build() -> None:
    requirements = Path(__file__).resolve().parents[1] / "requirements.txt"

    assert "pyinstaller>=6.0,<7.0" in requirements.read_text().lower()


def test_pyinstaller_spec_uses_spec_relative_entrypoint() -> None:
    spec = Path(__file__).resolve().parents[1] / "packaging" / "ai_private_workspace_backend.spec"
    text = spec.read_text()

    assert "SPECPATH" in text
    assert 'ENTRYPOINT = BACKEND_DIR / "packaging" / "pyinstaller_backend_entrypoint.py"' in text
    assert '["backend/packaging/pyinstaller_backend_entrypoint.py"]' not in text
