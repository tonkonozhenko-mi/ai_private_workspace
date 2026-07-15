"""Following the address a superseded page leaves behind.

#247 taught the app to notice "Superseded by [ADR-08]" and say so. The live
re-run (2026-07-15) showed what noticing alone buys: the model stopped quoting
the dead decision and started inventing the live one — "stored in S3", from a
page that was not in its context. Told a replacement exists and shown nothing
else, a model will fill the gap itself.

The page names its successor. The successor is in the same index. Fetching it is
a lookup, not a guess.
"""

from app.core.domain.indexing import ContextSearchResult, SourceChunk
from app.core.domain.rag_prompt import build_source_status_section
from app.core.domain.supersession import resolve_successor_path, supersession_target
from app.core.use_cases.ask_workspace_question import AskWorkspaceQuestionUseCase

ADR_05 = (
    "[source: wiki/[ADR-05]_Report_storage.md › Status]\n"
    "## Status\n"
    "**Superseded by [[ADR-08] Report storage v2]([ADR-08]_Report_storage_v2.md).**\n\n"
    "## Decision (historical)\n"
    "Statements were stored on the application server's local disk.\n"
)
ADR_08_BODY = (
    "[source: wiki/[ADR-08]_Report_storage_v2.md › Status]\n"
    "## Status\nAccepted, supersedes [[ADR-05] Report storage].\n\n"
    "## Decision\nStatements are stored in object storage with lifecycle rules.\n"
)


PATHS = [
    "wiki/[ADR-05]_Report_storage.md",
    "wiki/[ADR-08]_Report_storage_v2.md",
    "wiki/[Policy]_Data_retention.md",
]


def _result(path: str, content: str, score: float = 0.7) -> ContextSearchResult:
    return ContextSearchResult(
        chunk_id=f"ws:{path}:0", source_path=path, content=content, score=score, metadata={}
    )


# --- reading the address -------------------------------------------------------


def test_a_markdown_link_gives_the_path():
    line = "**Superseded by [[ADR-08] Report storage v2]([ADR-08]_Report_storage_v2.md).**"
    assert supersession_target(line) == "[ADR-08]_Report_storage_v2.md"


def test_a_wiki_link_gives_the_title():
    assert supersession_target("Superseded by [[Report storage v2]]") == "Report storage v2"


def test_bare_prose_gives_what_follows_the_phrase():
    assert supersession_target("Status: superseded by ADR-08, see migration notes") == "ADR-08"


def test_every_way_a_page_can_name_its_successor_leads_to_the_same_page():
    """The contract is the destination, not the syntax. A wiki exporter, a person
    typing by hand and a linter all write this line differently; each has to
    arrive at the same file."""
    for line in (
        "**Superseded by [[ADR-08] Report storage v2]([ADR-08]_Report_storage_v2.md).**",
        "Superseded by [[ADR-08] Report storage v2]",
        "Status: superseded by [ADR-08] Report storage v2",
        "Superseded by ADR-08 Report storage v2.",
    ):
        target = supersession_target(line)
        assert target is not None, line
        assert resolve_successor_path(target, PATHS) == "wiki/[ADR-08]_Report_storage_v2.md", line


def test_a_page_that_only_says_it_is_dead_points_nowhere():
    assert supersession_target("Status: Deprecated.") is None
    assert supersession_target("") is None


# --- finding it in the index ---------------------------------------------------


def test_resolved_by_the_tail_of_the_path():
    assert resolve_successor_path("[ADR-08]_Report_storage_v2.md", PATHS) == (
        "wiki/[ADR-08]_Report_storage_v2.md"
    )


def test_resolved_by_the_page_title_when_the_pointer_has_no_path():
    # "[ADR-08] Report storage v2" is the same page as "[ADR-08]_Report_storage_v2.md",
    # written once by a person and once by the exporter.
    assert resolve_successor_path("[ADR-08] Report storage v2", PATHS) == (
        "wiki/[ADR-08]_Report_storage_v2.md"
    )


def test_a_successor_that_is_not_indexed_resolves_to_nothing():
    assert resolve_successor_path("[ADR-99]_Something_else.md", PATHS) is None


# --- the jump ------------------------------------------------------------------


class _Store:
    def get_source_chunks(self, workspace_id, source_path):
        if source_path == "wiki/[ADR-08]_Report_storage_v2.md":
            return [SourceChunk(chunk_index=0, chunk_id="ws:adr08:0", content=ADR_08_BODY)]
        return []


def _use_case() -> AskWorkspaceQuestionUseCase:
    use_case = AskWorkspaceQuestionUseCase(
        workspace_repository=None,
        embedding_provider=None,
        vector_store=_Store(),
        llm_provider_factory=None,
        index_status_repository=None,
    )
    use_case.index_manifest_repository = type(
        "_Manifest", (), {"get": lambda _self, _wid: {path: {} for path in PATHS}}
    )()
    return use_case


def test_the_successor_is_fetched_and_outranks_the_page_that_named_it():
    retrieved = [
        _result("wiki/[ADR-05]_Report_storage.md", ADR_05, score=0.8),
        _result("wiki/[Policy]_Data_retention.md", "## Retention\nSeven years.", score=0.5),
    ]

    followed = _use_case()._follow_supersession("ws", retrieved)

    paths = [r.source_path for r in followed]
    assert "wiki/[ADR-08]_Report_storage_v2.md" in paths
    # The replacement takes the dead page's place; the dead page goes last, so a
    # tight budget keeps the live decision and drops the history.
    assert paths.index("wiki/[ADR-08]_Report_storage_v2.md") < paths.index(
        "wiki/[ADR-05]_Report_storage.md"
    )
    assert paths[-1] == "wiki/[ADR-05]_Report_storage.md"


def test_a_successor_already_retrieved_is_not_fetched_twice():
    retrieved = [
        _result("wiki/[ADR-05]_Report_storage.md", ADR_05),
        _result("wiki/[ADR-08]_Report_storage_v2.md", ADR_08_BODY),
    ]
    followed = _use_case()._follow_supersession("ws", retrieved)
    assert len(followed) == 2


def test_nothing_to_follow_leaves_the_context_untouched():
    retrieved = [_result("main.tf", 'resource "aws_s3_bucket" "reports" {}')]
    assert _use_case()._follow_supersession("ws", retrieved) == retrieved


# --- what the prompt then says -------------------------------------------------


def test_the_prompt_says_the_replacement_is_here():
    section = build_source_status_section(
        [
            _result("wiki/[ADR-05]_Report_storage.md", ADR_05),
            _result("wiki/[ADR-08]_Report_storage_v2.md", ADR_08_BODY),
        ]
    )
    assert "its replacement `wiki/[ADR-08]_Report_storage_v2.md` is included below" in section
    # Nothing is missing, so no anti-fabrication clause is needed.
    assert "you have not read it" not in section


def test_the_prompt_forbids_inventing_a_replacement_it_did_not_find():
    section = build_source_status_section([_result("wiki/[ADR-05]_Report_storage.md", ADR_05)])
    assert "its replacement" not in section
    assert "you have not read it" in section
    assert "do not name a technology it might use" in section
