"""A model that starts repeating itself is stopped, and a model that repeats a
line for a reason is left alone.

Maks, 16.07: Mistral wrote a good answer, then the same paragraph about ten
times. He pressed Stop and lost the answer with it — the app had noticed
nothing. The cost of being wrong in the other direction is truncating something
he wanted, so the bar is deliberately high.
"""

from app.core.domain.degenerate_output import looping_paragraph, trim_to_first_loop

PARAGRAPH = (
    "The retention period is configured in the storage module and applies to "
    "every environment this project deploys to."
)
OTHER = (
    "Reports are written to object storage, and the lifecycle rules there are "
    "what actually enforce how long they are kept."
)


def test_an_answer_that_says_something_once_is_not_looping():
    assert looping_paragraph(f"{OTHER}\n\n{PARAGRAPH}") is None


def test_saying_it_twice_is_still_allowed():
    """Emphasis, or a summary that restates the finding. Not a loop."""
    assert looping_paragraph(f"{OTHER}\n\n{PARAGRAPH}\n\n{PARAGRAPH}") is None


def test_a_third_time_is_a_loop():
    text = f"{OTHER}" + f"\n\n{PARAGRAPH}" * 3

    assert looping_paragraph(text) == " ".join(PARAGRAPH.split())


def test_short_repeats_are_prose_not_loops():
    """A heading, a path, a "Yes." — repeated all the time in a real answer."""
    text = "\n\n".join(["## Findings", "`app/storage.py`", "## Findings", "`app/storage.py`"] * 3)

    assert looping_paragraph(text) is None


def test_extra_blank_lines_do_not_hide_the_loop():
    text = f"{OTHER}" + f"\n\n\n{PARAGRAPH}\n" * 3

    assert looping_paragraph(text) is not None


def test_trimming_keeps_what_was_said_once():
    text = f"{OTHER}" + f"\n\n{PARAGRAPH}" * 8

    trimmed = trim_to_first_loop(text)

    assert trimmed.count(PARAGRAPH) == 1
    assert OTHER in trimmed


def test_trimming_leaves_a_healthy_answer_untouched():
    text = f"{OTHER}\n\n{PARAGRAPH}"

    assert trim_to_first_loop(text) == text
