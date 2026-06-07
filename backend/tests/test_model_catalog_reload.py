import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.model_catalog.user_model_catalog_loader import UserModelCatalogLoader
from app.api.routes import models as model_routes
from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.main import app


client = TestClient(app)


def test_reload_with_disabled_user_catalog_keeps_builtins(monkeypatch) -> None:
    _configure_reloadable_catalog(monkeypatch, "")

    response = client.post("/models/catalog/reload")

    assert response.status_code == 200
    result = response.json()
    assert result["models_count"] == 6
    assert result["user_models_count"] == 0
    assert result["warnings_count"] == 0
    assert result["warnings"] == []
    assert len(client.get("/models/catalog").json()) == 6


def test_reload_after_editing_file_adds_user_model(tmp_path, monkeypatch) -> None:
    path = _write_catalog(tmp_path, [])
    _configure_reloadable_catalog(monkeypatch, str(path))
    path.write_text(json.dumps({"models": [_valid_user_llm()]}), encoding="utf-8")

    response = client.post("/models/catalog/reload")

    assert response.status_code == 200
    result = response.json()
    assert result["models_count"] == 7
    assert result["user_models_count"] == 1
    assert result["warnings_count"] == 0
    assert "ollama-codellama" in {
        model["id"] for model in client.get("/models/catalog").json()
    }


def test_reload_invalid_json_replaces_previous_user_models_with_warning(
    tmp_path,
    monkeypatch,
) -> None:
    path = _write_catalog(tmp_path, [_valid_user_llm()])
    _configure_reloadable_catalog(monkeypatch, str(path))
    assert "ollama-codellama" in {
        model["id"] for model in client.get("/models/catalog").json()
    }
    path.write_text('{"models": [', encoding="utf-8")

    response = client.post("/models/catalog/reload")

    assert response.status_code == 200
    result = response.json()
    assert result["models_count"] == 6
    assert result["user_models_count"] == 0
    assert result["warnings_count"] == 1
    assert result["warnings"][0]["code"] == "user_catalog_invalid_json"
    assert "ollama-codellama" not in {
        model["id"] for model in client.get("/models/catalog").json()
    }
    assert client.get("/models/catalog/details").json()["warnings"] == result["warnings"]


def test_recommendations_use_reloaded_user_model(tmp_path, monkeypatch) -> None:
    path = _write_catalog(tmp_path, [])
    _configure_reloadable_catalog(monkeypatch, str(path))
    path.write_text(json.dumps({"models": [_valid_user_llm()]}), encoding="utf-8")
    assert client.post("/models/catalog/reload").status_code == 200

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
        recommendation["model"]["id"]
        for recommendation in response.json()["recommendations"]
    }


def _configure_reloadable_catalog(monkeypatch, catalog_path: str) -> None:
    registry = ModelCatalogRegistry(loader=UserModelCatalogLoader(catalog_path))
    registry.reload()
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
