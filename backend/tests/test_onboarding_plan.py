from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_balanced_devops_local_only_recommends_qdrant_and_ollama() -> None:
    response = _create_plan("devops", "balanced")

    assert response.status_code == 200
    plan = response.json()
    assert plan["assistant_profile_id"] == "devops"
    assert plan["laptop_profile_id"] == "balanced"
    assert plan["privacy_mode"] == "local_only"
    assert plan["recommended_runtime"] == {
        "VECTOR_STORE": "qdrant",
        "EMBEDDING_PROVIDER": "ollama",
        "LLM_PROVIDER": "ollama",
    }
    assert plan["recommended_models"] == {
        "OLLAMA_EMBEDDING_MODEL": "nomic-embed-text",
        "OLLAMA_LLM_MODEL": "llama3.2",
    }
    assert _step(plan, "start_qdrant_if_needed")["status"] == "recommended"
    assert _step(plan, "start_ollama_if_needed")["status"] == "recommended"


def test_low_power_plan_recommends_lightweight_providers() -> None:
    response = _create_plan("developer", "low_power")

    assert response.status_code == 200
    plan = response.json()
    assert plan["recommended_runtime"] == {
        "VECTOR_STORE": "memory",
        "EMBEDDING_PROVIDER": "fake",
        "LLM_PROVIDER": "fake",
    }
    assert _step(plan, "start_qdrant_if_needed")["status"] == "optional"
    assert _step(plan, "start_ollama_if_needed")["status"] == "optional"
    assert any("real local AI can be enabled later" in note for note in plan["notes"])


def test_powerful_plan_recommends_stronger_coding_model() -> None:
    response = _create_plan("developer", "powerful")

    assert response.status_code == 200
    assert response.json()["recommended_models"]["OLLAMA_LLM_MODEL"] == "qwen2.5-coder"


def test_onboarding_plan_steps_include_scan_index_ask_and_readiness() -> None:
    response = _create_plan("documentation", "balanced")

    assert response.status_code == 200
    step_ids = {step["id"] for step in response.json()["steps"]}
    assert {
        "run_project_scan",
        "index_workspace",
        "ask_first_question",
        "review_readiness",
    }.issubset(step_ids)


def test_invalid_assistant_profile_returns_400() -> None:
    response = _create_plan("missing-profile", "balanced")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown assistant profile: missing-profile"


def test_invalid_laptop_profile_returns_400() -> None:
    response = _create_plan("devops", "missing-laptop")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown laptop profile: missing-laptop"


def test_onboarding_plan_does_not_create_workspace() -> None:
    before_response = client.get("/workspaces")
    assert before_response.status_code == 200
    before_ids = {workspace["id"] for workspace in before_response.json()}

    response = _create_plan("manager_summary", "balanced")

    assert response.status_code == 200
    after_response = client.get("/workspaces")
    assert after_response.status_code == 200
    assert {workspace["id"] for workspace in after_response.json()} == before_ids


def _create_plan(assistant_profile_id: str, laptop_profile_id: str):
    return client.post(
        "/onboarding/plan",
        json={
            "assistant_profile_id": assistant_profile_id,
            "laptop_profile_id": laptop_profile_id,
            "privacy_mode": "local_only",
        },
    )


def _step(plan: dict, step_id: str) -> dict:
    return next(step for step in plan["steps"] if step["id"] == step_id)
