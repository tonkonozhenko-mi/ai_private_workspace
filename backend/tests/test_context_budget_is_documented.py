"""The documented budget and the real budget are one thing, checked.

Documentation about numbers goes stale in exactly the way two lists go stale, and
this project has now watched that happen twice: the extension dictionary drifted
from the include patterns, silently, for two releases. A table of token reserves
in ARCHITECTURE.md is the same shape of risk with a worse failure mode — nobody
runs a document, so nothing complains.

So the document is read, and its numbers are compared with the constants. Change
a constant without the table and this fails; change the table without the
constant and it fails too. It does not check prose, only the figures a reader
would take away and act on.
"""

import re
from pathlib import Path

from app.core.domain.context_budget import (
    CHARS_PER_TOKEN,
    CJK_CHARS_PER_TOKEN,
    CYRILLIC_CHARS_PER_TOKEN,
    MIN_CHUNK_CHARS,
    PROMPT_SCAFFOLD_TOKENS,
    RESPONSE_RESERVE_TOKENS,
    _DEFAULT_CONTEXT_WINDOW,
)

ARCHITECTURE = Path(__file__).parents[2] / "docs" / "ARCHITECTURE.md"
README = Path(__file__).parents[2] / "README.md"


def _budget_section() -> str:
    """The budget section with its line wrapping flattened.

    Markdown wraps prose at 80 columns, so "one token per 4 ASCII characters"
    is split across two lines in the file. Asserting on the raw text would make
    this test about where a paragraph happens to break — reflow the document and
    it fails while every number is still correct. Whitespace is collapsed so the
    assertions are about what the sentence says.
    """
    text = ARCHITECTURE.read_text(encoding="utf-8")
    start = text.index("## Context budget")
    section = text[start : text.index("## Answer honesty", start)]
    return re.sub(r"\s+", " ", section)


def test_the_two_reserved_figures_are_the_ones_in_the_code():
    section = _budget_section()

    # Read out of the table cells, so reformatting the prose cannot fake a pass.
    figures = [int(cell.replace(",", "")) for cell in re.findall(r"\|\s*(\d[\d,]*)\s*\|", section)]

    assert RESPONSE_RESERVE_TOKENS in figures, (
        f"answer headroom is {RESPONSE_RESERVE_TOKENS} in code; the table says {figures}"
    )
    assert PROMPT_SCAFFOLD_TOKENS in figures, (
        f"prompt scaffold is {PROMPT_SCAFFOLD_TOKENS} in code; the table says {figures}"
    )


def test_the_other_figures_the_document_quotes_are_real():
    section = _budget_section()

    assert f"floor of {MIN_CHUNK_CHARS} characters" in section
    assert f"the fallback is {_DEFAULT_CONTEXT_WINDOW}" in section
    # The script ratios, which are the point of the paragraph about Ukrainian.
    assert f"one token per {CHARS_PER_TOKEN} ASCII characters" in section
    assert f"about one per {CYRILLIC_CHARS_PER_TOKEN} Cyrillic" in section
    assert CJK_CHARS_PER_TOKEN == 1, "the document says 'one per CJK character'"


def test_the_document_does_not_promise_per_category_reservations():
    """The mental model this section exists to correct. If someone later writes
    'N% for retrieval, M% for memory', that is a description of a different
    program than the one in context_budget.py."""
    section = _budget_section()

    assert "measured, not reserved" in section
    assert "%" not in section.split("Two consequences")[0].replace("28%", "")


def test_the_worked_example_stays_a_measurement():
    """1,792 of 6,516 is a reading taken from one real session, not arithmetic.

    My first version of this test asserted the 6,516 followed from 8,192 minus
    the two reserves. It does not — that session had its own history and memory
    section — and the assertion was false the moment it was written. A measured
    number is checked by being labelled as measured and left alone; deriving it
    would be inventing a provenance it never had.
    """
    section = _budget_section()

    assert "1,792 of 6,516" in section
    assert "Measured live" in section


def test_the_readme_quotes_the_same_two_numbers():
    """The README repeats the two reserves rather than linking only, because a
    reader deciding whether this app fits their laptop should not have to open a
    second document. Repeating a number is fine; repeating it *unchecked* is how
    two records of one fact drift, which this project has already lived through.
    """
    readme = re.sub(r"\s+", " ", README.read_text(encoding="utf-8"))

    assert f"{RESPONSE_RESERVE_TOKENS} tokens so the model has room" in readme
    assert f"{PROMPT_SCAFFOLD_TOKENS} for the fixed instruction scaffold" in readme
    # And it points at the fuller explanation rather than growing its own table.
    assert "ARCHITECTURE.md#context-budget" in readme
