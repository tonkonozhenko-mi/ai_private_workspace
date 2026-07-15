"""Naming a file that does not exist is the hallucination this app exists to refuse.

The group answer of 2026-07-15 said the backend configures storage "in main.tf in
the Terraform directory". That project contains no Terraform and no main.tf. The
check that should have caught it was already there and looked straight past it,
for two reasons, both of them ours:

* it only read between backticks — the form the prompt *asks* for, not the form a
  model uses when it is making something up;
* the warning it raised was advisory, not one of the codes that trigger the
  corrective pass, so the answer shipped with a note nobody acts on.

Both are closed here. The evidence now includes the retrieved file contents, so a
file a document merely mentions still counts as read rather than invented.
"""

from app.core.domain.rag import RagSource
from app.core.domain.rag_answer_evaluator import evaluate_rag_answer, find_unsupported_citations
from app.core.use_cases.ask_workspace_question import _HARD_GROUNDING_CODES

SOURCES = [RagSource(chunk_id="1", source_path="app/main.py", score=0.7, preview="")]
CONTENTS = ["from fastapi import FastAPI\n\napp = FastAPI()\n"]


def _codes(answer: str, contents=None) -> set[str]:
    warnings = evaluate_rag_answer(
        question="Where does the backend configure storage?",
        answer=answer,
        sources=SOURCES,
        source_contents=contents if contents is not None else CONTENTS,
    )
    return {w.code for w in warnings}


# --- the sentence that started this --------------------------------------------


def test_a_file_named_in_plain_prose_is_caught():
    # The real answer, in the language it was written in and in English: no
    # backticks anywhere.
    assert "answer_cited_unknown_source" in _codes(
        "Storage configuration lives in main.tf in the Terraform directory (app/main.py)."
    )
    assert "answer_cited_unknown_source" in _codes(
        "Конфігурація в файлі main.tf в директорії Terraform (app/main.py)."
    )


def test_naming_a_file_that_does_not_exist_now_triggers_the_corrective_pass():
    assert "answer_cited_unknown_source" in _HARD_GROUNDING_CODES


# --- and what it must not catch ------------------------------------------------


def test_a_file_the_evidence_mentions_was_read_not_invented():
    # A README that tells you to edit main.tf is where the model got the name;
    # repeating it is grounded, whatever the retrieved paths happen to be.
    contents = ["# Setup\n\nEdit main.tf before running terraform apply.\n"]
    assert "answer_cited_unknown_source" not in _codes(
        "Edit main.tf as the setup notes say (app/main.py).", contents
    )


def test_citing_a_retrieved_file_by_its_bare_name_is_fine():
    sources = [RagSource(chunk_id="1", source_path="infra/prod/main.tf", score=0.7, preview="")]
    assert (
        find_unsupported_citations(
            "The backend is set in `main.tf`.", [s.source_path for s in sources]
        )
        == []
    )


def test_ordinary_prose_is_not_mistaken_for_a_filename():
    # "version 2.0", "e.g." and friends have dots but are not files.
    assert (
        find_unsupported_citations(
            "The app targets version 2.0 of the API, e.g. for the /orders route.",
            ["app/main.py"],
        )
        == []
    )


def test_an_answer_naming_nothing_is_not_flagged():
    assert "answer_cited_unknown_source" not in _codes(
        "The retrieved files do not configure storage (app/main.py)."
    )
