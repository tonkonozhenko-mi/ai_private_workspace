"""Helpers to ask an LLM for output that conforms to a JSON Schema.

llama.cpp's ``llama-server`` can constrain generation to a grammar derived from a
JSON Schema (the OpenAI-style ``response_format``), so the model *cannot* produce
invalid JSON. That is far more robust than parsing free-form text — useful for
agent tool calls, structured summaries, and any place we then ``json.loads`` the
answer.

This module only builds the request payload fragment; whether a provider honours
it is provider-specific (the bundled llama.cpp does; Ollama ignores it today).
Everything here is pure and trivial to test.
"""

from __future__ import annotations


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
