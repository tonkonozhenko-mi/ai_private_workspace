"""Only the app that started this backend may talk to it.

The backend listens on 127.0.0.1:8000 with no authentication of any kind. That
sounds harmless — it is loopback, nothing is exposed to the network — and it is
not, because a browser is also on loopback. CORS allows every ``localhost``
origin with credentials, so any page the person opens on any local port could
read the whole indexed project: source code, chat history, answers. A developer
runs local servers all day, from repositories they have just cloned. "Your files
never leave the machine" was true; "nothing else on the machine can read them"
was never checked.

So the desktop shell generates a random token when it launches, passes it to the
backend it spawns and hands the same value to its own webview. Every request has
to carry it. A page in an ordinary browser has no way to learn it: it is not in
the URL, not in a file the page can fetch, and not derivable — it comes from the
Tauri bridge, which only the app's own webview has.

When no token is configured the API is open, exactly as before. That is not a
loophole to be closed later; it is what `uvicorn app.main:app` for development
and the 1500-test suite both rely on, and neither is reachable from a browser
someone else controls. The packaged app always sets one.

Two things stay open even with a token, on purpose:

  ``/health``   the shell polls it to decide when the backend has started, and
                it answers before any token could be agreed. It reports liveness
                and nothing about the person's projects.
  ``OPTIONS``   a CORS preflight never carries the Authorization header — that is
                what it is asking permission for. Refusing it would make every
                real request fail with an error about the wrong thing.
"""

from collections.abc import Awaitable, Callable
from secrets import compare_digest

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

# Paths that answer before, or without, a token. Kept literal and tiny: a
# prefix match here would be a way in.
OPEN_PATHS: frozenset[str] = frozenset({"/health", "/health/"})


def bearer_token(header_value: str | None) -> str:
    """The token out of an ``Authorization: Bearer <token>`` header, or ""."""
    if not header_value:
        return ""
    scheme, _, value = header_value.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return value.strip()


def request_is_allowed(method: str, path: str, header_value: str | None, expected: str) -> bool:
    """Whether one request may proceed. Pure, so the rule can be read and tested
    without standing up an HTTP server."""
    if not expected:
        return True
    if method.upper() == "OPTIONS" or path in OPEN_PATHS:
        return True
    # compare_digest rather than ==: the comparison time of a plain string
    # comparison depends on how many leading characters match, which is enough
    # to recover a secret one character at a time.
    return compare_digest(bearer_token(header_value), expected)


class LocalApiTokenMiddleware:
    """Refuses any request that does not carry the shell's token.

    Written as raw ASGI rather than BaseHTTPMiddleware because the streaming
    answers (Ask, and the investigator's live steps) send Server-Sent Events,
    and BaseHTTPMiddleware buffers a response body — which would turn a stream
    that arrives token by token into one that arrives all at once at the end.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope, receive: Callable, send: Callable[..., Awaitable]) -> None:
        if scope["type"] != "http" or not self.token:
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if request_is_allowed(
            request.method, request.url.path, request.headers.get("authorization"), self.token
        ):
            await self.app(scope, receive, send)
            return

        response: Response = JSONResponse(
            status_code=401,
            content={
                "detail": (
                    "This backend only answers the desktop app that started it. "
                    "Open the app instead of calling the API directly."
                )
            },
        )
        await response(scope, receive, send)
