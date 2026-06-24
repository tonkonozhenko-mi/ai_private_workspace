"""Group Ask: fan-out retrieval, per-repo budget, repo-tagged sources."""

from app.adapters.memory.in_memory_project_group_repository import (
    InMemoryProjectGroupRepository,
)
from app.core.domain.indexing import ContextSearchResult
from app.core.domain.project_group import ProjectGroup
from app.core.use_cases.ask_group_question import (
    AskGroupQuestionInput,
    AskGroupQuestionUseCase,
)
from app.core.use_cases.manage_project_groups import ManageProjectGroupsUseCase


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


class _Status:
    def __init__(self, status):
        self.status = status


class _StatusRepo:
    def __init__(self, indexed_ids):
        self._indexed = set(indexed_ids)

    def get(self, workspace_id):
        return _Status("indexed" if workspace_id in self._indexed else "not_indexed")


class _VectorStore:
    """Returns canned chunks per workspace, sorted by score desc, capped to limit."""

    def __init__(self, by_workspace):
        self._by = by_workspace  # {workspace_id: [(path, score), ...]}

    def search(self, workspace_id, query_embedding, limit, **kwargs):
        rows = sorted(self._by.get(workspace_id, []), key=lambda r: r[1], reverse=True)
        return [
            ContextSearchResult(
                chunk_id=f"{workspace_id}:{path}",
                source_path=path,
                content=f"content of {path}",
                score=score,
                metadata={},
            )
            for path, score in rows[:limit]
        ]


class _LLMProvider:
    provider_name = "fake"
    model_name = "fake-llm"

    def __init__(self):
        self.last_prompt = None

    def generate(self, prompt, images=None, temperature=None, think=None, history=None):
        self.last_prompt = prompt
        return "ANSWER"


class _LLMFactory:
    def __init__(self):
        self.provider = _LLMProvider()

    def create(self, provider=None, model=None):
        return self.provider


def _build(group_members, vector_rows, indexed_ids, workspaces):
    group_repo = InMemoryProjectGroupRepository()
    group = ProjectGroup(
        id="g1", name="Platform", workspace_ids=tuple(group_members), created_at="2026-06-01"
    )
    group_repo.add(group)
    factory = _LLMFactory()
    uc = AskGroupQuestionUseCase(
        group_repository=group_repo,
        workspace_repository=_WorkspaceRepo(workspaces),
        embedding_provider=_Embedding(),
        vector_store=_VectorStore(vector_rows),
        llm_provider_factory=factory,
        index_status_repository=_StatusRepo(indexed_ids),
    )
    return uc, factory


def test_empty_group_returns_diagnostic():
    repo = InMemoryProjectGroupRepository()
    uc = ManageProjectGroupsUseCase(repo)
    g = uc.create("Empty")
    ask = AskGroupQuestionUseCase(
        group_repository=repo,
        workspace_repository=_WorkspaceRepo([]),
        embedding_provider=_Embedding(),
        vector_store=_VectorStore({}),
        llm_provider_factory=_LLMFactory(),
        index_status_repository=_StatusRepo([]),
    )
    res = ask.execute(AskGroupQuestionInput(group_id=g.id, question="hi"))
    assert res.diagnostic_code == "group_empty"
    assert res.sources == []


def test_no_indexed_members_returns_no_context():
    uc, _ = _build(
        group_members=["w1", "w2"],
        vector_rows={"w1": [("a.py", 0.9)]},
        indexed_ids=[],  # nothing indexed
        workspaces=[_Workspace("w1", "api"), _Workspace("w2", "web")],
    )
    res = uc.execute(AskGroupQuestionInput(group_id="g1", question="where is auth"))
    assert res.diagnostic_code == "group_no_context"
    assert len(res.contributions) == 2
    assert all(c.indexed is False for c in res.contributions)


