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
    assert area_of("[ADR-08] Invoice numbering") == "ADR-08"
    assert area_of("[Capability] Ingestion layer") == "Capability"
    assert area_of("RFC 12: Naming") == "RFC"
    assert area_of("Just a page") is None
    # Forty numbered ADRs are one area of forty, not forty areas of one.
    assert area_family("ADR-08") == "ADR"
    assert area_family("ADR-11") == "ADR"
    assert area_family("Capability") == "CAPABILITY"


def test_a_decision_is_recognised_whatever_the_local_acronym():
    assert is_decision("[ADR-08] Invoice numbering", "adr-08.html")
    assert is_decision("RFC 12: Naming", "rfc-12.md")
    assert is_decision("Decision: drop the cache", "notes/decision-cache.html")
    assert not is_decision("[Capability] Ingestion layer", "capability-ingestion.html")


def test_the_pages_and_the_links_between_them_are_read_from_the_folder():
    base = build_knowledge_base(
        [
            _page(
                "index.html",
                '<title>Home</title><a href="[ADR-08]._Invoice.html">ADR 8</a>'
                '<a href="Ingestion.html">Ingestion</a>',
            ),
            _page(
                "[ADR-08]._Invoice.html",
                "<title>Data Platform : [ADR-08] Invoice numbering</title>"
                '<a href="Ingestion.html">the ingestion layer</a>',
            ),
            _page("Ingestion.html", "<h1>[Capability] Ingestion layer</h1>"),
        ],
        all_paths=[
            "index.html",
            "[ADR-08]._Invoice.html",
            "Ingestion.html",
            "[ADR-08]._Invoice_files/flow.drawio",
        ],
    )

    titles = {document.path: document.title for document in base.documents}
    # The page's own title beats the file name the saver mangled — and the space
    # prefix an export puts in front of it is dropped.
    assert titles["[ADR-08]._Invoice.html"] == "[ADR-08] Invoice numbering"
    assert titles["Ingestion.html"] == "[Capability] Ingestion layer"

    assert base.areas == {"ADR": 1, "CAPABILITY": 1}
    assert [d.title for d in base.decisions] == ["[ADR-08] Invoice numbering"]
    # Two pages point at Ingestion; nothing points at the home page.
    assert base.inbound_links["Ingestion.html"] == 2
    # A diagram in the page's companion folder belongs to that page.
    adr = next(d for d in base.documents if d.path == "[ADR-08]._Invoice.html")
    assert adr.diagrams == ["[ADR-08]._Invoice_files/flow.drawio"]


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


def test_an_export_with_no_links_is_reported_as_such_not_as_169_orphans():
    """A browser-saved wiki keeps its links as URLs back to the original site, so
    nothing on disk points at anything else on disk. Every page was then an orphan, and
    Home led with "169 pages nothing links to" — a true sentence about the export
    masquerading as a finding about the writing."""
    from app.core.domain.project_graph_builder import from_knowledge_base

    base = build_knowledge_base(
        [
            _page("a.html", '<a href="https://wiki.example.com/x">the other page</a>'),
            _page("b.html", "<p>no links at all</p>"),
        ]
    )
    assert not base.has_link_graph
    assert base.orphans == []

    _entities, _relations, findings = from_knowledge_base(base)
    titles = [finding.title for finding in findings]
    assert "These pages carry no links to each other" in titles
    assert not any("nothing links to" in title for title in titles)


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


def test_a_repository_is_not_told_it_is_a_wiki():
    """The mirror of the bug we fixed yesterday. An infrastructure monorepo has a
    hundred READMEs among a thousand files: they do not link to one another, were never
    meant to, and "nothing links to it" under each of them is the same category error
    as telling a wiki it has no tests — only pointing the other way."""
    from app.core.domain.project_graph_builder import from_knowledge_base

    pages = [_page(f"modules/m{i}/README.md", "# README\n") for i in range(20)]
    code = [f"modules/m{i}/main.tf" for i in range(240)]
    base = build_knowledge_base(pages, all_paths=[p.path for p in pages] + code)

    assert not base.is_knowledge_base
    assert base.areas == {}
    assert base.inbound_links == {}
    assert base.orphans == []

    entities, _relations, findings = from_knowledge_base(base)
    # The documents are still listed — a person looking for the docs finds them…
    assert len([e for e in entities if e.type == "document"]) == 20
    # …and told apart by where they live, because "README" names none of them.
    assert any(e.name == "modules/m3 · README" for e in entities)
    # …but not one word of a wiki's facts is claimed about them.
    assert findings == []
    assert all("linked_from" not in e.metadata for e in entities)


def test_a_docs_folder_inside_a_repository_is_still_a_knowledge_base():
    """The gate is about what the collection IS, not where it sits: a genuinely
    cross-linked docs site keeps its facts even with code around it."""
    pages = [
        _page("docs/index.md", "".join(f'[p{i}](p{i}.md)' for i in range(1, 10))),
        *[_page(f"docs/p{i}.md", f"# Page {i}\n[home](index.md)") for i in range(1, 10)],
    ]
    base = build_knowledge_base(
        pages,
        all_paths=[p.path for p in pages] + [f"src/mod{i}.py" for i in range(40)],
    )
    assert base.is_knowledge_base
    assert base.has_link_graph


# --------------------------------------------------------------- the whole screen


