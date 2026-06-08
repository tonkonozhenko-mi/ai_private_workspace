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
