"""The answer is written in the language the person asked for — and when they did
not ask, in the one they wrote the question in.

Live, 16.07: Maks asked in Ukrainian for onboarding docs "and all of it must be in
English"; Mistral answered in Ukrainian, the language of the wiki it had read.
The prompt had said nothing about language at all, so the corpus decided.
"""

from app.core.domain.answer_language import (
    answer_language_directive,
    question_script_language,
    requested_language,
)

ASKED = "составь онбординг документацию для нового девопса, и все должно біть на английском"


def test_the_live_question_asks_for_english_typo_and_all():
    """'біти' is a slip for 'бути'. It asks just as clearly."""
    assert requested_language(ASKED) == "English"


def test_an_explicit_request_beats_a_saved_preference():
    directive = answer_language_directive(ASKED, saved_preference="Answer in Ukrainian.")

    assert "English" in directive
    assert "Ukrainian" not in directive


def test_a_saved_preference_is_used_when_nothing_was_asked():
    directive = answer_language_directive("де зберігаються звіти?", "Always answer in English.")

    assert directive == "Always answer in English."


def test_with_neither_the_answer_follows_the_question():
    assert "Ukrainian" in answer_language_directive("де зберігаються звіти?")
    assert "English" in answer_language_directive("where are reports stored?")
    # Cyrillic without і/ї/є/ґ is still the same language, not another one.
    assert "Ukrainian" in answer_language_directive("як налаштована база даних?")


def test_the_directive_names_the_documents_as_what_not_to_follow():
    """The whole failure: the wiki's language won over the person's."""
    assert "source documents" in answer_language_directive("де зберігаються звіти?")


def test_mentioning_a_language_is_not_asking_for_one():
    assert requested_language("the English docs are outdated") is None
    assert requested_language("where is the English translation stored?") is None


def test_requests_in_several_languages_are_understood():
    assert requested_language("answer in Ukrainian please") == "Ukrainian"
    assert requested_language("відповідай англійською") == "English"
    assert requested_language("напиши відповідь польською") == "Polish"


def test_cyrillic_is_ukrainian_with_or_without_its_own_letters():
    """The і/ї/є/ґ letters confirm Ukrainian; their absence does not deny it.
    That second line used to return "Russian" — one arm of a script check,
    chosen by nobody, which then told the model which language to answer in."""
    assert question_script_language("де зберігаються звіти?") == "Ukrainian"
    assert question_script_language("як налаштована база даних?") == "Ukrainian"


def test_a_question_too_short_to_tell_names_no_language():
    assert question_script_language("?") is None
    assert answer_language_directive("?") == ""


# --- length without grounding ---------------------------------------------------


def test_a_long_answer_that_names_nothing_is_flagged():
    """The live failure: a page about Terraform in general, from a question about
    this project's own documentation."""
    from app.core.domain.rag_answer_evaluator import cites_nothing_at_length

    generic = (
        "Terraform is a tool for managing infrastructure as code. It lets you "
        "create, change and update resources in the cloud or locally. "
    ) * 6

    assert cites_nothing_at_length(generic, ["docs/onboarding.md"]) is True


def test_an_answer_that_names_a_file_is_not_flagged():
    from app.core.domain.rag_answer_evaluator import cites_nothing_at_length

    grounded = (
        "Deployment is driven from `infra/terragrunt.hcl`, which the onboarding "
        "guide describes step by step. " * 8
    )

    assert cites_nothing_at_length(grounded, ["docs/onboarding.md"]) is False


def test_naming_a_source_in_prose_counts_as_pointing_somewhere():
    from app.core.domain.rag_answer_evaluator import cites_nothing_at_length

    text = "The onboarding guide covers every step of this in order. " * 14

    assert cites_nothing_at_length(text, ["docs/onboarding.md"]) is False


def test_a_short_answer_is_never_flagged_for_this():
    from app.core.domain.rag_answer_evaluator import cites_nothing_at_length

    assert cites_nothing_at_length("Yes — object storage, with lifecycle rules.", []) is False


def test_ukrainian_names_a_language_the_way_ukrainian_does():
    """Ukrainian names a language in the instrumental case, without a preposition:
    "англійською", "німецькою", "французькою". Only the "-ською" ending was
    listed, so two thirds of them were unknown — and "польською" was worse: it
    begins with "по", the preposition branch swallowed those two letters, and the
    word never reached the matcher. Asking for Polish did nothing, silently."""
    assert requested_language("напиши відповідь польською") == "Polish"
    assert requested_language("напиши відповідь німецькою") == "German"
    assert requested_language("напиши відповідь французькою") == "French"
    assert requested_language("напиши іспанською") == "Spanish"


def test_naming_a_language_without_asking_for_it_changes_nothing():
    assert requested_language("the English docs are outdated") is None
