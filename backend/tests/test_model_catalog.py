from fastapi.testclient import TestClient

from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.core.use_cases.recommend_models import (
    RecommendModelsInput,
    RecommendModelsUseCase,
)
from app.main import app


client = TestClient(app)


def test_list_catalog_returns_llm_and_embedding_models() -> None:
    response = client.get("/models/catalog")

    assert response.status_code == 200
    models = response.json()
    assert {model["model_type"] for model in models} == {"llm", "embedding"}
    assert {
        "ollama-llama3.2",
        "ollama-qwen2.5-coder",
        "ollama-mistral",
        "fake-llm",
        "ollama-nomic-embed-text",
        "fake-embedding",
    } == {model["id"] for model in models}


def test_list_catalog_filters_by_model_type() -> None:
    response = client.get("/models/catalog", params={"model_type": "embedding"})

    assert response.status_code == 200
    assert {model["model_type"] for model in response.json()} == {"embedding"}


def test_list_catalog_filters_by_provider() -> None:
    response = client.get("/models/catalog", params={"provider": "fake"})

    assert response.status_code == 200
    assert {model["provider"] for model in response.json()} == {"fake"}


def test_list_catalog_filters_by_assistant_profile() -> None:
    response = client.get(
        "/models/catalog",
        params={"assistant_profile_id": "documentation"},
    )

    assert response.status_code == 200
    model_ids = {model["id"] for model in response.json()}
    assert "ollama-llama3.2" in model_ids
    assert "ollama-mistral" in model_ids
    assert "ollama-qwen2.5-coder" not in model_ids


def test_recommend_llm_for_balanced_devops_prefers_code_oriented_models() -> None:
    response = _recommend("devops", "balanced", "workspace_ask", "llm")

    assert response.status_code == 200
    result = response.json()
    recommendation_ids = [
        recommendation["model"]["id"] for recommendation in result["recommendations"]
    ]
    assert recommendation_ids[:2] == [
        "ollama-qwen2.5-coder",
        "ollama-llama3.2",
    ]
    assert {
        recommendation["model"]["model_type"]
        for recommendation in result["recommendations"]
    } == {"llm"}
    assert not any(
        "does not match requested type" in warning
        for recommendation in result["recommendations"]
        for warning in recommendation["warnings"]
    )
    assert result["recommendations"][0]["score"] == 90


def test_recommend_embedding_for_balanced_profile_includes_nomic_first() -> None:
    response = _recommend("developer", "balanced", "context_search", "embedding")

    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    assert recommendations[0]["model"]["id"] == "ollama-nomic-embed-text"
    assert recommendations[0]["model"]["embedding_dimension"] == 768
    assert {
        recommendation["model"]["model_type"] for recommendation in recommendations
    } == {"embedding"}


def test_recommendation_returns_empty_when_catalog_has_no_matching_model_type() -> None:
    llm_models = [
        model
        for model in ModelCatalogRegistry().list_models()
        if model.model_type == "llm"
    ]
    use_case = RecommendModelsUseCase(
        model_catalog_registry=ModelCatalogRegistry(models=llm_models)
    )

    result = use_case.execute(
        RecommendModelsInput(
            assistant_profile_id="devops",
            laptop_profile_id="balanced",
            task_type="context_search",
            model_type="embedding",
        )
    )

    assert result.recommendations == []


def test_low_power_recommendation_prefers_fake_model_and_includes_warnings() -> None:
    response = _recommend("developer", "low_power", "workspace_ask", "llm")

    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    assert recommendations[0]["model"]["id"] == "fake-llm"
    assert any(
        "development/testing only" in warning
        for warning in recommendations[0]["warnings"]
    )
    qwen = _recommendation(recommendations, "ollama-qwen2.5-coder")
    assert any("heavy for low-power laptops" in warning for warning in qwen["warnings"])


def test_invalid_assistant_profile_returns_400() -> None:
    response = _recommend("missing-profile", "balanced", "workspace_ask", "llm")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown assistant profile: missing-profile"


def test_invalid_laptop_profile_returns_400() -> None:
    response = _recommend("devops", "missing-laptop", "workspace_ask", "llm")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown laptop profile: missing-laptop"


def test_invalid_model_type_returns_400() -> None:
    response = _recommend("devops", "balanced", "workspace_ask", "reranker")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown model type: reranker"


def test_catalog_and_recommendation_do_not_mutate_workspaces() -> None:
    before = client.get("/workspaces").json()

    assert client.get("/models/catalog").status_code == 200
    assert _recommend("devops", "balanced", "workspace_ask", "llm").status_code == 200

    assert client.get("/workspaces").json() == before


def _recommend(
    assistant_profile_id: str,
    laptop_profile_id: str,
    task_type: str,
    model_type: str,
):
    return client.post(
        "/models/recommend",
        json={
            "assistant_profile_id": assistant_profile_id,
            "laptop_profile_id": laptop_profile_id,
            "task_type": task_type,
            "model_type": model_type,
        },
    )


def _recommendation(recommendations: list[dict], model_id: str) -> dict:
    return next(
        recommendation
        for recommendation in recommendations
        if recommendation["model"]["id"] == model_id
    )


def test_agent_capabilities_rank_planning_models_and_keep_execution_manual() -> None:
    response = client.get("/models/agent-capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["safety_note"].startswith("Current agent mode is planning-only")
    models = {(model["provider"], model["model"]): model for model in payload["models"]}
    qwen = models[("ollama", "qwen2.5-coder")]
    assert qwen["planning_supported"] is True
    assert qwen["safe_execution_supported"] is False
    assert "safe_planning" in qwen["supported_agent_modes"]
    fake = models[("fake", "fake-llm")]
    assert fake["readiness"] == "demo_only"


def test_agent_planning_preview_is_review_only() -> None:
    response = client.post(
        "/models/agent-planning-preview",
        json={
            "goal": "Inspect the project, propose deployment checks, re-check, then continue.",
            "provider": "ollama",
            "model": "qwen2.5-coder",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_mode"] == "safe_planning_only"
    assert payload["readiness"] in {"planning_ready", "agent_ready"}
    assert len(payload["steps"]) >= 4
    assert "Automatic shell execution" in payload["unsupported_actions"]
    assert "does not execute the plan" in payload["safety_note"]
