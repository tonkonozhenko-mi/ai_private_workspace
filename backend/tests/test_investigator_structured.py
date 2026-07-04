"""Investigator structured (JSON-schema) decision path.

Covers the pure schema/parser and the use-case branch that asks a
structured-output-capable engine for JSON steps, with graceful fallback to the
text parser when the reply is not JSON.
"""

import json
from types import SimpleNamespace

from app.core.domain.investigator import (
    agent_step_schema,
    build_investigator_prompt,
    parse_structured_step,
)
from app.core.use_cases.investigate_project import (
    InvestigateProjectInput,
    InvestigateProjectUseCase,
)

_ALLOWED = {"search_code", "read_file", "graph_query"}


# --- pure schema + parser --------------------------------------------------


def test_schema_is_strict_object_with_required_fields():
    schema = agent_step_schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"thought", "next", "tool", "tool_input", "answer"}
    assert schema["properties"]["next"]["enum"] == ["action", "final"]


def test_schema_tool_is_free_string_without_allowed():
    schema = agent_step_schema()
    assert schema["properties"]["tool"] == {"type": "string"}


def test_schema_enum_constrains_tool_when_allowed_given():
    schema = agent_step_schema({"search_code", "read_file"})
    tool = schema["properties"]["tool"]
    # Grammar can only emit a real tool name or "" (final step) — never a blank
    # or hallucinated tool that the parser would reject as (format).
    assert tool["enum"] == ["read_file", "search_code", ""]


def test_parse_structured_action():
    text = json.dumps(
        {
            "thought": "find the db config",
            "next": "action",
            "tool": "search_code",
            "tool_input": "database engine",
            "answer": "",
        }
    )
    d = parse_structured_step(text, _ALLOWED)
    assert d.kind == "action"
    assert d.tool == "search_code"
    assert d.tool_input == "database engine"
    assert d.thought == "find the db config"


def test_parse_structured_final_wins():
    text = json.dumps(
        {"thought": "", "next": "final", "tool": "", "tool_input": "", "answer": "Postgres"}
    )
    d = parse_structured_step(text, _ALLOWED)
    assert d.kind == "final"
    assert d.answer == "Postgres"


def test_parse_structured_unknown_tool_is_invalid_with_tool():
    text = json.dumps(
        {"thought": "", "next": "action", "tool": "rm_rf", "tool_input": "/", "answer": ""}
    )
    d = parse_structured_step(text, _ALLOWED)
    assert d.kind == "invalid"
    # tool is set so the use case will NOT fall back to the text parser.
    assert d.tool == "rm_rf"


def test_parse_structured_bad_json_is_invalid_without_tool():
    d = parse_structured_step("not json at all", _ALLOWED)
    assert d.kind == "invalid"
    assert d.tool == ""  # signals the use case to retry with the text parser


def test_structured_prompt_describes_json_protocol():
    prompt = build_investigator_prompt("How is the DB set up?", [], [], structured=True)
    assert '"next"' in prompt
    assert "JSON object" in prompt
    # The text-protocol markers must NOT appear in structured mode.
    assert "ACTION:" not in prompt


# --- use-case loop with a structured-capable scripted engine ---------------

_WS = SimpleNamespace(id="w1", project_path="/p")


class _WSRepo:
    def get(self, wid):
        return _WS if wid == "w1" else None


class _StructuredProvider:
    """Scripted engine that advertises structured output and returns JSON steps.

    Records whether each call received a ``response_format`` so the test can
    assert the use case actually used the structured path.
    """

    supports_structured_output = True

    def __init__(self, replies):
        self._replies = list(replies)
        self.formats_seen = []

    def generate(self, prompt, response_format=None, **kw):
        self.formats_seen.append(response_format)
        return self._replies.pop(0) if self._replies else '{"next":"final","answer":"done"}'


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
                chunk_id="c1",
                source_path="db/config.tf",
                content="engine = postgres",
                score=0.9,
                metadata={},
            )
        ]


class _FS:
    def read_text_file(self, root_path, relative_path):
        return "engine = postgres\n"


