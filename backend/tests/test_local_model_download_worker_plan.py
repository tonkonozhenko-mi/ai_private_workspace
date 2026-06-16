from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_local_model_download_worker_plan_is_design_only() -> None:
    response = client.get("/models/local-download-worker-plan")

    assert response.status_code == 200
    plan = response.json()
    assert plan["status"] == "design_ready"
    assert plan["worker_enabled"] is False
    assert plan["execution_mode"] == "backend_only_after_explicit_approval"
    assert plan["approved_command_pattern"] == "ollama pull <catalog-model-name>"
    assert plan["allowed_provider"] == "ollama"
    assert any(guardrail["id"] == "no_frontend_shell" for guardrail in plan["guardrails"])
    assert any(step["id"] == "draft" and step["status"] == "implemented" for step in plan["steps"])
    assert any(step["id"] == "execute" and step["status"] == "planned" for step in plan["steps"])
