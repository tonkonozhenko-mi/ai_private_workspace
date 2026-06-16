from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_local_model_install_guide_is_manual_and_safe() -> None:
    response = client.get("/models/local-install-guide")

    assert response.status_code == 200
    guide = response.json()
    assert guide["status"] == "manual_install_required"
    assert guide["options"]
    assert any(option["install_command"].startswith("ollama pull ") for option in guide["options"])
    assert "frontend must not run shell commands" in " ".join(guide["safety_notes"]).lower()
    assert "Verify installed models" in " ".join(guide["next_steps"])


def test_local_model_install_guide_includes_llm_and_embedding_defaults() -> None:
    response = client.get("/models/local-install-guide")

    assert response.status_code == 200
    options = response.json()["options"]
    model_types = {option["model_type"] for option in options}
    assert "llm" in model_types
    assert "embedding" in model_types
