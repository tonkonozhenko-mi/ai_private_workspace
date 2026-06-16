from app.core.domain.assistant_profile import AssistantProfile


class AssistantProfileRegistry:
    def __init__(self, profiles: list[AssistantProfile] | None = None) -> None:
        self.profiles = profiles or DEFAULT_ASSISTANT_PROFILES

    def list_profiles(self) -> list[AssistantProfile]:
        return list(self.profiles)

    def get_profile(self, profile_id: str) -> AssistantProfile:
        return next(
            (profile for profile in self.profiles if profile.id == profile_id),
            self._default_profile(),
        )

    def _default_profile(self) -> AssistantProfile:
        return next(profile for profile in self.profiles if profile.id == "developer")


DEFAULT_ASSISTANT_PROFILES = [
    AssistantProfile(
        id="devops",
        name="DevOps Assistant",
        description="Analyze infrastructure, delivery pipelines, and operational workflows.",
        target_users=["DevOps engineers", "Platform engineers", "SREs"],
        primary_capabilities=[
            "project_scan",
            "deterministic_analysis",
            "terraform_analysis",
            "terragrunt_analysis",
            "cicd_analysis",
            "command_suggestions",
            "command_approval",
            "workspace_ask",
        ],
        recommended_actions=[
            "scan_project",
            "analyze_terraform",
            "analyze_terragrunt",
            "analyze_cicd",
            "index_workspace",
            "ask_workspace_question",
        ],
        recommended_runtime={
            "VECTOR_STORE": "qdrant",
            "EMBEDDING_PROVIDER": "ollama",
            "LLM_PROVIDER": "ollama",
        },
    ),
    AssistantProfile(
        id="developer",
        name="Developer Assistant",
        description="Explore application code and answer project development questions.",
        target_users=["Software developers", "Maintainers"],
        primary_capabilities=[
            "project_scan",
            "code_context_search",
            "workspace_ask",
            "command_suggestions",
        ],
        recommended_actions=[
            "scan_project",
            "index_workspace",
            "ask_workspace_question",
            "analyze_python",
        ],
        recommended_runtime={
            "VECTOR_STORE": "qdrant",
            "EMBEDDING_PROVIDER": "ollama",
            "LLM_PROVIDER": "ollama",
        },
    ),
    AssistantProfile(
        id="documentation",
        name="Documentation Assistant",
        description="Generate project overviews and review documentation context.",
        target_users=["Technical writers", "Maintainers", "Developers"],
        primary_capabilities=[
            "project_overview_report",
            "workspace_ask",
            "documentation_review",
        ],
        recommended_actions=[
            "generate_project_overview",
            "index_workspace",
            "ask_workspace_question",
        ],
        recommended_runtime={
            "VECTOR_STORE": "qdrant",
            "EMBEDDING_PROVIDER": "ollama",
            "LLM_PROVIDER": "ollama",
        },
    ),
    AssistantProfile(
        id="support_incident",
        name="Support Incident Assistant",
        description="Review recent workspace activity and approved diagnostic actions.",
        target_users=["Support engineers", "Incident responders", "SREs"],
        primary_capabilities=[
            "timeline",
            "command_approval",
            "command_suggestions",
            "workspace_ask",
        ],
        recommended_actions=[
            "review_timeline",
            "inspect_recent_commands",
            "ask_workspace_question",
        ],
        recommended_runtime={
            "VECTOR_STORE": "qdrant",
            "EMBEDDING_PROVIDER": "ollama",
            "LLM_PROVIDER": "ollama",
        },
    ),
    AssistantProfile(
        id="manager_summary",
        name="Manager Summary Assistant",
        description="Summarize project readiness, analysis findings, and recent activity.",
        target_users=["Engineering managers", "Technical leads", "Project managers"],
        primary_capabilities=[
            "project_overview_report",
            "analysis_summary",
            "readiness",
            "timeline",
        ],
        recommended_actions=[
            "generate_project_overview",
            "review_analysis_summary",
            "review_readiness",
        ],
        recommended_runtime={
            "VECTOR_STORE": "memory",
            "EMBEDDING_PROVIDER": "fake",
            "LLM_PROVIDER": "fake",
        },
    ),
    AssistantProfile(
        id="tester",
        name="Tester / QA Assistant",
        description="Review test coverage, how to run tests, and what to verify.",
        target_users=["QA engineers", "Testers", "SDETs"],
        primary_capabilities=[
            "project_scan",
            "code_context_search",
            "workspace_ask",
            "command_suggestions",
        ],
        recommended_actions=[
            "scan_project",
            "index_workspace",
            "ask_workspace_question",
        ],
        recommended_runtime={
            "VECTOR_STORE": "qdrant",
            "EMBEDDING_PROVIDER": "ollama",
            "LLM_PROVIDER": "ollama",
        },
    ),
    AssistantProfile(
        id="business_analyst",
        name="Business Analyst Assistant",
        description="Explain in plain language what the project does, its features, and stakeholders.",
        target_users=["Business analysts", "Product managers", "Stakeholders"],
        primary_capabilities=[
            "project_overview_report",
            "analysis_summary",
            "workspace_ask",
        ],
        recommended_actions=[
            "generate_project_overview",
            "index_workspace",
            "ask_workspace_question",
        ],
        recommended_runtime={
            "VECTOR_STORE": "qdrant",
            "EMBEDDING_PROVIDER": "ollama",
            "LLM_PROVIDER": "ollama",
        },
    ),
]
