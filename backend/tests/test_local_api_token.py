"""The backend answers the app that started it, and nothing else.

Before this, it answered anyone. No authentication existed anywhere in the API —
not a header, not a cookie, not a dependency — while CORS allowed every
``localhost`` origin with credentials and the port was the fixed 8000. So any
page open in a browser could read the whole indexed project: file contents,
answers, conversation history. "Your files never leave the machine" held; the
part nobody had written down was that anything else on the machine could read
them.

The rule is deliberately dull: a shared secret the desktop shell generates at
launch, required on every request. What makes it worth reading is where it does
*not* apply, because each exception is a door.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.local_api_token import bearer_token, request_is_allowed
from app.main import app

TOKEN = "s3cret-token-from-the-shell"


def _client(monkeypatch, token: str) -> TestClient:
    """A client whose backend is configured with (or without) a token.

    Starlette builds the middleware stack once, on the first request, and hands
    each middleware its kwargs at construction time — so changing the kwargs
    afterwards changes nothing at all. The first version of this helper did
    exactly that, and three tests here passed by asserting against a backend
    that had never been given a token. The stack is dropped as well, so the next
    request rebuilds it with the value below, and restored afterwards because
    ``app`` is a module-level singleton shared with 77 other test files.
    """
    for middleware in app.user_middleware:
        if middleware.cls.__name__ == "LocalApiTokenMiddleware":
            monkeypatch.setitem(middleware.kwargs, "token", token)
    monkeypatch.setattr(app, "middleware_stack", None, raising=False)
    return TestClient(app)


def test_without_a_token_the_api_is_open(monkeypatch):
    """What `uvicorn app.main:app` and the whole test suite rely on. If this
    ever fails, 1500 tests fail with it and the failure will not say why."""
    client = _client(monkeypatch, "")

    assert client.get("/workspaces").status_code == 200


def test_with_a_token_an_unauthenticated_request_is_refused(monkeypatch):
    client = _client(monkeypatch, TOKEN)

    response = client.get("/workspaces")

    assert response.status_code == 401
    # Says what to do, not "Unauthorized".
    assert "desktop app" in response.json()["detail"]


def test_the_right_token_gets_through(monkeypatch):
    client = _client(monkeypatch, TOKEN)

    response = client.get("/workspaces", headers={"Authorization": f"Bearer {TOKEN}"})

    assert response.status_code == 200


def test_a_wrong_token_does_not(monkeypatch):
    client = _client(monkeypatch, TOKEN)

    for wrong in [f"Bearer {TOKEN}x", f"Bearer {TOKEN[:-1]}", "Bearer ", "Basic abc", TOKEN]:
        assert client.get("/workspaces", headers={"Authorization": wrong}).status_code == 401


def test_health_answers_without_a_token(monkeypatch):
    """The shell polls /health to decide when the backend has finished starting.
    It has to answer before anything is agreed, and it says nothing about the
    person's projects."""
    client = _client(monkeypatch, TOKEN)

    assert client.get("/health").status_code == 200


def test_a_preflight_is_not_refused(monkeypatch):
    """A CORS preflight never carries Authorization — carrying it is the thing
    it is asking permission for. Refusing preflights would make every real
    request fail with an error about the wrong problem."""
    client = _client(monkeypatch, TOKEN)

    response = client.options(
        "/workspaces",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code < 400


def test_a_refusal_still_carries_cors_headers(monkeypatch):
    """Middleware order, asserted rather than assumed. If the token check sits
    outside CORS, the 401 arrives without CORS headers and the app's own webview
    reports an opaque network failure instead of the reason."""
    client = _client(monkeypatch, TOKEN)

    response = client.get("/workspaces", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_the_open_paths_are_exactly_health():
    """A prefix match here would be the way in: /health-and-also-your-files."""
    assert request_is_allowed("GET", "/health", None, TOKEN)
    assert not request_is_allowed("GET", "/healthy", None, TOKEN)
    assert not request_is_allowed("GET", "/health/../workspaces", None, TOKEN)
    assert not request_is_allowed("GET", "/workspaces", None, TOKEN)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Bearer abc", "abc"),
        ("bearer abc", "abc"),
        ("Bearer  abc ", "abc"),
        ("Basic abc", ""),
        ("abc", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_reading_the_header(header, expected):
    assert bearer_token(header) == expected


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
