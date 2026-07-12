"""What the system does for the people who use it.

A business analyst does not want the module graph; they want the verbs. The HTTP
endpoints a service exposes *are* the verbs — "create an order", "cancel a
subscription" — and they are written down in the routes. So is the vocabulary: the
nouns the system works with (its domain entities).

Both are read from the files, in whatever framework the project happens to use. No
model invents a feature list; if the endpoint isn't in the code, we don't claim it.

Pure: no I/O, no state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")

# FastAPI / Flask / Django-ninja: @router.post("/orders/{id}")
_PY_DECORATOR_RE = re.compile(
    r"@(?:\w+\.)?(?P<method>" + "|".join(_HTTP_METHODS) + r")\s*\(\s*['\"](?P<path>[^'\"]+)['\"]",
    re.IGNORECASE,
)
# Flask's other spelling: @app.route("/orders", methods=["POST"])
_FLASK_ROUTE_RE = re.compile(
    r"@(?:\w+\.)?route\s*\(\s*['\"](?P<path>[^'\"]+)['\"](?P<rest>[^)]*)\)",
    re.IGNORECASE,
)
# Express / Koa / NestJS-lite: app.get("/orders", …) · router.post('/orders', …)
_JS_ROUTE_RE = re.compile(
    r"\b(?:app|router|api|server)\.(?P<method>" + "|".join(_HTTP_METHODS) + r")\s*\(\s*"
    r"['\"`](?P<path>/[^'\"`]*)['\"`]",
)
# Spring / NestJS decorators: @GetMapping("/orders") · @Post('/orders')
_JAVA_DECORATOR_RE = re.compile(
    r"@(?P<method>Get|Post|Put|Patch|Delete)(?:Mapping)?\s*\(\s*"
    r"(?:value\s*=\s*)?['\"](?P<path>[^'\"]+)['\"]",
)

# The nouns: ORM models and dataclasses that carry the domain vocabulary.
_PY_MODEL_RE = re.compile(r"^class\s+(?P<name>\w+)\s*\(\s*(?P<base>[^)]*)\)", re.MULTILINE)
_MODEL_BASES = ("basemodel", "base", "models.model", "declarative_base", "sqlmodel")

_MAX_FILES = 1200


@dataclass(frozen=True)
class ApiEndpoint:
    method: str
    path: str
    source_file: str
    handler: str | None = None

    @property
    def label(self) -> str:
        return f"{self.method.upper()} {self.path}"


@dataclass(frozen=True)
class ApiSurface:
    endpoints: list[ApiEndpoint] = field(default_factory=list)
    domain_entities: list[str] = field(default_factory=list)
    # The top-level resources the API is organised around: /orders, /users, …
    resources: list[str] = field(default_factory=list)


def _resource_of(path: str) -> str | None:
    """`/api/v1/orders/{id}/items` → `orders`. Version and api prefixes are noise; the
    first real word is the thing the endpoint is about."""
    for segment in path.strip("/").split("/"):
        lowered = segment.lower()
        if not lowered or lowered in {"api", "v1", "v2", "v3"}:
            continue
        if lowered.startswith(("{", ":", "<")):
            continue
        if re.fullmatch(r"v\d+", lowered):
            continue
        return lowered
    return None


def _handler_after(content: str, index: int) -> str | None:
    """The function name defined right after a route decorator — the handler, which
    usually reads like the feature itself (`def cancel_subscription`)."""
    tail = content[index : index + 400]
    match = re.search(r"(?:def|function|async def|async function)\s+(\w+)", tail)
    return match.group(1) if match else None


def _endpoints_in_python(path: str, content: str) -> list[ApiEndpoint]:
    endpoints: list[ApiEndpoint] = []
    for match in _PY_DECORATOR_RE.finditer(content):
        endpoints.append(
            ApiEndpoint(
                method=match.group("method").lower(),
                path=match.group("path"),
                source_file=path,
                handler=_handler_after(content, match.end()),
            )
        )
    for match in _FLASK_ROUTE_RE.finditer(content):
        methods = re.findall(
            r"['\"](" + "|".join(_HTTP_METHODS) + r")['\"]", match.group("rest"), re.I
        )
        for method in methods or ["get"]:
            endpoints.append(
                ApiEndpoint(
                    method=method.lower(),
                    path=match.group("path"),
                    source_file=path,
                    handler=_handler_after(content, match.end()),
                )
            )
    return endpoints


def _endpoints_in_js(path: str, content: str) -> list[ApiEndpoint]:
    return [
        ApiEndpoint(
            method=match.group("method").lower(),
            path=match.group("path"),
            source_file=path,
        )
        for match in _JS_ROUTE_RE.finditer(content)
    ]


def _endpoints_in_java(path: str, content: str) -> list[ApiEndpoint]:
    return [
        ApiEndpoint(
            method=match.group("method").lower(),
            path=match.group("path"),
            source_file=path,
        )
        for match in _JAVA_DECORATOR_RE.finditer(content)
    ]


# The machinery, not the business: a `class OrderRepository` moves orders around, a
# `class CreateOrderRequest` is a wire format. Only `class Order` is the noun a
# business analyst recognises. Transport and plumbing suffixes are dropped — an
# entity list full of `*Response` teaches nobody what the system is about.
_PLUMBING_SUFFIX_RE = re.compile(
    r"(Repository|Service|UseCase|Adapter|Port|Error|Exception|Config|Settings|Plan|"
    r"Request|Response|Schema|Payload|Dto|Input|Output|Result|Factory|Builder|Mixin)$"
)


def _domain_entities(path: str, content: str) -> list[str]:
    """Classes that carry the domain vocabulary: ORM models, dataclasses, schemas that
    are named after real things."""
    names: list[str] = []
    for match in _PY_MODEL_RE.finditer(content):
        base = match.group("base").lower()
        name = match.group("name")
        if not any(hint in base for hint in _MODEL_BASES):
            continue
        if _PLUMBING_SUFFIX_RE.search(name):
            continue
        names.append(name)
    if "@dataclass" in content:
        for match in re.finditer(r"@dataclass[^\n]*\n(?:@\w+[^\n]*\n)*class\s+(\w+)", content):
            name = match.group(1)
            if not _PLUMBING_SUFFIX_RE.search(name):
                names.append(name)
    return names


def build_api_surface(files: dict[str, str]) -> ApiSurface:
    """``files`` is {path: content}. Framework-agnostic: whichever routes are there."""
    endpoints: list[ApiEndpoint] = []
    entities: list[str] = []

    for path in sorted(files)[:_MAX_FILES]:
        content = files[path]
        suffix = PurePosixPath(path).suffix.lower()
        if suffix == ".py":
            endpoints += _endpoints_in_python(path, content)
            entities += _domain_entities(path, content)
        elif suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
            endpoints += _endpoints_in_js(path, content)
        elif suffix in {".java", ".kt", ".cs"}:
            endpoints += _endpoints_in_java(path, content)

    # One endpoint may be declared twice (a router and its mount); keep it once.
    unique: dict[tuple[str, str], ApiEndpoint] = {}
    for endpoint in endpoints:
        unique.setdefault((endpoint.method, endpoint.path), endpoint)

    ordered = sorted(unique.values(), key=lambda e: (e.path, e.method))
    resources: list[str] = []
    for endpoint in ordered:
        resource = _resource_of(endpoint.path)
        if resource and resource not in resources:
            resources.append(resource)

    return ApiSurface(
        endpoints=ordered,
        domain_entities=sorted(dict.fromkeys(entities)),
        resources=resources,
    )
