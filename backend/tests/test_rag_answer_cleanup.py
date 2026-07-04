"""Stripping the trailing source_path echo small models append to RAG answers."""

from app.core.domain.rag_answer_cleanup import strip_source_path_echo


def test_strips_trailing_numbered_source_path_list():
    text = (
        "The backend uses Terragrunt in `accounts/<env>/account.hcl`.\n\n"
        "1. source_path: .agents/skills/confluence-documentation/SKILL.md\n"
        "2. source_path: .agents/skills/confluence-documentation/SKILL.md\n"
        "3. source_path: AGENTS.md"
    )
    out = strip_source_path_echo(text)
    assert out == "The backend uses Terragrunt in `accounts/<env>/account.hcl`."
    assert "source_path" not in out


def test_strips_sources_header_above_the_block():
    text = "Answer body here.\n\nSources:\n- source_path: a.tf\n- source_path: b.tf"
    out = strip_source_path_echo(text)
    assert out == "Answer body here."


def test_leaves_inline_mentions_untouched():
    # A source_path inside a sentence is not a trailing list line — keep it.
    text = "The backend is configured (source_path: main.tf) and works."
    assert strip_source_path_echo(text) == text


def test_no_source_path_is_unchanged():
    text = "Terragrunt remote state is used (`main.tf`)."
    assert strip_source_path_echo(text) == text


def test_never_blanks_an_all_sources_answer():
    # If the model replied with ONLY a source list, don't return empty.
    text = "source_path: a.tf\nsource_path: b.tf"
    assert strip_source_path_echo(text) == text


def test_strips_only_the_trailing_block_not_earlier_content():
    text = (
        "Intro paragraph.\n\n"
        "- A finding (main.tf)\n\n"
        "1. source_path: main.tf\n2. source_path: other.tf"
    )
    out = strip_source_path_echo(text)
    assert out.endswith("- A finding (main.tf)")
    assert "source_path" not in out