class _GraphRepo:
    def get_latest_graph(self, wid):
        return None


class _ScanRepo:
    def get_latest_scan(self, wid):
        return SimpleNamespace(files=[SimpleNamespace(path="db/config.tf")])


class _GitHistory:
    def file_activity(self, project_path, relative_path=None):
        return None


def _use_case(provider):
    return InvestigateProjectUseCase(
        workspace_repository=_WSRepo(),
        llm_provider_factory=_Factory(provider),
        embedding_provider=_Embed(),
        vector_store=_Vector(),
        file_system=_FS(),
        project_graph_repository=_GraphRepo(),
        project_scan_repository=_ScanRepo(),
        git_history=_GitHistory(),
    )


def test_graph_tools_hidden_when_no_map_built():
    # With no project map, graph_query/ci_triggers would only ever return
    # "build first" — so they must not be offered (no dead-end loop).
    uc = _use_case(_StructuredProvider([]))
    tools, specs = uc._build_tools("w1", "/p")
    assert "graph_query" not in tools
    assert "ci_triggers" not in tools
    assert "search_code" in tools and "read_file" in tools
    names = {s.name for s in specs}
    assert "graph_query" not in names and "ci_triggers" not in names


def test_graph_tools_present_when_map_built():
    class _GraphRepoWithMap:
        def get_latest_graph(self, wid):
            return SimpleNamespace(entities=[], relations=[], findings=[])

    uc = InvestigateProjectUseCase(
        workspace_repository=_WSRepo(),
        llm_provider_factory=_Factory(_StructuredProvider([])),
        embedding_provider=_Embed(),
        vector_store=_Vector(),
        file_system=_FS(),
        project_graph_repository=_GraphRepoWithMap(),
        project_scan_repository=_ScanRepo(),
        git_history=_GitHistory(),
    )
    tools, specs = uc._build_tools("w1", "/p")
    assert "graph_query" in tools and "ci_triggers" in tools


def test_structured_schema_constrains_tool_to_enum_on_the_wire():
    # The response_format actually sent to the engine must carry the tool enum,
    # so the grammar forbids blank/hallucinated tools.
    provider = _StructuredProvider(
        [json.dumps({"thought": "", "next": "final", "tool": "", "tool_input": "", "answer": "ok"})]
    )
    _use_case(provider).execute(InvestigateProjectInput(workspace_id="w1", question="q"))
    schema = provider.formats_seen[0]["json_schema"]["schema"]
    tool_enum = schema["properties"]["tool"].get("enum")
    assert tool_enum is not None
    assert "search_code" in tool_enum and "" in tool_enum
    # graph tools absent (no map) → not in the enum either
    assert "graph_query" not in tool_enum


class _TextProvider:
    """A text-protocol engine (no structured support) — exercises the path used by
    Ollama and any model that doesn't honour a grammar."""

    supports_structured_output = False

    def __init__(self, replies):
        self._replies = list(replies)

    def generate(self, prompt, response_format=None, **kw):
        return self._replies.pop(0) if self._replies else "FINAL: done"


def test_format_failures_do_not_consume_tool_budget():
    # Two unparseable replies, then a real action + final. Even with max_steps=2,
    # the format stumbles must NOT eat the tool budget — the agent still gets to
    # act and answer. This is the engine-agnostic robustness fix.
    provider = _TextProvider(
        [
            "some rambling with no action or final",
            "still not the right format",
            "ACTION: search_code: database engine",
            "FINAL: PostgreSQL (db/config.tf).",
        ]
    )
    result = _use_case(provider).execute(
        InvestigateProjectInput(workspace_id="w1", question="Which database?", max_steps=2)
    )
    assert result.stopped_reason == "answered"
    assert "PostgreSQL" in result.answer
    assert [s.tool for s in result.steps if s.tool != "(format)"] == ["search_code"]
    assert len([s for s in result.steps if s.tool == "(format)"]) == 2


