from fastapi.testclient import TestClient

from app.main import app


def test_ollama_model_recommendations_are_human_readable_and_safe() -> None:
    response = TestClient(app).get("/models/ollama-recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Ollama model recommendations"
    assert body["default_profile_id"] == "balanced_mac"
    assert len(body["roles"]) >= 2
    assert any(role["model_type"] == "llm" for role in body["roles"])
    assert any(role["model_type"] == "embedding" for role in body["roles"])
    assert any(profile["id"] == "balanced_mac" for profile in body["profiles"])
    assert any("frontend never runs" in note.lower() for note in body["safety_notes"])
