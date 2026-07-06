"""Schema-constrained grounded answers: schema shape + tolerant parsing."""

from app.core.domain.rag_structured_answer import (
    citations_response_format,
    citations_schema,
    parse_structured_answer,
    structured_answer_text,
)


def test_schema_requires_answer_and_citations():
    schema = citations_schema()
    assert schema["required"] == ["answer_md", "citations"]
    props = schema["properties"]
    assert props["answer_md"]["type"] == "string"
    citation = props["citations"]["items"]
    assert citation["required"] == ["path", "quote"]


def test_response_format_wraps_the_schema():
    rf = citations_response_format()
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["schema"] == citations_schema()


def test_parse_valid_structured_answer():
    raw = (
        '{"answer_md": "Runs via `docker compose up`.", '
        '"citations": [{"path": "README.md", "quote": "docker compose up"}]}'
    )
    parsed = parse_structured_answer(raw)
    assert parsed is not None
    assert parsed.answer_md == "Runs via `docker compose up`."
    assert parsed.citations[0].path == "README.md"
    assert parsed.citations[0].quote == "docker compose up"


def test_parse_tolerates_a_code_fence():
    raw = '```json\n{"answer_md": "Hi", "citations": []}\n```'
    parsed = parse_structured_answer(raw)
    assert parsed is not None and parsed.answer_md == "Hi"
    assert parsed.citations == ()


def test_parse_returns_none_for_plain_text():
    assert parse_structured_answer("Just a normal answer, not JSON.") is None
    assert parse_structured_answer("") is None
    assert parse_structured_answer('{"citations": []}') is None  # no answer_md


def test_parse_skips_malformed_citation_entries():
    raw = (
        '{"answer_md": "ok", "citations": ['
        '{"path": "a.py", "quote": "x"}, {"quote": "no path"}, "junk", '
        '{"path": "   ", "quote": "blank path"}]}'
    )
    parsed = parse_structured_answer(raw)
    assert parsed is not None
    assert [c.path for c in parsed.citations] == ["a.py"]


def test_structured_answer_text_falls_back_to_raw():
    # Valid structured → the markdown body; anything else → unchanged (fail-open).
    assert structured_answer_text('{"answer_md": "Body", "citations": []}') == "Body"
    assert structured_answer_text("plain answer") == "plain answer"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