def test_repeated_identical_action_is_short_circuited_and_stops():
    # The model keeps asking for the SAME action that returns nothing — the agent
    # must not re-run it forever; it nudges, then stops and forces a final.
    provider = _TextProvider(
        [
            "ACTION: list_files: nonexistent",
            "ACTION: list_files: nonexistent",
            "ACTION: list_files: nonexistent",
            "ACTION: list_files: nonexistent",
            "ACTION: list_files: nonexistent",
        ]
    )
    result = _use_case(provider).execute(
        InvestigateProjectInput(workspace_id="w1", question="where is x?", max_steps=8)
    )
    assert result.stopped_reason == "budget_exhausted"
    # The tool ran once; the rest were caught as repeats, not re-executed.
    real_runs = [
        s for s in result.steps if s.tool == "list_files" and "already ran" not in s.observation
    ]
    assert len(real_runs) == 1
    repeats = [s for s in result.steps if "already ran" in s.observation]
    assert 1 <= len(repeats) <= _repeat_cap() + 1


def _repeat_cap():
    from app.core.use_cases.investigate_project import _MAX_REPEATED_ACTIONS

    return _MAX_REPEATED_ACTIONS


def test_list_files_tolerates_glob_syntax():
    # "*.tf" is a glob; the tool matches on substring. It must still find main.tf.
    uc = _use_case(_TextProvider([]))
    tools, _ = uc._build_tools("w1", "/p")
    # _ScanRepo lists db/config.tf
    out, _ = tools["list_files"]("*.tf")
    assert "db/config.tf" in out
    out2, _ = tools["list_files"]("**/*.tf")
    assert "db/config.tf" in out2


def test_exhausted_format_retries_forces_final_instead_of_looping():
    provider = _TextProvider(["nope, wrong format"] * 12)
    result = _use_case(provider).execute(
        InvestigateProjectInput(workspace_id="w1", question="q", max_steps=4)
    )
    assert result.stopped_reason == "budget_exhausted"
    # Bounded: it did not spin forever on malformed replies.
    assert len([s for s in result.steps if s.tool == "(format)"]) <= 4


def test_render_transcript_turns_invalid_step_into_a_correction():
    from app.core.domain.investigator import AgentStep, render_transcript

    text = render_transcript(
        [
            AgentStep(
                thought="",
                tool="(format)",
                tool_input="",
                observation="No ACTION or FINAL found. Reply with exactly one.",
            )
        ]
    )
    assert "NOTE:" in text and "required format" in text
    # It must NOT pretend the model took an action it didn't.
    assert "ACTION: (format)" not in text


def test_structured_loop_uses_schema_and_answers():
    provider = _StructuredProvider(
        [
            json.dumps(
                {
                    "thought": "find db",
                    "next": "action",
                    "tool": "search_code",
                    "tool_input": "database engine",
                    "answer": "",
                }
            ),
            json.dumps(
                {
                    "thought": "",
                    "next": "final",
                    "tool": "",
                    "tool_input": "",
                    "answer": "PostgreSQL (db/config.tf).",
                }
            ),
        ]
    )
    result = _use_case(provider).execute(
        InvestigateProjectInput(workspace_id="w1", question="Which database?")
    )
    assert "PostgreSQL" in result.answer
    assert [s.tool for s in result.steps] == ["search_code"]
    assert "db/config.tf" in result.sources
    # The structured path passed a JSON-schema response_format on each step.
    assert provider.formats_seen[0] is not None
    assert provider.formats_seen[0]["type"] == "json_schema"


def test_structured_loop_falls_back_to_text_on_non_json():
    # Engine claims structured support but replies in the text protocol; the loop
    # must still parse it via the lenient fallback rather than stalling.
    provider = _StructuredProvider(
        [
            "ACTION: search_code: database engine",
            "FINAL: It uses PostgreSQL (db/config.tf).",
        ]
    )
    result = _use_case(provider).execute(
        InvestigateProjectInput(workspace_id="w1", question="Which database?")
    )
    assert "PostgreSQL" in result.answer
    assert [s.tool for s in result.steps] == ["search_code"]
