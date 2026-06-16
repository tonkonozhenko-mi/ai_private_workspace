from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_backend_runtime_bundle_plan_is_read_only_and_safe() -> None:
    response = client.get("/runtime/backend-runtime-bundle-plan")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "planned-foundation"
    assert payload["build_script"] == "scripts/prepare_macos_backend_runtime.sh"
    assert payload["runtime_manifest_path"].endswith("AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.txt")
    assert any("No scan" in rule for rule in payload["safety_rules"])
    assert any("local python3" in limitation for limitation in payload["known_limitations"])
    assert any(
        step["command"] == "scripts/package_macos_app_foundation.sh"
        for step in payload["build_steps"]
    )


def test_backend_runtime_bundle_plan_documents_no_manual_venv_goal() -> None:
    response = client.get("/runtime/backend-runtime-bundle-plan")

    assert response.status_code == 200
    payload = response.json()
    assert "without asking the user to create a venv" in payload["package_goal"]
    assert any(item["id"] == "runtime-manifest" for item in payload["bundle_items"])
