"""Investigator: ReAct parser/prompt (pure) + the read-only agent loop."""

from types import SimpleNamespace

from app.core.domain.investigator import (
    AgentStep,
    ToolSpec,
    build_investigator_prompt,
    parse_agent_step,
    render_transcript,
)
from app.core.use_cases.investigate_project import (
    InvestigateProjectInput,
    InvestigateProjectUseCase,
)

_ALLOWED = {"search_code", "read_file", "graph_query", "list_files"}


def test_parse_action_variants():
    assert parse_agent_step("ACTION: search_code: db", _ALLOWED).tool == "search_code"
    d = parse_agent_step("ACTION: read_file(app/main.py)", _ALLOWED)
    assert d.kind == "action" and d.tool == "read_file" and d.tool_input == "app/main.py"
    d2 = parse_agent_step('ACTION: search_code "x y"', _ALLOWED)
    assert d2.tool_input == "x y"


def test_parse_final_and_invalid():
    assert parse_agent_step("FINAL: it uses Postgres", _ALLOWED).kind == "final"
    assert parse_agent_step("ACTION: bogus: x", _ALLOWED).kind == "invalid"
    assert parse_agent_step("hello", _ALLOWED).kind == "invalid"


def test_prompt_includes_tools_question_and_transcript():
    steps = [AgentStep("look", "search_code", "db", "found db.tf")]
    prompt = build_investigator_prompt(
        "How is the DB configured?",
        [ToolSpec("search_code", "search_code: <q>", "search")],
        steps,
    )
    assert "How is the DB configured?" in prompt
    assert "search_code: <q>" in prompt
    assert "OBSERVATION: found db.tf" in prompt
    assert "OBSERVATION: found db.tf" in render_transcript(steps)


# --- loop test with a scripted local model + real (fake-backed) tools ---

_WS = SimpleNamespace(id="w1", project_path="/p")


class _WSRepo:
    def get(self, wid):
        return _WS if wid == "w1" else None


class _ScriptedProvider:
    def __init__(self, replies):
        self._replies = list(replies)

    def generate(self, prompt, **kw):
        return self._replies.pop(0) if self._replies else "FINAL: done"


class _Factory:
    def __init__(self, provider):
        self._provider = provider

    def create(self, provider=None, model=None):
        return self._provider


class _Embed:
    provider_name = "fake"
    model_name = "fake"

    def embed_text(self, text):
        return [0.0, 0.0]


class _Vector:
    def search(self, **kw):
        return [
            SimpleNamespace(
                chunk_id="c1", source_path="db/config.tf",
                content="resource aws_db_instance main { engine = postgres }",
                score=0.9, metadata={},
            )
        ]


class _FS:
    def read_text_file(self, root_path, relative_path):
        return "engine = postgres\n" if relative_path == "db/config.tf" else ""


class _GraphRepo:
    def get_latest_graph(self, wid):
        return None


class _ScanRepo:
    def get_latest_scan(self, wid):
        return SimpleNamespace(files=[SimpleNamespace(path="db/config.tf")])


def _use_case(replies):
    return InvestigateProjectUseCase(
        workspace_repository=_WSRepo(),
        llm_provider_factory=_Factory(_ScriptedProvider(replies)),
        embedding_provider=_Embed(),
        vector_store=_Vector(),
        file_system=_FS(),
        project_graph_repository=_GraphRepo(),
        project_scan_repository=_ScanRepo(),
    )


def test_agent_loop_searches_then_answers_with_sources():
    uc = _use_case(
        [
            "THOUGHT: find db config\nACTION: search_code: database engine",
            "ACTION: read_file: db/config.tf",
            "FINAL: The project uses PostgreSQL (db/config.tf).",
        ]
    )
    result = uc.execute(InvestigateProjectInput(workspace_id="w1", question="Which database?"))
    assert "PostgreSQL" in result.answer
    assert result.stopped_reason == "answered"
    assert "db/config.tf" in result.sources
    assert [s.tool for s in result.steps] == ["search_code", "read_file"]


def test_agent_loop_budget_exhausted_forces_final():
    # Always asks to search, never finalises → budget runs out → forced final.
    uc = _use_case(["ACTION: search_code: x"] * 10 + ["From the files, it's Postgres."])
    result = uc.execute(
        InvestigateProjectInput(workspace_id="w1", question="db?", max_steps=3)
    )
    assert result.stopped_reason == "budget_exhausted"
    assert result.used_steps == 3
    assert result.answer


def test_agent_invalid_replies_break_gracefully():
    uc = _use_case(["nonsense", "still nonsense", "more nonsense", "FINAL: x"])
    result = uc.execute(InvestigateProjectInput(workspace_id="w1", question="q", max_steps=8))
    # Two invalids recorded, then it breaks to a forced final.
    assert result.answer
