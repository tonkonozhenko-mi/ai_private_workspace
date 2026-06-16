from fastapi.testclient import TestClient

from app.main import app


def test_staged_backend_runtime_contract_exposes_practical_runtime_staging() -> None:
    client = TestClient(app)

    response = client.get("/runtime/staged-backend-runtime-contract")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "source_runtime_staging_ready"
    assert body["staging_script"] == "scripts/stage_backend_runtime.sh"
    assert body["check_script"] == "scripts/check_staged_backend_runtime.sh"
    assert body["staging_directory"] == "build/desktop/backend-runtime"
    assert body["manifest_path"].endswith("AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json")
    assert any(
        item["id"] == "frozen-binary" and item["status"] == "future" for item in body["items"]
    )
    assert any("does not start the backend" in rule for rule in body["safety_rules"])
    assert any("must not be committed" in rule for rule in body["safety_rules"])
    assert any(
        command["command"] == "scripts/stage_backend_runtime.sh"
        for command in body["validation_commands"]
    )
