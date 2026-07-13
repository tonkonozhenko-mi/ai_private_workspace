"""A fact on the map is the beginning of a question. It should finish it for you.

The dashboard states things — "3 tables have no primary key", "this page has not
changed in over a year and 6 pages link to it" — and the only way to act on one was to
re-type it as a question in Ask, in your own words, hoping they matched the words in
the files. These pin the questions each kind of fact carries with it.
"""

from app.core.domain.fact_questions import question_for_finding
from app.core.domain.project_graph import FindingCategory, ProjectFinding, Severity


def _finding(identifier: str, title: str = "Something was found") -> ProjectFinding:
    return ProjectFinding(
        id=identifier,
        category=FindingCategory.GENERAL,
        severity=Severity.LOW,
        title=title,
        explanation="",
        analyzer="test",
    )


def test_the_question_names_the_thing_the_fact_is_about():
    """A finding's title quotes the page; the question should ask about that page, not
    about "documentation:stale:notes/Design.html"."""
    question = question_for_finding(
        _finding(
            "documentation:stale:notes/Design.html",
            '"[ADR-08] Invoice numbering" has not changed in over a year',
        )
    )
    assert question == (
        'What does "[ADR-08] Invoice numbering" describe, and is any of it '
        "contradicted by a newer page?"
    )


def test_each_kind_of_fact_asks_what_a_colleague_would_ask():
    assert "not mentioned by any test" in question_for_finding(
        _finding("tests:areas_no_test_mentions")
    )
    assert "no primary key" in question_for_finding(_finding("sql:tables_without_primary_key"))
    assert "only one person" in question_for_finding(_finding("ownership:single_owner_files"))
    # …and every one of them is a question, not an instruction.
    for identifier in (
        "tests:no_tests_found",
        "tests:not_run_in_ci",
        "sql:unindexed_foreign_keys",
        "documentation:orphan_pages",
        "documentation:no_link_graph",
    ):
        assert question_for_finding(_finding(identifier)).endswith("?")


def test_a_fact_we_have_no_good_question_for_is_left_alone():
    """Better a fact with no button than a button that asks "tell me more about this"."""
    assert question_for_finding(_finding("something:we:have:never:seen")) is None


def test_the_question_travels_with_the_finding_into_the_view():
    from app.core.domain.project_graph_builder import build_project_graph
    from app.core.domain.project_intelligence_view import present_project_intelligence
    from app.core.domain.role_lens import Section, role_lens_for
    from app.core.domain.sql_schema import build_sql_schema

    graph = build_project_graph(
        "w",
        sql_schema=build_sql_schema([("db/V1.sql", "CREATE TABLE orders (id int);")]),
    )
    view = present_project_intelligence(graph, role_lens_for("dba"))
    findings = view[Section.RISKS]["findings"]
    assert findings, "a table with no primary key is a finding"
    assert any(f["ask"] and f["ask"].endswith("?") for f in findings)
