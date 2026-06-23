"""Pure tests for review-first profile-fact extraction (prompt + parser)."""

from app.core.domain.user_profile_extraction import (
    build_extraction_prompt,
    parse_candidates,
)


def test_prompt_forbids_secrets_and_project_facts():
    prompt = build_extraction_prompt("I'm a DevOps engineer, answer in Russian.")
    low = prompt.lower()
    assert "secret" in low
    assert "project" in low  # excludes project facts
    assert "category|fact" in prompt


def test_parser_reads_category_and_text():
    raw = "role|DevOps engineer\nstyle|Answer in Russian\npreference|Keep it concise"
    out = parse_candidates(raw)
    assert {(c.category, c.text) for c in out} == {
        ("role", "DevOps engineer"),
        ("style", "Answer in Russian"),
        ("preference", "Keep it concise"),
    }


def test_parser_drops_existing_and_duplicates():
    raw = "role|DevOps engineer\nrole|DevOps engineer\nstyle|Answer in Russian"
    out = parse_candidates(raw, existing_texts=["answer in russian"])
    # The duplicate role collapses to one; the style already exists → dropped.
    assert [(c.category, c.text) for c in out] == [("role", "DevOps engineer")]


def test_parser_tolerates_stray_prose_and_bullets():
    raw = (
        "Here are some facts:\n"
        "- role|Backend developer\n"
        "garbage line without a delimiter\n"
        "* preference|Show code examples\n"
    )
    out = parse_candidates(raw)
    assert [(c.category, c.text) for c in out] == [
        ("role", "Backend developer"),
        ("preference", "Show code examples"),
    ]


def test_parser_unknown_category_falls_back_to_fact():
    out = parse_candidates("hobby|likes hiking")
    assert out[0].category == "fact"
    assert "hiking" in out[0].text


def test_parser_caps_at_max():
    raw = "\n".join(f"fact|thing number {i}" for i in range(20))
    assert len(parse_candidates(raw, max_facts=5)) == 5
