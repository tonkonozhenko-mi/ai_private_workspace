"""Groundedness check: flag backticked project terms absent from retrieved text."""

from app.core.domain.rag_answer_evaluator import find_ungrounded_terms


def test_flags_concrete_term_absent_from_context():
    out = find_ungrounded_terms(
        "Enable `FEATURE_TURBO` and point it at the `payments-service`.",
        ["some unrelated retrieved file content about networking"],
    )
    assert "FEATURE_TURBO" in out
    assert "payments-service" in out


def test_does_not_flag_grounded_terms():
    out = find_ungrounded_terms(
        "Enable `FEATURE_TURBO` in the config.",
        ["the config sets FEATURE_TURBO=1 in main.tf"],
    )
    assert out == []


def test_skips_backticked_prose_and_vague_words():
    # `good` has no separator/camel/upper/digit → not a concrete identifier.
    out = find_ungrounded_terms("This looks `good` to me.", ["unrelated content"])
    assert out == []


def test_flags_camelcase_identifier():
    out = find_ungrounded_terms("Call `getUserToken` first.", ["unrelated content"])
    assert out == ["getUserToken"]


def test_excludes_already_flagged_citations():
    out = find_ungrounded_terms(
        "See `infra/ghost.tf` for details.",
        ["unrelated content"],
        already_flagged=["infra/ghost.tf"],
    )
    assert out == []


def test_empty_inputs_are_safe():
    assert find_ungrounded_terms("", ["x"]) == []
    assert find_ungrounded_terms("`X_Y`", []) == []
