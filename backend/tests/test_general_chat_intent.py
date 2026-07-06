"""looks_general_chat() — the high-precision inverse chit-chat detector."""

from app.core.domain.question_intent import looks_general_chat, looks_project_specific
from eval.golden_set import (
    CLASS_PROJECT_BROAD,
    CLASS_PROJECT_PRECISE,
    CLASS_SHOULD_ABSTAIN,
    golden_set,
)


def test_all_should_abstain_are_chat():
    for case in golden_set():
        if case.cls == CLASS_SHOULD_ABSTAIN:
            assert looks_general_chat(case.question), case.id


def test_no_project_question_is_chat():
    # The dangerous false positive: a real project question flagged as chat would
    # skip retrieval and answer ungrounded.
    for case in golden_set():
        if case.cls in (CLASS_PROJECT_PRECISE, CLASS_PROJECT_BROAD):
            assert not looks_general_chat(case.question), case.id


def test_bare_greetings_and_thanks():
    for q in (
        "hi",
        "Hello!",
        "hey there".replace(" there", ""),
        "Thanks!",
        "thank you very much",
        "Good morning",
    ):
        assert looks_general_chat(q), q


def test_greeting_prefix_on_a_project_question_is_not_chat():
    # A greeting that prefixes a substantive project question must NOT route to chat.
    assert not looks_general_chat(
        "Hi, how does the RAG pipeline work?"
    )  # 'pipeline' = project signal
    assert not looks_general_chat("Hello, what is this project about?")  # 'this project'


def test_in_general_marker_but_project_signal_wins():
    # "in general" is a chat marker, but a project signal overrides it.
    assert looks_general_chat("What is a Python decorator in general?")
    assert not looks_general_chat("How does `main.py` work in general?")  # backtick = project


def test_arithmetic_and_world_trivia():
    assert looks_general_chat("What is 17 times 23?")
    assert looks_general_chat("what is 5 + 4")
    assert looks_general_chat("Who is the president of Brazil?")
    assert looks_general_chat("What is the capital of France?")


def test_project_specific_still_works():
    # sanity: the existing detector is unchanged
    assert looks_project_specific("How is `backend.tf` configured?")
    assert not looks_project_specific("What time is it?")
