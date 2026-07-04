"""Helpers to ask an LLM for output that conforms to a JSON Schema.

llama.cpp's ``llama-server`` can constrain generation to a grammar derived from a
JSON Schema (the OpenAI-style ``response_format``), so the model *cannot* produce
invalid JSON. That is far more robust than parsing free-form text — useful for
agent tool calls, structured summaries, and any place we then ``json.loads`` the
answer.

This module only builds the request payload fragment; whether a provider honours
it is provider-specific. The bundled llama.cpp honours the OpenAI-style
``response_format`` directly; Ollama uses a different field (``format``) that takes
the raw JSON Schema — :func:`ollama_format_from_response_format` translates between
them so the same constrained-output request works on both engines.
Everything here is pure and trivial to test.
"""

from __future__ import annotations


def ollama_format_from_response_format(response_format: dict | None) -> dict | str | None:
    """Translate an OpenAI-style ``response_format`` into Ollama's ``format`` field.

    Ollama constrains output with a top-level ``format`` that is either the string
    ``"json"`` (any JSON object) or a raw JSON Schema object. Returns ``None`` when
    there's nothing to constrain, so the caller omits the field.
    """
    if not response_format:
        return None
    kind = response_format.get("type")
    if kind == "json_object":
        return "json"
    if kind == "json_schema":
        schema = response_format.get("json_schema", {}).get("schema")
        if isinstance(schema, dict):
            return schema
    return None


def json_schema_response_format(
    schema: dict,
    name: str = "response",
    strict: bool = True,
) -> dict:
    """Build the OpenAI-compatible ``response_format`` for a JSON Schema.

    Passed through to ``llama-server``'s ``/v1/chat/completions`` so generation is
    constrained to the schema. ``name`` labels the format; ``strict`` asks the
    server to enforce the schema exactly.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": strict,
            "schema": schema,
        },
    }


def json_object_response_format() -> dict:
    """Constrain output to *some* valid JSON object (no fixed schema).

    Useful when you want guaranteed-parseable JSON but the exact shape varies.
    """
    return {"type": "json_object"}
