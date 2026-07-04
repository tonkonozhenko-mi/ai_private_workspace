"""Ollama honours structured output via its ``format`` field.

The investigator (and other structured callers) send an OpenAI-style
``response_format``; the Ollama provider must translate that into Ollama's
``format`` so the same schema-constrained JSON works on both engines.
"""

from app.core.domain.structured_output import (
    json_object_response_format,
    json_schema_response_format,
    ollama_format_from_response_format,
)


# --- pure translation ------------------------------------------------------


def test_translate_json_object_to_string_json():
    assert ollama_format_from_response_format(json_object_response_format()) == "json"


def test_translate_json_schema_to_raw_schema():
    rf = json_schema_response_format({"type": "object", "properties": {"x": {"type": "string"}}})
    translated = ollama_format_from_response_format(rf)
    assert translated == {"type": "object", "properties": {"x": {"type": "string"}}}


def test_translate_none_is_none():
    assert ollama_format_from_response_format(None) is None
    assert ollama_format_from_response_format({}) is None


# --- provider passes format on the wire ------------------------------------


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                "error", request=httpx.Request("POST", "http://x/api/generate"), response=self
            )

    def json(self):
        return self._payload

    @property
    def text(self):
        return ""


class _RecordingClient:
    def __init__(self, responder):
        self.responder = responder
        self.payloads = []

    def post(self, url, json=None, timeout=None):
        self.payloads.append(json)
        return self.responder(json)


def test_provider_sends_schema_format_for_structured_request():
    from app.adapters.llm.ollama_llm_provider import OllamaLLMProvider

    client = _RecordingClient(lambda body: _Response({"response": '{"ok": true}'}))
    provider = OllamaLLMProvider("http://x:11434", "mistral", client=client)
    assert provider.supports_structured_output is True

    rf = json_schema_response_format({"type": "object"}, name="step")
    provider.generate("hi", response_format=rf)

    assert client.payloads[0]["format"] == {"type": "object"}


def test_provider_drops_format_and_retries_on_400():
    # An older Ollama rejects a schema format with 400 — the provider must retry
    # once without it and still return the answer, not hard-fail.
    calls = {"n": 0}

    def responder(body):
        calls["n"] += 1
        if "format" in body:
            return _Response({}, status_code=400)
        return _Response({"response": "plain answer"})

    client = _RecordingClient(responder)
    from app.adapters.llm.ollama_llm_provider import OllamaLLMProvider

    provider = OllamaLLMProvider("http://x:11434", "mistral", client=client)
    out = provider.generate("hi", response_format=json_schema_response_format({"type": "object"}))
    assert out == "plain answer"
    assert calls["n"] == 2  # first with format (400), retry without
