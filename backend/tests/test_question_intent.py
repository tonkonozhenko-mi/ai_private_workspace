"""Heuristic that flags project-specific questions (drives honest abstention)."""

from app.core.domain.question_intent import looks_project_specific


def test_project_specific_questions_are_flagged():
    for q in [
        "where is the database configured in this project?",
        "explain `main.tf`",
        "how does our deployment pipeline work",
        "what environments does the service run in",
        "which file defines the auth middleware",
        "show me the terraform backend config",
        "what does docker-compose.yml start",
    ]:
        assert looks_project_specific(q), q


def test_general_questions_are_not_flagged():
    for q in [
        "hi there",
        "how are you?",
        "what model are you",
        "explain recursion in simple terms",
        "what's the capital of France",
        "write a haiku about the sea",
    ]:
        assert not looks_project_specific(q), q


def test_empty_is_not_flagged():
    assert looks_project_specific("") is False
    assert looks_project_specific(None) is False  # type: ignore[arg-type]
