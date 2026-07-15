"""A group can hold a conversation, because that is what a group is for.

"What did we decide about report storage?" — "and where is that configured in the
code?" is the question a group exists to answer: the decision lives in the wiki,
the code lives in the repository, and the second question is only a question if
the first one survived. It could not: the group Ask hard-coded `history=[]` and
answered every question as if it were the first.

The mechanics are the single Ask's, moved to a place both can call rather than
copied — copies are how the group spent three releases missing fixes the single
path had.
"""

from app.adapters.memory.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from app.adapters.memory.in_memory_project_group_repository import (
    InMemoryProjectGroupRepository,
)
from app.core.domain.conversation import (
    create_conversation_message,
    create_workspace_conversation,
)
from app.core.domain.indexing import ContextSearchResult
from app.core.domain.project_group import ProjectGroup
from app.core.domain.rag_prompt import answer_mode_tuning
from app.core.use_cases.ask_group_question import (
    AskGroupQuestionInput,
    AskGroupQuestionUseCase,
)

WIKI = "ws-wiki"
CODE = "ws-code"
GROUP = "g1"


class _Workspace:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class _WorkspaceRepo:
    def get(self, workspace_id):
        return {
            WIKI: _Workspace(WIKI, "Wiki"),
            CODE: _Workspace(CODE, "Backend"),
        }.get(workspace_id)


class _Embedding:
    provider_name = "fake"
    model_name = "fake-embed"

    def __init__(self):
        self.embedded: list[str] = []

    def embed_text(self, text):
        self.embedded.append(text)
        return [0.1, 0.2, 0.3]


class _Status:
    def __init__(self, floor=None, ceiling=None):
        self.status = "indexed"
        self.relevance_floor = floor
        self.relevance_probe_ceiling = ceiling


class _StatusRepo:
    def __init__(self, status=None):
        self._status = status or _Status()

    def get(self, workspace_id):
        return self._status


class _VectorStore:
    def __init__(self):
        self.limits: list[int] = []

    def search(self, workspace_id, query_embedding, limit, **kwargs):
        self.limits.append(limit)
        return [
            ContextSearchResult(
                chunk_id=f"{workspace_id}:doc",
                source_path=f"{workspace_id}-doc.md",
                content=f"content from {workspace_id}",
                score=0.8,
                metadata={},
            )
        ]

    def get_source_chunks(self, workspace_id, source_path):
        return []


class _LLM:
    provider_name = "fake"
    model_name = "fake-llm"
    context_window = 8192

    def __init__(self):
        self.calls: list[tuple[str, object]] = []

    def generate(self, prompt, images=None, temperature=None, think=None, history=None):
        self.calls.append((prompt, history))
        return "The answer (Wiki/ws-wiki-doc.md)."


class _Factory:
    def __init__(self):
        self.provider = _LLM()

    def create(self, provider=None, model=None):
        return self.provider


def _build(status=None):
    groups = InMemoryProjectGroupRepository()
    groups.add(
        ProjectGroup(id=GROUP, name="Platform", workspace_ids=(WIKI, CODE), created_at="2026-07-15")
    )
    conversations = InMemoryConversationRepository()
    store = _VectorStore()
    embedder = _Embedding()
    factory = _Factory()
    use_case = AskGroupQuestionUseCase(
        group_repository=groups,
        workspace_repository=_WorkspaceRepo(),
        embedding_provider=embedder,
        vector_store=store,
        llm_provider_factory=factory,
        index_status_repository=_StatusRepo(status),
        conversation_repository=conversations,
    )
    return use_case, conversations, store, embedder, factory


def _turn(conversations, conversation_id: str, question: str, answer: str) -> None:
    """Record a completed exchange, the way the route does after an answer."""
    for role, content in (("user", question), ("assistant", answer)):
        conversations.add_message(
            create_conversation_message(
                conversation_id=conversation_id, workspace_id=GROUP, role=role, content=content
            )
        )


def _ask(use_case, question, conversation_id=None, answer_mode=None):
    return use_case.execute(
        AskGroupQuestionInput(
            group_id=GROUP,
            question=question,
            conversation_id=conversation_id,
            answer_mode=answer_mode,
        )
    )


# --- the thread ----------------------------------------------------------------


