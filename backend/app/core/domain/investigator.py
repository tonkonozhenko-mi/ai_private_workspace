"""ReAct scaffolding for the read-only Investigator agent.

The agent answers a question by repeatedly choosing ONE read-only tool, reading
its result, and continuing — until it can answer. Because local models are not
reliable at structured tool-calling, the protocol is plain text that we parse
ourselves (a strict-but-lenient ReAct format), with validation and graceful
fallback. Everything here is pure and deterministic; the LLM call and tool
execution are injected by the use case.
"""

import json
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolSpec:
    name: str
    usage: str  # e.g. "search_code: <query>"
    description: str


@dataclass(frozen=True)
class AgentStep:
    thought: str
    tool: str
    tool_input: str
    observation: str


@dataclass(frozen=True)
class AgentDecision:
    kind: str  # "action" | "final" | "invalid"
    thought: str = ""
    tool: str = ""
    tool_input: str = ""
    answer: str = ""
    error: str = ""
    raw: str = ""


_THOUGHT_RE = re.compile(r"(?im)^\s*THOUGHT\s*:\s*(.+?)\s*$")
_FINAL_RE = re.compile(r"(?is)\bFINAL(?:\s+ANSWER)?\s*:\s*(.+)\Z")
_ACTION_RE = re.compile(r"(?is)\bACTION\s*:\s*(.+?)(?:\n\s*\n|\nOBSERVATION|\Z)")


def parse_agent_step(text: str, allowed_tools: set[str]) -> AgentDecision:
    """Parse one model turn into an action or a final answer.

    Accepts ``ACTION: tool: input``, ``ACTION: tool(input)`` and
    ``ACTION: tool input``. ``FINAL:`` (or ``FINAL ANSWER:``) takes priority.
    """
    raw = text or ""
    thought_match = _THOUGHT_RE.search(raw)
    thought = thought_match.group(1).strip() if thought_match else ""

    final_match = _FINAL_RE.search(raw)
    if final_match:
        answer = final_match.group(1).strip()
        return AgentDecision(kind="final", thought=thought, answer=answer, raw=raw)

    action_match = _ACTION_RE.search(raw)
    if action_match:
        body = action_match.group(1).strip()
        tool, tool_input = _split_action(body)
        if not tool:
            return AgentDecision(
                kind="invalid", thought=thought, error="Could not read a tool name.", raw=raw
            )
        if tool not in allowed_tools:
            return AgentDecision(
                kind="invalid",
                thought=thought,
                tool=tool,
                error=f"Unknown tool '{tool}'. Allowed: {', '.join(sorted(allowed_tools))}.",
                raw=raw,
            )
        return AgentDecision(
            kind="action", thought=thought, tool=tool, tool_input=tool_input, raw=raw
        )

    return AgentDecision(
        kind="invalid",
        thought=thought,
        error="No ACTION or FINAL found. Reply with exactly one.",
        raw=raw,
    )


def _split_action(body: str) -> tuple[str, str]:
    # Tool name is the leading identifier; the rest (after ':' '(' or space) is input.
    name_match = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)", body.strip())
    if not name_match:
        return "", ""
    tool = name_match.group(1)
    rest = body[name_match.end() :].strip()
    if rest.startswith("(") and rest.endswith(")"):
        rest = rest[1:-1].strip()
    elif rest.startswith(":"):
        rest = rest[1:].strip()
    # Strip wrapping quotes if present.
    if len(rest) >= 2 and rest[0] in "\"'" and rest[-1] == rest[0]:
        rest = rest[1:-1]
    return tool, rest.strip()


# -- structured (JSON-schema) variant ---------------------------------------
#
# When the provider can constrain output to a JSON Schema (llama.cpp), we ask for
# one decision as a JSON object instead of the loose text protocol. The model
# then *cannot* emit a malformed step, so parsing is exact. Providers without
# this capability (e.g. Ollama) keep using the text protocol above, and a JSON
# parse failure also degrades gracefully back to it.

_STRUCTURED_FIELDS = ("thought", "next", "tool", "tool_input", "answer")


