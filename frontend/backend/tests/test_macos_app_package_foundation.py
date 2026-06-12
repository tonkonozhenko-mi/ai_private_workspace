from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_macos_app_package_foundation_describes_double_click_bundle() -> None:
    response = client.get("/runtime/macos-app-package-foundation")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "foundation"
    assert body["app_bundle_name"] == "AI Private Workspace.app"
    assert body["build_script"] == "scripts/package_macos_app_foundation.sh"
    assert "double click" in body["package_goal"].lower()
    assert any("frontend/dist" in step for step in body["build_steps"])
    assert any("Runtime data is excluded" in rule for rule in body["safety_rules"])
    assert any(artifact["path"].endswith("Contents/Info.plist") for artifact in body["artifacts"])
    assert any("Tauri" in item for item in body["not_yet_included"])


def test_macos_app_package_foundation_keeps_execution_out_of_scope() -> None:
    response = client.get("/runtime/macos-app-package-foundation")

    assert response.status_code == 200
    body = response.json()
    safety_text = " ".join(body["safety_rules"]).lower()
    assert "model downloads" in safety_text
    assert "scan" in safety_text
    assert "mcp" in safety_text
    assert "build/" in safety_text
