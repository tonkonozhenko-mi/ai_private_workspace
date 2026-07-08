"""The handbook pseudo-path is shown to the model as a friendly label, never as the
raw __project_handbook__ token — in the grounded prompt, the answer cleanup, and the
grounding evaluator."""

from app.core.domain.handbook_source import (
    HANDBOOK_DISPLAY_NAME,
    HANDBOOK_SOURCE_PATH,
    display_source_path,
    mask_handbook_token,
)
from app.core.domain.indexing import ContextSearchResult
from app.core.domain.rag import RagSource
from app.core.domain.rag_answer_cleanup import (
    soften_handbook_identifier,
    strip_source_path_echo,
)
from app.core.domain.rag_answer_evaluator import evaluate_rag_answer
from app.core.domain.rag_prompt import build_workspace_question_prompt


def test_display_source_path_maps_only_the_handbook():
    assert display_source_path(HANDBOOK_SOURCE_PATH) == HANDBOOK_DISPLAY_NAME
    assert display_source_path("backend/app/main.py") == "backend/app/main.py"


def test_mask_handbook_token_inside_a_chunk_id():
    assert mask_handbook_token(f"w:{HANDBOOK_SOURCE_PATH}:0") == f"w:{HANDBOOK_DISPLAY_NAME}:0"
    assert mask_handbook_token("w:backend/app/main.py:0") == "w:backend/app/main.py:0"


def _handbook_result():
    return ContextSearchResult(
        chunk_id=f"w:{HANDBOOK_SOURCE_PATH}:0",
        source_path=HANDBOOK_SOURCE_PATH,
        content="# Project handbook\nOverview of the project.",
        score=0.9,
        metadata={},
    )


def test_grounded_prompt_never_shows_the_raw_token():
    prompt = build_workspace_question_prompt("what is this project about?", [_handbook_result()])
    assert HANDBOOK_SOURCE_PATH not in prompt
    assert HANDBOOK_DISPLAY_NAME in prompt


def test_grounded_prompt_leaves_real_paths_unchanged():
    result = ContextSearchResult(
        chunk_id="w:backend/app/main.py:0",
        source_path="backend/app/main.py",
        content="x",
        score=0.9,
        metadata={},
    )
    prompt = build_workspace_question_prompt("q", [result])
    assert "backend/app/main.py" in prompt


def test_cleanup_softens_an_echoed_raw_token_in_prose():
    text = "Details are in the README.md and the `__project_handbook__` document this."
    softened = soften_handbook_identifier(text)
    assert HANDBOOK_SOURCE_PATH not in softened
    assert HANDBOOK_DISPLAY_NAME in softened
    # strip_source_path_echo applies the same softening as part of its cleanup.
    assert HANDBOOK_SOURCE_PATH not in strip_source_path_echo(text)


def test_evaluator_accepts_the_friendly_label_as_a_mentioned_source():
    sources = [
        RagSource(
            chunk_id=f"w:{HANDBOOK_SOURCE_PATH}:0",
            source_path=HANDBOOK_SOURCE_PATH,
            score=0.9,
            preview="x",
        )
    ]
    warnings = evaluate_rag_answer(
        "q",
        "The Project handbook describes the architecture.",
        sources,
        ["# Project handbook architecture"],
    )
    assert "answer_missing_source_paths" not in [w.code for w in warnings]
