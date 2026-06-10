from dataclasses import dataclass

from app.core.domain.model_catalog import LocalModelDefinition


@dataclass(frozen=True)
class AgentCapability:
    provider: str
    model: str
    display_name: str
    model_type: str
    readiness: str
    planning_supported: bool
    tool_calling_supported: bool
    json_mode_supported: bool
    safe_execution_supported: bool
    supported_agent_modes: list[str]
    recommended_use: str
    guardrails: list[str]
    evidence: list[str]
    limitations: list[str]


@dataclass(frozen=True)
class AgentCapabilityCatalog:
    summary: str
    models: list[AgentCapability]
    recommended_models: list[str]
    safety_note: str
    planning_modes: list[str]


@dataclass(frozen=True)
class AgentPlanStep:
    order: int
    title: str
    description: str
    requires_user_confirmation: bool
    allowed_execution: str
    verification: str


@dataclass(frozen=True)
class AgentPlanningPreview:
    goal: str
    selected_provider: str | None
    selected_model: str | None
    readiness: str
    agent_mode: str
    steps: list[AgentPlanStep]
    unsupported_actions: list[str]
    guardrails: list[str]
    safety_note: str


PLANNING_CAPABILITY_NAMES = {
    "agent_planning",
    "multi_step_planning",
    "workspace_ask",
    "code_analysis",
    "devops_analysis",
}
TOOL_CAPABILITY_NAMES = {"tool_calling", "function_calling", "tools"}
JSON_CAPABILITY_NAMES = {"json_mode", "structured_output", "json_schema"}


def build_agent_capability(model: LocalModelDefinition) -> AgentCapability:
    capabilities = {capability.lower() for capability in model.capabilities}
    name = model.model_name.lower()
    provider = model.provider.lower()
    is_llm = model.model_type == "llm"
    is_fake = provider == "fake" or "fake" in name or "testing" in capabilities

    planning_supported = is_llm and (
        bool(capabilities & PLANNING_CAPABILITY_NAMES)
        or any(token in name for token in ["qwen", "llama", "mistral", "deepseek", "codestral", "hermes"])
    )
    tool_calling_supported = is_llm and bool(capabilities & TOOL_CAPABILITY_NAMES)
    json_mode_supported = is_llm and (
        bool(capabilities & JSON_CAPABILITY_NAMES)
        or any(token in name for token in ["qwen", "llama3", "mistral", "hermes"])
    )

    evidence: list[str] = []
    limitations: list[str] = []
    supported_modes: list[str] = []

    if planning_supported:
        evidence.append("Catalog metadata suggests the model can follow multi-step instructions.")
        supported_modes.append("safe_planning")
    if "coder" in name or "code" in capabilities or "code_analysis" in capabilities:
        evidence.append("Code-oriented model or capability detected.")
        supported_modes.append("code_review_planning")
    if "devops_analysis" in capabilities:
        evidence.append("DevOps analysis capability detected.")
        supported_modes.append("devops_runbook_planning")
    if json_mode_supported:
        evidence.append("Structured-output guidance is likely usable for step plans.")
        supported_modes.append("structured_plan_output")
    if tool_calling_supported:
        evidence.append("Tool/function calling is declared in the model catalog.")
        supported_modes.append("tool_calling_when_backend_supports_it")
    else:
        limitations.append("Tool calling is not declared in the local catalog for this model.")

    if not is_llm:
        readiness = "not_applicable"
        recommended_use = "Embedding models cannot run agent planning."
        planning_supported = False
        json_mode_supported = False
        limitations.append("This is not an LLM model.")
    elif is_fake:
        readiness = "demo_only"
        recommended_use = "Use only for deterministic tests or UI demos."
        limitations.append("Fake providers do not perform real reasoning.")
    elif tool_calling_supported and planning_supported:
        readiness = "agent_ready"
        recommended_use = "Good candidate for safe planning and future tool-calling workflows."
    elif planning_supported:
        readiness = "planning_ready"
        recommended_use = "Use for safe multi-step plans; keep all execution manual and user-confirmed."
    else:
        readiness = "ask_only"
        recommended_use = "Use for normal workspace questions, not agent workflows."
        limitations.append("No planning capability was detected from catalog metadata.")

    guardrails = [
        "Agent mode is planning-only in this app right now.",
        "The frontend never executes shell commands.",
        "Every scan, index, rebuild, restart, or command remains an explicit user action.",
        "Project facts must still come from retrieved sources, not from model assumptions.",
    ]

    return AgentCapability(
        provider=model.provider,
        model=model.model_name,
        display_name=model.display_name,
        model_type=model.model_type,
        readiness=readiness,
        planning_supported=planning_supported,
        tool_calling_supported=tool_calling_supported,
        json_mode_supported=json_mode_supported,
        safe_execution_supported=False,
        supported_agent_modes=sorted(set(supported_modes)),
        recommended_use=recommended_use,
        guardrails=guardrails,
        evidence=evidence,
        limitations=limitations,
    )