def test_merges_and_tags_sources_by_repo():
    uc, factory = _build(
        group_members=["w1", "w2"],
        vector_rows={
            "w1": [("auth.py", 0.95), ("util.py", 0.40)],
            "w2": [("login.ts", 0.80)],
        },
        indexed_ids=["w1", "w2"],
        workspaces=[_Workspace("w1", "api"), _Workspace("w2", "web")],
    )
    res = uc.execute(AskGroupQuestionInput(group_id="g1", question="how does login work", limit=6))
    assert res.answer == "ANSWER"
    # highest score first; source keeps the raw path + a separate repo label
    top = res.sources[0]
    assert top.source_path == "auth.py" and top.workspace_name == "api" and top.workspace_id == "w1"
    assert any(s.workspace_name == "web" and s.source_path == "login.ts" for s in res.sources)
    # the prompt, however, cites the repo-prefixed path so the model attributes it
    assert "api/auth.py" in factory.provider.last_prompt
    # contributions reflect how many chunks each repo supplied
    by_id = {c.workspace_id: c.chunks_used for c in res.contributions}
    assert by_id["w1"] == 2 and by_id["w2"] == 1


class _StreamProvider:
    provider_name = "fake"
    model_name = "fake-llm"

    def generate(self, prompt, images=None, temperature=None, think=None, history=None):
        return "FULL"

    def generate_stream(self, prompt, images=None, temperature=None, think=None, history=None):
        yield "AN"
        yield "SWER"


class _StreamFactory:
    def create(self, provider=None, model=None):
        return _StreamProvider()


class _Stats:
    def __init__(self, memory_items, graph_facts):
        self.memory_items = memory_items
        self.graph_facts = graph_facts


class _ContextProvider:
    """compose_with_stats per workspace, like the real composer."""

    def __init__(self, by_workspace):
        self._by = by_workspace  # {wid: (text, memory, facts)}

    def compose_with_stats(self, workspace_id, query):
        text, mem, facts = self._by.get(workspace_id, ("", 0, 0))
        return text, _Stats(mem, facts)


def test_execute_stream_yields_tokens_then_final():
    group_repo = InMemoryProjectGroupRepository()
    group_repo.add(ProjectGroup(id="g1", name="P", workspace_ids=("w1",), created_at="2026-06-01"))
    uc = AskGroupQuestionUseCase(
        group_repository=group_repo,
        workspace_repository=_WorkspaceRepo([_Workspace("w1", "api")]),
        embedding_provider=_Embedding(),
        vector_store=_VectorStore({"w1": [("a.py", 0.9)]}),
        llm_provider_factory=_StreamFactory(),
        index_status_repository=_StatusRepo(["w1"]),
    )
    events = list(uc.execute_stream(AskGroupQuestionInput(group_id="g1", question="q")))
    tokens = [e.text for e in events if hasattr(e, "text")]
    finals = [e.answer for e in events if hasattr(e, "answer")]
    assert tokens == ["AN", "SWER"]
    assert len(finals) == 1 and finals[0].answer == "ANSWER"
    assert finals[0].used_context_chunks == 1


def test_context_provider_counts_are_summed_across_repos():
    group_repo = InMemoryProjectGroupRepository()
    group_repo.add(
        ProjectGroup(id="g1", name="P", workspace_ids=("w1", "w2"), created_at="2026-06-01")
    )
    uc = AskGroupQuestionUseCase(
        group_repository=group_repo,
        workspace_repository=_WorkspaceRepo([_Workspace("w1", "api"), _Workspace("w2", "web")]),
        embedding_provider=_Embedding(),
        vector_store=_VectorStore({"w1": [("a", 0.9)], "w2": [("b", 0.8)]}),
        llm_provider_factory=_LLMFactory(),
        index_status_repository=_StatusRepo(["w1", "w2"]),
        project_context_provider=_ContextProvider(
            {
                "w1": ("prod is called prd", 2, 1),
                "w2": ("uses postgres", 1, 3),
            }
        ),
    )
    res = uc.execute(AskGroupQuestionInput(group_id="g1", question="db?"))
    assert res.memory_used == 3  # 2 + 1
    assert res.facts_used == 4  # 1 + 3


def test_per_repo_cap_limits_one_repo():
    uc, _ = _build(
        group_members=["w1", "w2"],
        vector_rows={
            "w1": [("a", 0.99), ("b", 0.98), ("c", 0.97), ("d", 0.96)],  # 4 strong hits
            "w2": [("z", 0.50)],
        },
        indexed_ids=["w1", "w2"],
        workspaces=[_Workspace("w1", "api"), _Workspace("w2", "web")],
    )
    res = uc.execute(AskGroupQuestionInput(group_id="g1", question="q", limit=6, per_repo_cap=2))
    by_id = {c.workspace_id: c.chunks_used for c in res.contributions}
    assert by_id["w1"] == 2  # capped, not 4
    assert by_id["w2"] == 1
