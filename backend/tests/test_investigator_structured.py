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
