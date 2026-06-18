"""Contract for the llama.cpp cross-encoder reranker adapter.

The reranker must reorder candidates by the server's relevance score and, on any
failure path (disabled, HTTP error, malformed response), return the input order
unchanged so retrieval never breaks.
"""

import json

import httpx

from app.adapters.llm.llama_server_reranker import LlamaServerReranker
from app.adapters.llm.null_reranker import NullReranker

_DOCS = ["alpha doc", "bravo doc", "charlie doc"]


def _reranker(handler, enabled=True) -> LlamaServerReranker:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return LlamaServerReranker("http://rerank.test", "bge-reranker", enabled=enabled, client=client)


def test_reranks_by_relevance_score() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://rerank.test/rerank"
        body = json.loads(request.content)
        assert body["query"] == "find charlie"
        assert body["documents"] == _DOCS
        # Server says doc index 2 (charlie) is most relevant, then 0, then 1.
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 0, "relevance_score": 0.1},
                    {"index": 1, "relevance_score": 0.05},
                    {"index": 2, "relevance_score": 0.9},
                ]
            },
        )

    order = _reranker(handler).rerank("find charlie", _DOCS, top_k=2)
    assert order == [2, 0]


def test_disabled_returns_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("disabled reranker must not call the server")

    order = _reranker(handler, enabled=False).rerank("q", _DOCS, top_k=3)
    assert order == [0, 1, 2]


def test_server_error_falls_back_to_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    order = _reranker(handler).rerank("q", _DOCS, top_k=3)
    assert order == [0, 1, 2]


def test_malformed_response_falls_back_to_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    order = _reranker(handler).rerank("q", _DOCS, top_k=3)
    assert order == [0, 1, 2]


def test_null_reranker_is_identity_and_disabled() -> None:
    null = NullReranker()
    assert null.enabled is False
    assert null.rerank("q", _DOCS, top_k=2) == [0, 1]
