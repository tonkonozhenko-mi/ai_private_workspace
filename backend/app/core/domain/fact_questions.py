"""From a fact on the map to the question a person would actually ask about it.

The map states things: "3 tables have no primary key", "this page has not changed in
over a year and 6 pages link to it", "the tests are not run in CI". Each one is the
beginning of a thought, and until now the thought ended there — the fact sat on the
dashboard, and turning it into an answer meant re-typing it as a question in Ask,
in your own words, hoping they matched the words in the files.

So each kind of fact carries its own question. Deterministic: a template per finding
kind, filled from the finding's own title and evidence. No model is asked to invent
the question, because the fact already contains everything the question needs — and a
question we generated from a fact is one the index can answer, which is not true of a
question a person guesses at.

The rule for the wording: ask what a colleague would ask, not what a linter would.
"Which pages describe the invoice flow, and which of them is current?" — not "resolve
finding documentation:stale".
"""

from __future__ import annotations

from app.core.domain.project_graph import ProjectFinding

# One template per kind of fact. Keyed by the stable prefix of the finding id, so a
# finding that carries a path ("documentation:stale:notes/Design.html") still matches.
# The values are questions, not commands: the person is asking their project something,
# and the answer will come back with the files it came from.
_QUESTION_BY_FINDING: tuple[tuple[str, str], ...] = (
    (
        "documentation:stale",
        'What does "{subject}" describe, and is any of it contradicted by a newer page?',
    ),
    (
        "documentation:orphan_pages",
        "Which pages does nothing link to, and are any of them still worth reading?",
    ),
    (
        "documentation:no_link_graph",
        "What are the main areas of this documentation, and where should I start?",
    ),
    ("tests:no_tests_found", "How is this project tested today, if at all?"),
    ("tests:not_run_in_ci", "What runs in CI, and why would the tests not be part of it?"),
    ("tests:skipped_cases", "Which tests are skipped, and what did they used to cover?"),
    (
        "tests:areas_no_test_mentions",
        "Which parts of this project are not mentioned by any test, and what could break there unnoticed?",
    ),
    (
        "sql:tables_without_primary_key",
        "Which tables have no primary key, and how are their rows identified in the code?",
    ),
    (
        "sql:unindexed_foreign_keys",
        "Which foreign keys have no index, and which queries join on them?",
    ),
    (
        "sql:unreferenced_tables",
        "Which tables does no code reference, and are they still written to?",
    ),
    (
        "ownership:single_owner_files",
        "Which files has only one person ever touched, and what do they do?",
    ),
    # The analyzers each prefix their own findings ("terraform:…", "kubernetes:…").
    # Anything security- or deployment-shaped that we have no bespoke question for
    # still deserves one, and the finding's own title is the best subject we have.
    ("terraform", 'What does the file behind "{subject}" configure, and what depends on it?'),
    ("kubernetes", 'What does "{subject}" affect when it is deployed?'),
    ("helm", 'What does "{subject}" affect when it is deployed?'),
)


def _subject(finding: ProjectFinding) -> str:
    """The thing the question is about: the quoted name in the title if there is one,
    else the title itself. Titles are written as sentences ('"Design" has not changed
    in over a year'), and the quoted part is the only bit worth putting in a question.
    """
    title = finding.title
    if '"' in title:
        parts = title.split('"')
        if len(parts) >= 3 and parts[1].strip():
            return parts[1].strip()
    return title.rstrip(".")


def question_for_finding(finding: ProjectFinding) -> str | None:
    """The question this fact is the beginning of, or None when we have none to offer.

    None is a real answer: a fact we cannot turn into a question a person would ask is
    better left as a fact than dressed up in a generic "tell me more about this".
    """
    identifier = (finding.id or "").lower()
    for prefix, template in _QUESTION_BY_FINDING:
        if identifier.startswith(prefix):
            return template.format(subject=_subject(finding))
    return None
