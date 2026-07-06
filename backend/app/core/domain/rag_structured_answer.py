"""Schema-constrained grounded answers (experimental, behind a flag).

A small local model often ends its answer by parroting the prompt's per-chunk
``source_path:`` headers, or renders citations inconsistently. When the engine can
constrain generation to a JSON Schema (llama.cpp grammar / Ollama ``format``), we
can ask it for a strict shape instead::

    {"answer_md": "...", "citations": [{"path": "...", "quote": "..."}]}

so the prose can't contain a raw ``source_path:`` block and the citations come out
as structured data. This is the pure part: the schema, the response-format payload,
the prompt nudge, and a tolerant parser. Whether to use it is decided by the use
case (flag + answer mode + provider capability); parsing is always fail-open, so a
malformed or plain-text answer is used as-is.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.core.domain.structured_output import json_schema_response_format

# Opt-in env flag. Experimental: constraining a small model to a rigid schema can
# degrade the prose, so it stays off unless explicitly enabled.
STRUCTURED_CITATIONS_ENV_VAR = "AI_WORKSPACE_ASK_STRUCTURED_CITATIONS"


@dataclass(frozen=True)
class StructuredCitation:
    path: str
    quote: str


@dataclass(frozen=True)
class StructuredAnswer:
    answer_md: str
    citations: tuple[StructuredCitation, ...]


def citations_schema() -> dict:
    """JSON Schema for a grounded answer with explicit citations."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["answer_md", "citations"],
        "properties": {
            "answer_md": {
                "type": "string",
                "description": "The answer in Markdown. Cite files inline with the "
                "path in backticks; do NOT append a source_path list.",
            },
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["path", "quote"],
                    "properties": {
                        "path": {"type": "string"},
                        "quote": {
                            "type": "string",
                            "description": "A short verbatim excerpt from that file "
                            "supporting the answer.",
                        },
                    },
                },
            },
        },
    }


def citations_response_format() -> dict:
    """The OpenAI-style ``response_format`` that constrains generation to the schema."""
    return json_schema_response_format(citations_schema(), name="grounded_answer")


def structured_answer_instruction() -> str:
    """A short nudge appended to the prompt so the model fills the fields with
    meaning (the grammar guarantees the shape, not the content)."""
    return (
        '\n\nRespond as a JSON object with two keys: "answer_md" (your answer in '
        'Markdown) and "citations" (a list of {"path", "quote"} objects, each a '
        "short verbatim excerpt from a cited file). Put file paths in backticks inside "
        "answer_md; never append a plain source_path list."
    )


def parse_structured_answer(raw: str) -> StructuredAnswer | None:
    """Parse a schema-constrained answer. Returns ``None`` when ``raw`` isn't the
    expected JSON object (so the caller falls back to treating it as plain text)."""
    text = (raw or "").strip()
    if not text:
        return None
    # Tolerate a leading/trailing code fence the model may add despite the grammar.
    if text.startswith("```"):
        text = text.strip("`")
        newline = text.find("\n")
        if newline != -1:
            text = text[newline + 1 :]
        text = text.strip()
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or "answer_md" not in data:
        return None
    answer_md = data.get("answer_md")
    if not isinstance(answer_md, str) or not answer_md.strip():
        return None
    citations: list[StructuredCitation] = []
    for item in data.get("citations") or []:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        quote = item.get("quote", "")
        if isinstance(path, str) and path.strip():
            citations.append(StructuredCitation(path=path.strip(), quote=str(quote)))
    return StructuredAnswer(answer_md=answer_md.strip(), citations=tuple(citations))


def structured_answer_text(raw: str) -> str:
    """The Markdown answer to show the user: the parsed ``answer_md`` when ``raw`` is
    a valid structured answer, otherwise ``raw`` unchanged (fail-open)."""
    parsed = parse_structured_answer(raw)
    return parsed.answer_md if parsed is not None else raw