def agent_step_schema() -> dict:
    """JSON Schema for one investigator decision.

    Every field is required so the grammar is fully determined; the model fills
    the irrelevant ones with empty strings (e.g. ``answer`` is "" for an action,
    ``tool``/``tool_input`` are "" for a final). ``next`` is constrained to the
    two legal moves. The tool name is validated against the live tool set by the
    parser rather than baked into the schema, so a "final" step needn't name a
    tool.
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "thought": {"type": "string"},
            "next": {"type": "string", "enum": ["action", "final"]},
            "tool": {"type": "string"},
            "tool_input": {"type": "string"},
            "answer": {"type": "string"},
        },
        "required": list(_STRUCTURED_FIELDS),
    }


def parse_structured_step(text: str, allowed_tools: set[str]) -> AgentDecision:
    """Parse a JSON decision object into an :class:`AgentDecision`.

    Mirrors :func:`parse_agent_step`'s validation (final wins, tool must be
    allowed). Returns ``kind="invalid"`` with ``raw`` preserved on malformed
    JSON so the caller can fall back to the text parser.
    """
    raw = text or ""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return AgentDecision(kind="invalid", error="Output was not valid JSON.", raw=raw)
    if not isinstance(data, dict):
        return AgentDecision(kind="invalid", error="Output was not a JSON object.", raw=raw)

    thought = str(data.get("thought") or "").strip()
    answer = str(data.get("answer") or "").strip()
    tool = str(data.get("tool") or "").strip()
    tool_input = str(data.get("tool_input") or "").strip()
    nxt = str(data.get("next") or "").strip().lower()

    # A concrete final answer wins, mirroring the text protocol.
    if nxt == "final" or (answer and not tool):
        if not answer:
            return AgentDecision(
                kind="invalid", thought=thought, error="Final step had no answer.", raw=raw
            )
        return AgentDecision(kind="final", thought=thought, answer=answer, raw=raw)

    if not tool:
        return AgentDecision(
            kind="invalid", thought=thought, error="Could not read a tool name.", raw=raw
        )
    if tool not in allowed_tools:
        return AgentDecision(
            kind="invalid",
            thought=thought,
            tool=tool,
            error=f"Unknown tool '{tool}'. Allowed: {', '.join(sorted(allowed_tools))}.",
            raw=raw,
        )
    return AgentDecision(
        kind="action", thought=thought, tool=tool, tool_input=tool_input, raw=raw
    )


def render_transcript(steps: list[AgentStep]) -> str:
    blocks: list[str] = []
    for step in steps:
        lines = []
        if step.thought:
            lines.append(f"THOUGHT: {step.thought}")
        lines.append(f"ACTION: {step.tool}: {step.tool_input}")
        lines.append(f"OBSERVATION: {step.observation}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def build_investigator_prompt(
    question: str,
    tools: list[ToolSpec],
    steps: list[AgentStep],
    role_label: str = "engineer",
    structured: bool = False,
) -> str:
    tool_lines = "\n".join(f"- {t.usage} — {t.description}" for t in tools)
    transcript = render_transcript(steps)
    transcript_block = f"\n{transcript}\n" if transcript else "\n"
    protocol = _STRUCTURED_PROTOCOL if structured else _TEXT_PROTOCOL
    return (
        f"You are a careful, read-only investigator helping a {role_label} understand "
        "an unfamiliar software project. You answer ONLY from what the tools return — "
        "never from outside knowledge or assumptions.\n\n"
        "You can use exactly these read-only tools (one per step):\n"
        f"{tool_lines}\n\n"
        f"{protocol}\n\n"
        "Rules:\n"
        "- One action per reply. Do not invent observations.\n"
        "- Base every claim on tool results; if the tools don't show it, say it "
        "isn't visible in the project.\n"
        "- Prefer searching and reading real files over guessing.\n\n"
        f"Question: {question}\n"
        f"{transcript_block}"
        "Your reply:"
    )


_TEXT_PROTOCOL = (
    "Protocol — reply with EXACTLY ONE of:\n"
    "  THOUGHT: <one short sentence on what you need next>\n"
    "  ACTION: <tool>: <input>\n"
    "or, when you have enough evidence:\n"
    "  FINAL: <a concise answer that cites the files/entities you relied on>\n\n"
    "Example:\n"
    "  THOUGHT: I need to find where the database is configured.\n"
    "  ACTION: search_code: database connection settings"
)

_STRUCTURED_PROTOCOL = (
    "Reply with a single JSON object with these fields:\n"
    '  "thought": one short sentence on what you need next\n'
    '  "next": "action" to use a tool, or "final" when you can answer\n'
    '  "tool": the tool name to use (only when next is "action"; otherwise "")\n'
    '  "tool_input": the input for that tool (only when next is "action"; otherwise "")\n'
    '  "answer": a concise answer citing the files/entities you relied on '
    '(only when next is "final"; otherwise "")\n\n'
    "Example (action):\n"
    '  {"thought": "I need to find where the database is configured.", '
    '"next": "action", "tool": "search_code", '
    '"tool_input": "database connection settings", "answer": ""}'
)


@dataclass(frozen=True)
class InvestigationResult:
    answer: str
    steps: list[AgentStep] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    used_steps: int = 0
    stopped_reason: str = "answered"  # answered | budget_exhausted | no_answer
    memory_used: int = 0
    facts_used: int = 0
