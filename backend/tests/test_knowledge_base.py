"""A wiki has facts of its own, and they are not the ones a repository has.

Pointed at an exported Confluence space, the app used to report an absence: no
infrastructure, no environments, no pipelines. All true, and all beside the point.
These pin the facts a folder of documentation actually carries — its areas, its
links, its decisions, its stale pages — and the honesty of each: a page nobody links
to is *reported*, not condemned; a page a year old is only a risk when others still
rely on it.
"""

from datetime import datetime, timedelta, timezone

from app.core.domain.knowledge_base import (
    PageSource,
    area_family,
    area_of,
    build_knowledge_base,
    is_decision,
)

_NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def _page(path: str, text: str = "", days_old: int = 1) -> PageSource:
    return PageSource(path=path, text=text, modified_at=_NOW - timedelta(days=days_old))


def test_a_wikis_own_naming_convention_is_its_table_of_contents():
    assert area_of("[ADR-08] Sequence generation") == "ADR-08"
    assert area_of("[Capability] Ingestion layer") == "Capability"
    assert area_of("RFC 12: Naming") == "RFC"
    assert area_of("Just a page") is None
    # Forty numbered ADRs are one area of forty, not forty areas of one.
    assert area_family("ADR-08") == "ADR"
    assert area_family("ADR-11") == "ADR"
    assert area_family("Capability") == "CAPABILITY"


def test_a_decision_is_recognised_whatever_the_local_acronym():
    assert is_decision("[ADR-08] Sequence generation", "adr-08.html")
    assert is_decision("RFC 12: Naming", "rfc-12.md")
    assert is_decision("Decision: drop the cache", "notes/decision-cache.html")
    assert not is_decision("[Capability] Ingestion layer", "capability-ingestion.html")


def test_the_pages_and_the_links_between_them_are_read_from_the_folder():
    base = build_knowledge_base(
        [
            _page(
                "index.html",
                '<title>Home</title><a href="[ADR-08]._Sequence.html">ADR 8</a>'
                '<a href="Ingestion.html">Ingestion</a>',
            ),
            _page(
                "[ADR-08]._Sequence.html",
                "<title>Data Platform : [ADR-08] Sequence generation</title>"
                '<a href="Ingestion.html">the ingestion layer</a>',
            ),
            _page("Ingestion.html", "<h1>[Capability] Ingestion layer</h1>"),
        ],
        all_paths=[
            "index.html",
            "[ADR-08]._Sequence.html",
            "Ingestion.html",
            "[ADR-08]._Sequence_files/flow.drawio",
        ],
    )

    titles = {document.path: document.title for document in base.documents}
    # The page's own title beats the file name the saver mangled — and the space
    # prefix an export puts in front of it is dropped.
    assert titles["[ADR-08]._Sequence.html"] == "[ADR-08] Sequence generation"
    assert titles["Ingestion.html"] == "[Capability] Ingestion layer"

    assert base.areas == {"ADR": 1, "CAPABILITY": 1}
    assert [d.title for d in base.decisions] == ["[ADR-08] Sequence generation"]
    # Two pages point at Ingestion; nothing points at the home page.
    assert base.inbound_links["Ingestion.html"] == 2
    # A diagram in the page's companion folder belongs to that page.
    adr = next(d for d in base.documents if d.path == "[ADR-08]._Sequence.html")
    assert adr.diagrams == ["[ADR-08]._Sequence_files/flow.drawio"]


def test_a_link_to_a_page_that_was_never_exported_is_not_counted():
    """Counting links we cannot follow would inflate every number downstream."""
    base = build_knowledge_base(
        [_page("a.html", '<a href="https://example.com">out</a><a href="ghost.html">ghost</a>')]
    )
    assert base.documents[0].links_to == []


def test_the_home_page_is_not_accused_of_being_an_orphan():
    base = build_knowledge_base(
        [
            _page("index.html", '<a href="a.html">a</a>'),
            _page("a.html", ""),
            _page("forgotten.html", ""),
        ]
    )
    orphans = {document.path for document in base.orphans}
    # An entry point is an orphan by definition — saying so would be noise.
    assert orphans == {"forgotten.html"}


