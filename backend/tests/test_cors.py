from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.main import app

client = TestClient(app)
allowed_origin = "http://localhost:5173"


def test_preflight_from_frontend_origin_returns_cors_headers() -> None:
    response = client.options(
        "/workspaces/overview",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == allowed_origin
    assert response.headers["access-control-allow-credentials"] == "true"


def test_get_from_frontend_origin_returns_allow_origin_header() -> None:
    response = client.get(
        "/workspaces/overview",
        headers={"Origin": allowed_origin},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == allowed_origin


def test_get_from_unknown_origin_does_not_return_allow_origin_header() -> None:
    response = client.get(
        "/workspaces/overview",
        headers={"Origin": "http://example.invalid"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_allowed_origins_parses_comma_separated_setting(monkeypatch) -> None:
    get_settings.cache_clear()
    with monkeypatch.context() as context:
        context.setenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:4173, http://127.0.0.1:4173, ",
        )

        assert get_settings().cors_allowed_origins == [
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]

    get_settings.cache_clear()
    get_settings()


def test_preflight_from_tauri_origin_returns_cors_headers() -> None:
    tauri_origin = "http://tauri.localhost"
    response = client.options(
        "/workspaces",
        headers={
            "Origin": tauri_origin,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == tauri_origin


def test_preflight_from_null_origin_is_allowed_for_packaged_webview() -> None:
    response = client.options(
        "/workspaces",
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "null"


def test_legacy_desktop_env_aliases_map_to_canonical_paths(monkeypatch, tmp_path) -> None:
    get_settings.cache_clear()
    with monkeypatch.context() as context:
        context.delenv("APP_DATA_DIR", raising=False)
        context.delenv("WORKSPACE_DB_PATH", raising=False)
        context.setenv("AI_WORKSPACE_APP_DATA_DIR", str(tmp_path / "app-data"))
        context.setenv("AI_WORKBENCH_DB_PATH", str(tmp_path / "app-data" / "workspace.sqlite3"))

        settings = get_settings()

        assert settings.app_data_dir == tmp_path / "app-data"
        assert settings.workspace_db_path == tmp_path / "app-data" / "workspace.sqlite3"
        assert settings.app_data_dir.exists()
        assert settings.workspace_db_path.parent.exists()

    get_settings.cache_clear()
    get_settings()