def build_agent_capability_catalog(models: list[LocalModelDefinition]) -> AgentCapabilityCatalog:
    capabilities = [build_agent_capability(model) for model in models]
    llm_capabilities = [capability for capability in capabilities if capability.model_type == "llm"]
    recommended = [
        f"{capability.provider}/{capability.model}"
        for capability in llm_capabilities
        if capability.readiness in {"agent_ready", "planning_ready"}
    ]
    return AgentCapabilityCatalog(
        summary=(
            "Agent support is treated as capability awareness plus safe planning. "
            "This workspace does not auto-execute model plans."
        ),
        models=capabilities,
        recommended_models=recommended,
        safety_note=(
            "Current agent mode is planning-only. Execution stays manual, copy-only, "
            "and user-confirmed by design."
        ),
        planning_modes=[
            "safe_planning",
            "code_review_planning",
            "devops_runbook_planning",
            "structured_plan_output",
        ],
    )


def build_agent_planning_preview(
    goal: str,
    provider: str | None,
    model: str | None,
    capability: AgentCapability | None,
) -> AgentPlanningPreview:
    readiness = capability.readiness if capability else "unknown_model"
    steps = [
        AgentPlanStep(
            order=1,
            title="Understand the requested goal",
            description="Rewrite the goal into explicit, reviewable work items before touching project state.",
            requires_user_confirmation=False,
            allowed_execution="read_only_planning",
            verification="User can review and edit the plan before any action.",
        ),
        AgentPlanStep(
            order=2,
            title="Collect source-backed context",
            description="Use indexed project context, saved notes, and conversations to ground the plan.",
            requires_user_confirmation=False,
            allowed_execution="retrieval_only",
            verification="Every project claim should reference retrieved sources or be marked as an assumption.",
        ),
        AgentPlanStep(
            order=3,
            title="Propose ordered actions",
            description="Break the goal into safe steps such as inspect, ask, preview, scan, index, or draft documentation.",
            requires_user_confirmation=True,
            allowed_execution="manual_user_clicks_only",
            verification="No shell command, scan, index, rebuild, or restart runs automatically.",
        ),
        AgentPlanStep(
            order=4,
            title="Re-check result before continuing",
            description="After each user-confirmed action, compare the result with the goal and propose the next safe step.",
            requires_user_confirmation=True,
            allowed_execution="review_then_continue",
            verification="The user chooses whether to continue, stop, or adjust the plan.",
        ),
    ]
    unsupported = [
        "Automatic shell execution",
        "Automatic code edits",
        "Automatic git operations",
        "Automatic scan/index/rebuild/restart without an explicit click",
        "Background internet upload or sharing",
    ]
    guardrails = capability.guardrails if capability else [
        "Unknown model capability. Treat it as normal Ask until reviewed.",
        "Keep all execution manual and explicit.",
    ]
    return AgentPlanningPreview(
        goal=goal,
        selected_provider=provider,
        selected_model=model,
        readiness=readiness,
        agent_mode="safe_planning_only",
        steps=steps,
        unsupported_actions=unsupported,
        guardrails=guardrails,
        safety_note=(
            "This is a planning preview only. The app does not execute the plan. "
            "Use explicit UI actions or copied commands after reviewing each step."
        ),
    )