def test_an_old_page_is_only_a_risk_when_others_still_rely_on_it():
    base = build_knowledge_base(
        [
            _page("old-and-loved.html", "", days_old=500),
            _page("old-and-ignored.html", "", days_old=500),
            _page("a.html", '<a href="old-and-loved.html">x</a>'),
            _page("b.html", '<a href="old-and-loved.html">x</a>'),
            _page("c.html", '<a href="old-and-loved.html">x</a>'),
        ]
    )
    stale = [document.path for document in base.stale_but_relied_on(now=_NOW)]
    # Documentation is allowed to be stable. It is only expensive when a page is out
    # of date AND everybody still points at it.
    assert stale == ["old-and-loved.html"]


# --------------------------------------------------------------- the whole screen


def test_a_wiki_gets_a_map_of_its_own_and_no_wall_of_absences():
    """The bug, end to end: a folder of documentation used to report ten things it did
    not find. Every line true; the screen as a whole a lie."""
    from app.core.domain.project_graph_builder import build_project_graph
    from app.core.domain.project_intelligence_view import present_project_intelligence
    from app.core.domain.role_lens import Section, role_lens_for

    base = build_knowledge_base(
        [
            _page("index.html", '<title>Home</title><a href="[ADR-08]._Seq.html">a</a>'),
            _page(
                "[ADR-08]._Seq.html",
                "<title>[ADR-08] Sequence generation</title>",
                days_old=400,
            ),
            _page("a.html", '<a href="[ADR-08]._Seq.html">x</a>'),
            _page("b.html", '<a href="[ADR-08]._Seq.html">x</a>'),
        ],
        all_paths=["index.html", "[ADR-08]._Seq.html", "a.html", "b.html"],
    )
    graph = build_project_graph("w", knowledge_base=base)
    view = present_project_intelligence(graph, role_lens_for("business_analyst"))

    # The sections this project HAS — and not one "no infrastructure detected".
    assert Section.DOCUMENTS in view["section_order"]
    assert Section.INFRASTRUCTURE not in view["section_order"]
    assert Section.ENVIRONMENTS not in view["section_order"]
    assert Section.DEPLOYMENT not in view["section_order"]
    # Risks stays, because an empty risks list is itself the good news — and here it
    # is not empty: a decision everyone links to has not moved in over a year.
    assert Section.RISKS in view["section_order"]
    assert any("has not changed in over a year" in f["title"] for f in view["risks"]["findings"])
    assert [d["name"] for d in view[Section.DOCUMENTS]["decisions"]] == [
        "[ADR-08] Sequence generation"
    ]


def test_every_kind_of_project_gets_the_sections_it_actually_has():
    """The general rule, not a special case for wikis: a code repository shows code
    and tests, a data project shows its schema, a wiki shows its pages — and none of
    them is shown a wall of things it does not contain."""
    from app.core.domain.project_graph_builder import build_project_graph
    from app.core.domain.project_intelligence_view import present_project_intelligence
    from app.core.domain.role_lens import Section, role_lens_for
    from app.core.domain.sql_schema import build_sql_schema
    from app.core.domain.test_suites import build_test_facts

    code_and_tests = build_project_graph(
        "w",
        tests=build_test_facts(
            {"tests/test_api.py": "import pytest\n\ndef test_ok():\n    assert True\n"},
            source_paths=["src/api.py"],
        ),
        sql_schema=build_sql_schema(
            [("db/V1__init.sql", "CREATE TABLE orders (id BIGSERIAL PRIMARY KEY);")]
        ),
    )
    view = present_project_intelligence(code_and_tests, role_lens_for("tester"))
    sections = view["section_order"]

    # The tester's project leads with tests, and the schema it happens to contain is
    # offered too — but nothing invites them to read about environments it does not have.
    assert sections[1] == Section.TESTS
    assert Section.DATA in sections
    assert Section.ENVIRONMENTS not in sections
    assert Section.DOCUMENTS not in sections
    assert view[Section.TESTS]["suites"]
    assert [t["name"] for t in view[Section.DATA]["tables"]] == ["orders"]
