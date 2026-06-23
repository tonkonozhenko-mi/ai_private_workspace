import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.model_catalog.user_model_catalog_loader import UserModelCatalogLoader
from app.api.routes import models as model_routes
from app.config.settings import Settings
from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.main import app

client = TestClient(app)


def test_no_user_catalog_path_keeps_static_catalog() -> None:
    loaded = UserModelCatalogLoader("").load()
    registry = ModelCatalogRegistry(
        user_models=loaded.models,
        warnings=loaded.warnings,
    )

    assert Settings().USER_MODEL_CATALOG_PATH == ""
    assert loaded.models == []
    assert loaded.warnings == []
    assert len(registry.list_models()) == 9


def test_valid_user_model_appears_in_catalog(tmp_path, monkeypatch) -> None:
    path = _write_catalog(tmp_path, [_valid_user_llm()])
    _configure_route_catalog(monkeypatch, path)

    response = client.get("/models/catalog")

    assert response.status_code == 200
    assert "ollama-codellama" in {model["id"] for model in response.json()}


def test_valid_user_model_participates_in_recommendation(tmp_path, monkeypatch) -> None:
    path = _write_catalog(tmp_path, [_valid_user_llm()])
    _configure_route_catalog(monkeypatch, path)

    response = client.post(
        "/models/recommend",
        json={
            "assistant_profile_id": "developer",
            "laptop_profile_id": "powerful",
            "task_type": "workspace_ask",
            "model_type": "llm",
        },
    )

    assert response.status_code == 200
    assert "ollama-codellama" in {
        recommendation["model"]["id"] for recommendation in response.json()["recommendations"]
    }


def test_invalid_user_model_is_skipped_and_reported(tmp_path, monkeypatch) -> None:
    invalid_model = _valid_user_llm()
    invalid_model["model_type"] = "reranker"
    path = _write_catalog(tmp_path, [invalid_model])
    _configure_route_catalog(monkeypatch, path)

    details = client.get("/models/catalog/details").json()

    assert "ollama-codellama" not in {model["id"] for model in details["models"]}
    assert details["warnings"][0]["code"] == "invalid_user_model"
    assert "model_type" in details["warnings"][0]["message"]


def test_duplicate_user_model_id_is_skipped_with_warning(tmp_path, monkeypatch) -> None:
    duplicate = _valid_user_llm()
    duplicate["id"] = "ollama-llama3.2"
    path = _write_catalog(tmp_path, [duplicate])
    _configure_route_catalog(monkeypatch, path)

    details = client.get("/models/catalog/details").json()

    assert sum(model["id"] == "ollama-llama3.2" for model in details["models"]) == 1
    assert any(warning["code"] == "duplicate_model_id" for warning in details["warnings"])


def test_malformed_json_does_not_crash_catalog_details(tmp_path, monkeypatch) -> None:
    path = tmp_path / "models.json"
    path.write_text('{"models": [', encoding="utf-8")
    _configure_route_catalog(monkeypatch, path)

    response = client.get("/models/catalog/details")

    assert response.status_code == 200
    details = response.json()
    assert len(details["models"]) == 9
    assert details["warnings"][0]["code"] == "user_catalog_invalid_json"


def test_catalog_details_uses_same_filters_as_catalog(tmp_path, monkeypatch) -> None:
    path = _write_catalog(tmp_path, [_valid_user_llm(), _valid_user_embedding()])
    _configure_route_catalog(monkeypatch, path)

    response = client.get("/models/catalog/details", params={"model_type": "embedding"})

    assert response.status_code == 200
    assert {model["model_type"] for model in response.json()["models"]} == {"embedding"}


def _configure_route_catalog(monkeypatch, path: Path) -> None:
    loaded = UserModelCatalogLoader(str(path)).load()
    registry = ModelCatalogRegistry(
        user_models=loaded.models,
        warnings=loaded.warnings,
    )
    monkeypatch.setattr(model_routes, "model_catalog_registry", registry)


def _write_catalog(tmp_path: Path, models: list[dict]) -> Path:
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"models": models}), encoding="utf-8")
    return path


def _valid_user_llm() -> dict:
    return {
        "id": "ollama-codellama",
        "provider": "ollama",
        "model_name": "codellama",
        "model_type": "llm",
        "display_name": "Code Llama",
        "description": "User-added local coding model.",
        "capabilities": ["workspace_ask", "code_analysis"],
        "recommended_for_profiles": ["developer", "devops"],
        "recommended_laptop_profiles": ["powerful"],
        "estimated_size": None,
        "context_window": None,
        "embedding_dimension": None,
        "quality_tier": "experimental",
        "speed_tier": "medium",
        "local_only": True,
        "notes": ["User-provided metadata."],
    }


def _valid_user_embedding() -> dict:
    return {
        "id": "custom-embedding",
        "provider": "custom",
        "model_name": "custom-embedding",
        "model_type": "embedding",
        "display_name": "Custom Embedding",
        "description": "User-added embedding metadata.",
        "capabilities": ["workspace_indexing", "context_search"],
        "recommended_for_profiles": ["developer"],
        "recommended_laptop_profiles": ["balanced"],
        "estimated_size": None,
        "context_window": None,
        "embedding_dimension": 384,
        "quality_tier": "experimental",
        "speed_tier": "fast",
        "local_only": True,
        "notes": ["User-provided metadata."],
    }
