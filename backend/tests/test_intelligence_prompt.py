"""The prompt is assembled from the project in front of it, and for the person reading.

Before this, every project and every role got the same prompt: a fixed block of
infrastructure, pipelines, environments and counts. A wiki's copy of that block was six
lines of "none detected", so the model wrote the only paragraph those facts supported —
one about absences. These pin the two things that fixed it: the facts follow the
project, and the question follows the role.
"""

from datetime import datetime, timedelta, timezone

from app.core.domain.knowledge_base import PageSource, build_knowledge_base
from app.core.domain.project_graph_builder import build_project_graph
from app.core.domain.project_intelligence_prompt import (
    build_project_intelligence_overview_prompt,
)
from app.core.domain.project_intelligence_view import present_project_intelligence
from app.core.domain.role_lens import role_lens_for
from app.core.domain.sql_schema import build_sql_schema
from app.core.domain.test_suites import build_test_facts

_NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def _wiki_prompt(role: str = "business_analyst") -> str:
    base = build_knowledge_base(
        [
            PageSource(
                "index.html",
                '<title>Home</title><a href="[ADR-08]._Seq.html">a</a>',
                _NOW - timedelta(days=2),
            ),
            PageSource(
                "[ADR-08]._Seq.html",
                "<title>[ADR-08] Sequence generation</title>"
                "<p>The platform writes to an S3 bucket and reads from Aurora.</p>",
                _NOW - timedelta(days=30),
            ),
        ],
        all_paths=["index.html", "[ADR-08]._Seq.html"],
    )
    graph = build_project_graph("w", knowledge_base=base)
    view = present_project_intelligence(graph, role_lens_for(role))
    return build_project_intelligence_overview_prompt(view, view["role_label"])


def test_a_project_is_never_described_by_what_it_does_not_contain():
    prompt = _wiki_prompt()
    # The old prompt handed the model six of these and got a paragraph about absences.
    assert "none detected" not in prompt.lower()
    assert "CI/CD" not in prompt
    assert "ENVIRONMENTS" not in prompt
    # What it does have, it is told about.
    assert "DOCUMENTATION" in prompt
    assert "[ADR-08] Sequence generation" in prompt


def test_a_wiki_is_not_credited_with_the_system_its_pages_describe():
    """The pages name S3 and Aurora; the folder contains neither. "The project uses
    AWS" is a falsehood assembled entirely out of true sentences."""
    prompt = _wiki_prompt()
    assert "body of documentation" in prompt
    assert "the documentation covers" in prompt.lower()
    assert "never" in prompt.lower() and "the project uses" in prompt.lower()


def test_the_facts_arrive_in_the_order_the_role_reads_them():
    graph = build_project_graph(
        "w",
        tests=build_test_facts(
            {"tests/test_login.py": "import pytest\n\ndef test_ok():\n    assert True\n"},
            source_paths=["src/login.py"],
        ),
        sql_schema=build_sql_schema(
            [("db/V1__init.sql", "CREATE TABLE orders (id BIGSERIAL PRIMARY KEY);")]
        ),
    )
    tester = build_project_intelligence_overview_prompt(
        present_project_intelligence(graph, role_lens_for("tester")), "Tester / QA"
    )
    dba = build_project_intelligence_overview_prompt(
        present_project_intelligence(graph, role_lens_for("dba")), "DBA"
    )
    # Same facts, both present; the one the role opens on comes first.
    assert tester.index("TESTS") < tester.index("DATA")
    assert dba.index("DATA") < dba.index("TESTS")


def test_home_does_not_credit_a_wiki_with_the_cloud_its_pages_describe():
    """The same lie, in the other place it was told. Home's summary is written from
    retrieved excerpts, and an ADR reading "we chose Aurora" is indistinguishable from
    a repository that uses Aurora unless the prompt says what the excerpts are made of.
    """
    from app.core.domain.indexing import ContextSearchResult
    from app.core.domain.rag_prompt import (
        build_project_understanding_prompt,
        evidence_is_documentation,
    )

    def _chunk(path: str) -> ContextSearchResult:
        return ContextSearchResult(
            chunk_id=path, source_path=path, content="We chose Aurora.", score=0.9, metadata={}
        )

    pages = [_chunk("[ADR-08]._Seq.html"), _chunk("Ingestion.html"), _chunk("notes/Design.md")]
    code = [_chunk("src/app.py"), _chunk("main.py"), _chunk("README.md")]

    assert evidence_is_documentation(pages)
    assert not evidence_is_documentation(code)

    doc_prompt = build_project_understanding_prompt(pages)
    assert "pages of DOCUMENTATION" in doc_prompt
    assert "the project uses X" in doc_prompt  # …as the thing it must never write
    assert 'empty "run_commands"' in doc_prompt

    # And a real codebase is not lectured about a distinction it does not have.
    assert "pages of DOCUMENTATION" not in build_project_understanding_prompt(code)


def test_the_question_the_paragraph_answers_belongs_to_the_role():
    graph = build_project_graph(
        "w",
        sql_schema=build_sql_schema(
            [("db/V1__init.sql", "CREATE TABLE orders (id BIGSERIAL PRIMARY KEY);")]
        ),
    )
    view = present_project_intelligence(graph, role_lens_for("dba"))
    dba = build_project_intelligence_overview_prompt(view, "DBA")
    tester_view = present_project_intelligence(graph, role_lens_for("tester"))
    tester = build_project_intelligence_overview_prompt(tester_view, "Tester / QA")

    assert "migration" in dba and "dangerous" in dba
    assert "regression" in tester
    # And in neither case is the model given licence to fill the gaps itself.
    for prompt in (dba, tester):
        assert "Use ONLY the facts above" in prompt
        assert "not even ones that projects like this usually have" in prompt
