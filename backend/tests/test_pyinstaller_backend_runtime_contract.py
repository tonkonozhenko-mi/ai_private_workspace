from fastapi.testclient import TestClient

from app.main import app


def test_pyinstaller_backend_runtime_contract_exposes_frozen_runtime_poc() -> None:
    client = TestClient(app)

    response = client.get("/runtime/pyinstaller-backend-runtime-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pyinstaller_poc_ready"
    assert body["builder"] == "PyInstaller"
    assert body["build_script"] == "scripts/build_pyinstaller_backend_runtime.sh"
    assert body["check_script"] == "scripts/check_pyinstaller_backend_runtime.sh"
    assert body["entrypoint_path"] == "backend/packaging/pyinstaller_backend_entrypoint.py"
    assert body["spec_path"] == "backend/packaging/ai_private_workspace_backend.spec"
    assert body["frozen_runtime_dir"] == "build/desktop/frozen-backend-runtime"
    assert any(
        item["id"] == "frozen-manifest" and item["status"] in {"ready_after_command", "ok"}
        for item in body["items"]
    )
    assert any("open-source" in rule for rule in body["runtime_contract"])
    assert any(
        "Frontend still cannot execute shell commands" in rule for rule in body["safety_rules"]
    )
    assert any(
        command["command"] == "scripts/check_pyinstaller_backend_runtime.sh"
        for command in body["validation_commands"]
    )