def test_the_model_is_given_the_turns_that_came_before():
    use_case, conversations, _store, _embedder, factory = _build()
    conversation = conversations.add_conversation(create_workspace_conversation(GROUP))
    _turn(
        conversations,
        conversation.id,
        "What did we decide about report storage?",
        "Object storage with lifecycle rules.",
    )

    _ask(use_case, "And where is that configured in the code?", conversation.id)

    _prompt, history = factory.provider.calls[-1]
    assert history == [
        ("user", "What did we decide about report storage?"),
        ("assistant", "Object storage with lifecycle rules."),
    ]


def test_a_follow_up_searches_for_what_it_is_about():
    """"Where is that configured?" has no subject. The previous question holds the
    terms, so it steers the search — and only the search."""
    use_case, conversations, _store, embedder, _factory = _build()
    conversation = conversations.add_conversation(create_workspace_conversation(GROUP))
    _turn(conversations, conversation.id, "Where are reports stored?", "Object storage.")

    _ask(use_case, "And where is that configured?", conversation.id)

    searched = embedder.embedded[-1]
    assert "reports" in searched
    assert "And where is that configured?" in searched


def test_a_first_question_carries_no_history():
    use_case, conversations, _store, _embedder, factory = _build()
    conversation = conversations.add_conversation(create_workspace_conversation(GROUP))

    _ask(use_case, "Where are reports stored?", conversation.id)

    _prompt, history = factory.provider.calls[-1]
    assert history is None


def test_a_fresh_thread_starts_the_conversation_over():
    """Reset is a new thread, not an erasure: the old one keeps its turns and the
    new one starts empty — the same as "+ New chat" in a single project."""
    use_case, conversations, _store, embedder, factory = _build()
    first = conversations.add_conversation(create_workspace_conversation(GROUP))
    _turn(conversations, first.id, "Where are reports stored?", "Object storage.")
    second = conversations.add_conversation(create_workspace_conversation(GROUP))

    _ask(use_case, "What runs the tests?", second.id)

    _prompt, history = factory.provider.calls[-1]
    assert history is None
    assert "reports" not in embedder.embedded[-1]


def test_without_a_conversation_repository_the_group_answers_as_it_always_did():
    use_case, _conversations, _store, _embedder, factory = _build()
    use_case.conversation_repository = None

    _ask(use_case, "Where are reports stored?", "some-conversation")

    _prompt, history = factory.provider.calls[-1]
    assert history is None


# --- answer modes --------------------------------------------------------------


def test_only_from_sources_raises_the_bar_for_every_member():
    use_case, _c, _s, _e, _f = _build(status=_Status(floor=0.60))
    # A fake embedder short-circuits the threshold to a fixed test value, and a
    # mode that cannot move the bar is not a mode — so this asks the question the
    # way a real embedder does.
    use_case.embedding_provider.provider_name = "ollama"
    members = [type("_M", (), {"workspace_id": WIKI, "indexed": True})()]

    balanced = use_case._group_threshold(members, None)
    strict = use_case._group_threshold(members, "sources_only")
    deep = use_case._group_threshold(members, "deep")

    assert abs(strict - balanced * answer_mode_tuning("sources_only").threshold_scale) < 1e-9
    assert abs(deep - balanced * answer_mode_tuning("deep").threshold_scale) < 1e-9
    assert deep < balanced < strict


def test_deep_dive_asks_each_member_for_more():
    # per_repo_cap high enough that the candidate pool is driven by the cap rather
    # than by its floor, which is what makes the multiplier visible at all.
    def limits_for(mode):
        use_case, _c, store, _e, _f = _build()
        use_case.execute(
            AskGroupQuestionInput(
                group_id=GROUP,
                question="Where are reports stored?",
                per_repo_cap=10,
                answer_mode=mode,
            )
        )
        return store.limits

    balanced = limits_for(None)
    deep = limits_for("deep")

    # The same multiplier the single Ask uses, applied to every member alike.
    assert answer_mode_tuning("deep").chunk_scale == 2.0
    assert len(deep) == len(balanced) == 2  # both members asked, either way
    assert max(deep) == max(balanced) * 2


def test_a_mode_never_changes_which_repositories_are_consulted():
    for mode in (None, "deep", "sources_only", "explain"):
        use_case, _c, _s, _e, _f = _build()
        answer = _ask(use_case, "Where are reports stored?", answer_mode=mode)
        assert {c.workspace_id for c in answer.contributions} == {WIKI, CODE}, mode
