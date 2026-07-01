"""Answer modes: pure steering clauses injected into the RAG prompt."""

from app.core.domain.indexing import ContextSearchResult
from app.core.domain.rag_prompt import (
    AnswerMode,
    answer_mode_instructions,
    build_workspace_question_prompt,
)


def _ctx():
    return [
        ContextSearchResult(
            chunk_id="c1",
            source_path="main.tf",
            content="terraform backend s3",
            score=0.9,
            metadata={},
        )
    ]


def test_normalize_defaults_to_safe():
    assert AnswerMode.normalize(None) == AnswerMode.SAFE
    assert AnswerMode.normalize("") == AnswerMode.SAFE
    assert AnswerMode.normalize("nonsense") == AnswerMode.SAFE
    assert AnswerMode.normalize("SOURCES_ONLY") == AnswerMode.SOURCES_ONLY


def test_safe_mode_adds_no_clause():
    assert answer_mode_instructions(None) == ""
    assert answer_mode_instructions(AnswerMode.SAFE) == ""


def test_each_non_safe_mode_has_a_distinct_clause():
    clauses = {
        answer_mode_instructions(m)
        for m in (AnswerMode.SOURCES_ONLY, AnswerMode.DEEP, AnswerMode.EXPLAIN)
    }
    assert len(clauses) == 3
    assert all(c for c in clauses)


def test_sources_only_forbids_outside_knowledge():
    text = answer_mode_instructions(AnswerMode.SOURCES_ONLY).lower()
    assert "strictly" in text
    assert "outside knowledge" in text


def test_prompt_includes_mode_section_only_when_non_safe():
    safe = build_workspace_question_prompt(
        question="q", context_results=_ctx(), answer_mode="safe"
    )
    strict = build_workspace_question_prompt(
        question="q", context_results=_ctx(), answer_mode="sources_only"
    )
    assert "Answer mode:" not in safe
    assert "Answer mode:" in strict
    assert "STRICTLY" in strict


def test_prompt_backward_compatible_without_mode():
    # Existing callers that never pass answer_mode keep the old prompt shape.
    assert "Answer mode:" not in build_workspace_question_prompt(
        question="q", context_results=_ctx()
    )
