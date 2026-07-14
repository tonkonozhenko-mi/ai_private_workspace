"""A decision that has been overruled says so in its first line.

"Superseded by [ADR-08]" — and the model read straight past it, and reported the
local disk that ADR-05 chose as where the reports are stored today, three months
after ADR-08 moved them to object storage (mixed-group run, 2026-07-14). The page
was small enough to fit in the context whole, so nothing was lost in retrieval:
the model simply did not notice. Noticing is not something to hope for. The app
reads the marker itself, names the file, and quotes the line back.

The second half of the same run: asked whether anything enforced a retention
period, the answer was that it "may be implemented in the code and would need
further investigation". Nothing enforced it. A hedge sounds like knowledge
without being knowledge, and is worse than the honest no.
"""

from app.core.domain.indexing import ContextSearchResult
from app.core.domain.rag_prompt import (
    build_source_status_section,
    build_workspace_question_prompt,
    superseded_sources,
)

# The real page from the wiki corpus, as it reaches the prompt (contextual header
# included, because that is what the chunker prepends).
ADR_05 = (
    "[source: wiki/[ADR-05]_Report_storage.md › Status]\n"
    "## Status\n"
    "**Superseded by [[ADR-08] Report storage v2]([ADR-08]_Report_storage_v2.md).**\n\n"
    "## Decision (historical)\n"
    "Monthly statements were rendered to PDF and stored on the application server's "
    "local disk under `/var/reports`.\n"
)
ADR_08 = (
    "[source: wiki/[ADR-08]_Report_storage_v2.md › Status]\n"
    "## Status\n"
    "Accepted, supersedes [[ADR-05] Report storage]([ADR-05]_Report_storage.md).\n\n"
    "## Decision\n"
    "Statements are stored in object storage with lifecycle rules.\n"
)


def _result(path: str, content: str) -> ContextSearchResult:
    return ContextSearchResult(
        chunk_id=f"ws:{path}:0", source_path=path, content=content, score=0.7, metadata={}
    )


def test_a_superseded_page_is_recognised_by_its_own_status_line():
    found = superseded_sources([_result("wiki/[ADR-05]_Report_storage.md", ADR_05)])
    assert len(found) == 1
    path, line = found[0]
    assert path == "wiki/[ADR-05]_Report_storage.md"
    assert "Superseded by" in line


def test_the_page_that_did_the_superseding_is_not_itself_marked():
    """ADR-08 says it *supersedes* ADR-05 — that is a claim about another page, and
    marking the live decision as dead would be the same bug facing the other way."""
    assert superseded_sources([_result("wiki/[ADR-08]_Report_storage_v2.md", ADR_08)]) == []


def test_a_deprecation_mentioned_in_the_body_is_not_a_status():
    body = (
        "[source: app/api/client.py]\n"
        "def fetch(url):\n"
        "    # We used to call the deprecated v1 endpoint here.\n"
        "    return get(url)\n"
    )
    assert superseded_sources([_result("app/api/client.py", body)]) == []


def test_the_prompt_names_the_superseded_source_and_says_what_to_do():
    section = build_source_status_section([_result("wiki/[ADR-05]_Report_storage.md", ADR_05)])
    assert "[ADR-05]_Report_storage.md" in section
    assert "Superseded by" in section
    assert "current state" in section


def test_a_prompt_with_no_stale_sources_carries_no_status_section():
    assert build_source_status_section([_result("main.tf", "resource \"aws_s3_bucket\" {}")]) == ""


def test_the_grounded_prompt_carries_the_warning_above_the_context():
    prompt = build_workspace_question_prompt(
        question="Where are monthly statements stored?",
        context_results=[
            _result("wiki/[ADR-05]_Report_storage.md", ADR_05),
            _result("wiki/[ADR-08]_Report_storage_v2.md", ADR_08),
        ],
    )
    assert "declare themselves out of date" in prompt
    # The warning must arrive before the model reads the page it is about.
    assert prompt.index("declare themselves out of date") < prompt.index("Context chunks:")
    assert "[ADR-05]" in prompt


def test_the_prompt_forbids_the_hedge():
    prompt = build_workspace_question_prompt(
        question="Does anything enforce a retention period?",
        context_results=[_result("app/main.py", "print('hello')")],
    )
    assert "If the answer is no, say no" in prompt
    assert "further investigation" in prompt  # named as the thing not to write
