"""Unit tests for the llama-server provider payload + exact token counting."""

import httpx

from app.adapters.llm.llama_server_llm_provider import LlamaServerLLMProvider
from app.core.domain.structured_output import json_schema_response_format


def _provider(client=None):
    return LlamaServerLLMProvider(base_url="http://test", model="m", client=client)


def test_payload_basics():
    payload = _provider()._payload("hi", None, None, stream=False)
    assert payload["cache_prompt"] is True
    assert payload["messages"][-1]["content"] == "hi"
    assert "response_format" not in payload


def test_payload_includes_response_format():
    rf = json_schema_response_format({"type": "object"}, name="tool_call")
    payload = _provider()._payload("hi", None, 0.0, stream=False, response_format=rf)
    assert payload["response_format"] == rf
    assert payload["temperature"] == 0.0


def test_payload_stream_requests_usage():
    payload = _provider()._payload("hi", None, None, stream=True)
    assert payload["stream_options"] == {"include_usage": True}


def test_count_tokens_uses_server():
    class _Resp:
        status_code = 200

        def json(self):
            return {"tokens": [1, 2, 3, 4, 5]}

    class _Client:
        def post(self, *a, **k):
            return _Resp()

    assert _provider(_Client()).count_tokens("whatever") == 5


def test_count_tokens_falls_back_on_error():
    class _Client:
        def post(self, *a, **k):
            raise httpx.HTTPError("offline")

    # 8 chars // 4 == 2
    assert _provider(_Client()).count_tokens("abcdefgh") == 2
