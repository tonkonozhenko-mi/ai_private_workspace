"""A group is several projects, and a pointer belongs to the one that wrote it.

#250 taught the single-workspace Ask to follow "Superseded by X". The group Ask
gathers its context member by member and never reached that code, so the live
re-run of the mixed-group question found ADR-05 presented as current all over
again — the one screenshot that had looked fixed was a ranking accident, not a
mechanism.

The successor is looked up in the index of the member whose page carried the
pointer. A wiki's link addresses a page in the wiki; the repository sitting
beside it in the group has nothing to do with it.
"""

from app.adapters.memory.in_memory_project_group_repository import (
    InMemoryProjectGroupRepository,
)
from app.core.domain.indexing import ContextSearchResult, SourceChunk
from app.core.domain.project_group import ProjectGroup
from app.core.use_cases.ask_group_question import (
    AskGroupQuestionInput,
    AskGroupQuestionUseCase,
)

ADR_05 = (
    "[source: wiki/[ADR-05]_Report_storage.md › Status]\n"
    "## Status\n"
    "**Superseded by [[ADR-08] Report storage v2]([ADR-08]_Report_storage_v2.md).**\n\n"
    "## Decision (historical)\nStored on the application server's local disk.\n"
)
ADR_08 = (
    "[source: wiki/[ADR-08]_Report_storage_v2.md › Status]\n"
    "## Status\nAccepted.\n\n"
    "## Decision\nStored in object storage with lifecycle rules.\n"
)

WIKI = "ws-wiki"
CODE = "ws-code"


class _Workspace:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class _WorkspaceRepo:
    def __init__(self, workspaces):
        self._w = {w.id: w for w in workspaces}

    def get(self, workspace_id):
        return self._w.get(workspace_id)


class _Embedding:
    provider_name = "fake"
    model_name = "fake-embed"

    def embed_text(self, text):
        return [0.1, 0.2, 0.3]


class _StatusRepo:
    def get(self, workspace_id):
        return type("_S", (), {"status": "indexed"})()


class _VectorStore:
    """The wiki member retrieves ADR-05 (and only ADR-05); the code member
    retrieves a source file. ADR-08 exists in the wiki's index but does not match
    the question — which is the whole situation being tested."""

    def __init__(self):
        self.fetched: list[tuple[str, str]] = []

    def search(self, workspace_id, query_embedding, limit, **kwargs):
        if workspace_id == WIKI:
            return [
                ContextSearchResult(
                    chunk_id=f"{WIKI}:adr05",
                    source_path="wiki/[ADR-05]_Report_storage.md",
                    content=ADR_05,
                    score=0.8,
                    metadata={},
                )
            ]
        return [
            ContextSearchResult(
                chunk_id=f"{CODE}:main",
                source_path="app/main.py",
                content="print('hello')",
                score=0.6,
                metadata={},
            )
        ]

    def get_source_chunks(self, workspace_id, source_path):
        self.fetched.append((workspace_id, source_path))
        if workspace_id == WIKI and source_path == "wiki/[ADR-08]_Report_storage_v2.md":
            return [SourceChunk(chunk_index=0, chunk_id=f"{WIKI}:adr08", content=ADR_08)]
        return []


class _Manifest:
    """Each member has its own index. Only the wiki holds the ADRs."""

    def get(self, workspace_id):
        if workspace_id == WIKI:
            return {
                "wiki/[ADR-05]_Report_storage.md": {},
                "wiki/[ADR-08]_Report_storage_v2.md": {},
            }
        return {"app/main.py": {}}


class _LLMProvider:
    provider_name = "fake"
    model_name = "fake-llm"

    def __init__(self):
        self.prompts: list[str] = []

    def generate(self, prompt, images=None, temperature=None, think=None, history=None):
        self.prompts.append(prompt)
        return "Statements are in object storage (wiki/[ADR-08]_Report_storage_v2.md)."


class _LLMFactory:
    def __init__(self):
        self.provider = _LLMProvider()

    def create(self, provider=None, model=None):
        return self.provider


def _build(manifest=_Manifest()):
    groups = InMemoryProjectGroupRepository()
    groups.add(
        ProjectGroup(
            id="g1", name="Platform", workspace_ids=(WIKI, CODE), created_at="2026-07-15"
        )
    )
    store = _VectorStore()
    factory = _LLMFactory()
    use_case = AskGroupQuestionUseCase(
        group_repository=groups,
        workspace_repository=_WorkspaceRepo(
            [_Workspace(WIKI, "Wiki"), _Workspace(CODE, "Backend")]
        ),
        embedding_provider=_Embedding(),
        vector_store=store,
        llm_provider_factory=factory,
        index_status_repository=_StatusRepo(),
        index_manifest_repository=manifest,
    )
    return use_case, store, factory


def _ask(use_case):
    return use_case.execute(
        AskGroupQuestionInput(
            group_id="g1",
            question="What did we decide about where reports are stored?",
            limit=6,
        )
    )


def test_the_successor_is_pulled_into_the_group_answer():
    use_case, store, factory = _build()

    answer = _ask(use_case)

    paths = [source.source_path for source in answer.sources]
    assert any("[ADR-08]" in path for path in paths), paths
    # It reaches the model, not just the source list.
    assert "[ADR-08]_Report_storage_v2.md" in factory.provider.prompts[0]


def test_the_successor_is_looked_for_in_the_index_that_named_it():
    """The pointer is the wiki's. Asking the code repository for a page the wiki
    mentions would be looking for it in the wrong project."""
    use_case, store, _factory = _build()

    _ask(use_case)

    assert (WIKI, "wiki/[ADR-08]_Report_storage_v2.md") in store.fetched
    # Never anywhere else: a group has several indexes, and this page lives in one.
    # (Other fetches are parent-document expansion, which is a different errand.)
    assert (CODE, "wiki/[ADR-08]_Report_storage_v2.md") not in store.fetched


def test_the_successor_keeps_its_place_when_the_group_re_sorts_by_score():
    """A group merges every member's results and sorts them by score. A successor
    scored 0 would sink below the cut; it inherits the score of the page that
    named it instead."""
    use_case, _store, _factory = _build()

    answer = _ask(use_case)

    order = [source.source_path for source in answer.sources]
    assert order.index("wiki/[ADR-08]_Report_storage_v2.md") < order.index(
        "wiki/[ADR-05]_Report_storage.md"
    )


def test_without_a_manifest_the_group_ask_is_exactly_as_it_was():
    use_case, store, _factory = _build(manifest=None)

    answer = _ask(use_case)

    assert not any("[ADR-08]" in source.source_path for source in answer.sources)
    # No pointer was followed — the only fetches are parent-document expansion of
    # what retrieval actually found.
    assert (WIKI, "wiki/[ADR-08]_Report_storage_v2.md") not in store.fetched