def test_a_wiki_gets_a_map_of_its_own_and_no_wall_of_absences():
    """The bug, end to end: a folder of documentation used to report ten things it did
    not find. Every line true; the screen as a whole a lie."""
    from app.core.domain.project_graph_builder import build_project_graph
    from app.core.domain.project_intelligence_view import present_project_intelligence
    from app.core.domain.role_lens import Section, role_lens_for

    base = build_knowledge_base(
        [
            _page("index.html", '<title>Home</title><a href="[ADR-08]._Invoice.html">a</a>'),
            _page(
                "[ADR-08]._Invoice.html",
                "<title>[ADR-08] Invoice numbering</title>",
                days_old=400,
            ),
            _page("a.html", '<a href="[ADR-08]._Invoice.html">x</a>'),
            _page("b.html", '<a href="[ADR-08]._Invoice.html">x</a>'),
        ],
        all_paths=["index.html", "[ADR-08]._Invoice.html", "a.html", "b.html"],
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
        "[ADR-08] Invoice numbering"
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


def test_a_wiki_is_not_told_off_for_being_a_wiki():
    """Live review, on a real Confluence export: the app said "No test files were
    found" (in red), asked how dev/staging/prod are separated, and told a Manager the
    scan "did not detect much yet" — about 169 pages. Every sentence about something
    the project never claimed to be."""
    from app.core.domain.project_graph_builder import build_project_graph
    from app.core.domain.project_intelligence_view import present_project_intelligence
    from app.core.domain.role_brief import build_role_brief
    from app.core.domain.role_lens import role_lens_for
    from app.core.domain.test_suites import build_test_facts

    base = build_knowledge_base(
        [
            _page(f"[Capability]_Layer_{i}.html", f"<title>[Capability] Layer {i}</title>")
            for i in range(5)
        ]
        + [_page("[ADR-1]_Choice.html", "<title>[ADR-1] Choice</title>")],
    )
    # The test analyzer runs on every project — including one with no code at all.
    tests = build_test_facts({}, source_paths=[])
    graph = build_project_graph("w", knowledge_base=base, tests=tests)
    view = present_project_intelligence(graph, role_lens_for("manager"))

    titles = [f["title"] for f in view["risks"]["findings"]]
    assert not any("test file" in title.lower() for title in titles)
    assert view["questions"]["questions"] == []
    assert "documentation" in view["summary"]["description"].lower()
    assert "did not detect much" not in build_role_brief(graph, role_lens_for("manager")).focus


def test_a_page_the_export_left_untitled_keeps_the_name_its_author_gave_it():
    """Confluence hands dozens of exported pages the same <title> ("General
    Information"). Taken at face value, the Documents tab became a column of identical
    entries — and so did the decisions list."""
    base = build_knowledge_base(
        [
            _page("Ingestion_layer.html", "<title>General Information</title>"),
            _page("Retention_policy.html", "<title>General Information</title>"),
        ]
    )
    assert sorted(d.title for d in base.documents) == ["Ingestion layer", "Retention policy"]


def test_the_infrastructure_project_lost_nothing_to_all_of_this():
    """The other side of the same rule. Everything above teaches the app to stop
    talking to a wiki about pipelines — it must not have learned to stop talking to a
    Terraform repository about them. Sections follow facts, in both directions."""
    from app.core.domain.analysis import TerraformAnalysisResult, TerragruntAnalysisResult
    from app.core.domain.project_graph_builder import build_project_graph
    from app.core.domain.project_intelligence_view import present_project_intelligence
    from app.core.domain.role_lens import Section, role_lens_for
    from app.core.domain.test_suites import build_test_facts

    terraform = TerraformAnalysisResult(
        workspace_id="w",
        project_path="/p",
        total_terraform_files=2,
        files=["accounts/dev/main.tf", "accounts/prod/main.tf"],
        has_backend_config=True,
        has_provider_config=True,
        has_variables=True,
        has_outputs=True,
        has_modules=True,
        findings=[],
    )
    terragrunt = TerragruntAnalysisResult(
        workspace_id="w",
        project_path="/p",
        total_terragrunt_files=1,
        files=["accounts/prod/terragrunt.hcl"],
        has_remote_state=True,
        has_include_blocks=True,
        has_dependencies=True,
        has_inputs=True,
        has_terraform_source=True,
        findings=[],
    )
    graph = build_project_graph(
        "w",
        terraform=terraform,
        terragrunt=terragrunt,
        # A repo WITH code and no tests still hears about its missing tests.
        tests=build_test_facts({"main.py": "print(1)"}, source_paths=["main.py"]),
    )
    view = present_project_intelligence(graph, role_lens_for("devops"))

    assert view["section_order"][1] == Section.INFRASTRUCTURE
    assert Section.ENVIRONMENTS in view["section_order"]
    assert Section.DOCUMENTS not in view["section_order"]  # no pages here, so no tab
    assert {"dev", "prod"} <= {e["name"] for e in view[Section.ENVIRONMENTS]["environments"]}
    # A repo that HAS code and no tests still hears about it — the tightening was
    # "you cannot fail to test what you never wrote", not "never mention tests".
    assert any("test file" in f["title"].lower() for f in view["risks"]["findings"])
    # And it is still asked the questions only a deployed thing can be asked. (Not the
    # dev/staging/prod one: this repo's environments were found, so that gap is closed.)
    assert any("Terraform state" in q["question"] for q in view["questions"]["questions"])


def test_a_title_is_a_line_not_a_page():
    """Some exported pages have an <h1> that never closes near it. Read literally, the
    "title" became the whole document — screenfuls of prose in a list of page names."""
    runaway = "<h1>Ops runbook " + ("blah " * 200) + "</h1>"
    base = build_knowledge_base([_page("CIF_Data_Model.html", runaway)])
    assert base.documents[0].title == "CIF Data Model"


def test_html_entities_in_a_title_are_read_as_the_characters_they_are():
    base = build_knowledge_base(
        [_page("p.html", "<title>AWS DataSync &ndash; Docs &amp; more</title>")]
    )
    assert base.documents[0].title == "AWS DataSync – Docs & more"
