from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import (
    runtime_health_checkers,
    runtime_health_configuration,
)
from app.api.schemas.runtime_health_schemas import (
    RuntimeHealthResponse,
    RuntimeTroubleshootingIssueResponse,
    RuntimeTroubleshootingResponse,
    RuntimeTroubleshootingStepResponse,
    to_runtime_health_response,
)
from app.api.schemas.runtime_setup_guide_schemas import (
    GetRuntimeSetupGuideRequest,
    RuntimeSetupGuideResponse,
    to_runtime_setup_guide_response,
)
from app.config.settings import get_settings
from app.core.domain.runtime_health import RuntimeComponentHealth
from app.core.use_cases.get_runtime_health import GetRuntimeHealthUseCase
from app.core.use_cases.get_runtime_setup_guide import (
    GetRuntimeSetupGuideInput,
    GetRuntimeSetupGuideUseCase,
    RuntimeSetupGuideValidationError,
)


router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/health", response_model=RuntimeHealthResponse)
def get_runtime_health() -> RuntimeHealthResponse:
    health = GetRuntimeHealthUseCase(
        health_checkers=runtime_health_checkers,
        configuration=runtime_health_configuration,
    ).execute()
    return to_runtime_health_response(health)


@router.get("/troubleshooting", response_model=RuntimeTroubleshootingResponse)
def get_runtime_troubleshooting() -> RuntimeTroubleshootingResponse:
    settings = get_settings()
    health = GetRuntimeHealthUseCase(
        health_checkers=runtime_health_checkers,
        configuration=runtime_health_configuration,
    ).execute()
    issues: list[RuntimeTroubleshootingIssueResponse] = []
    for component in health.components:
        issue = _troubleshooting_issue(component)
        if issue is not None:
            issues.append(issue)

    if settings.llm_provider.lower() == "fake" or settings.embedding_provider.lower() == "fake":
        issues.append(
            RuntimeTroubleshootingIssueResponse(
                id="fake-providers-active",
                title="Fake model provider is active",
                severity="review",
                component="models",
                summary="The backend is running in demo/test model mode.",
                details="Ask can work, but answers are not produced by your local Ollama models until LLM_PROVIDER and EMBEDDING_PROVIDER are set to ollama.",
                steps=[
                    RuntimeTroubleshootingStepResponse(
                        title="Start backend with local Ollama providers",
                        detail="Stop the backend and start it again with explicit local runtime environment variables.",
                        copy_command="export VECTOR_STORE=qdrant EMBEDDING_PROVIDER=ollama OLLAMA_EMBEDDING_MODEL=nomic-embed-text LLM_PROVIDER=ollama OLLAMA_LLM_MODEL=llama3.2",
                    )
                ],
            )
        )

    if settings.vector_store.lower() != "qdrant":
        issues.append(
            RuntimeTroubleshootingIssueResponse(
                id="memory-vector-store-active",
                title="Memory vector store is active",
                severity="review",
                component="qdrant",
                summary="Search context is temporary when VECTOR_STORE is not qdrant.",
                details="Indexing will not persist across backend restarts unless the backend is configured to use Qdrant.",
                steps=[
                    RuntimeTroubleshootingStepResponse(
                        title="Use Qdrant for persistent local search context",
                        detail="Start Qdrant first, then restart the backend with VECTOR_STORE=qdrant.",
                        copy_command="export VECTOR_STORE=qdrant QDRANT_URL=http://localhost:6333",
                    )
                ],
            )
        )

    status_value = "ok"
    if any(issue.severity == "blocked" for issue in issues):
        status_value = "blocked"
    elif issues:
        status_value = "review"

    return RuntimeTroubleshootingResponse(
        status=status_value,
        summary=(
            "Runtime looks ready."
            if status_value == "ok"
            else "Review runtime troubleshooting steps before relying on local AI results."
        ),
        issues=issues,
        quick_checks=[
            RuntimeTroubleshootingStepResponse(
                title="Check backend health",
                detail="Verifies the FastAPI backend is reachable.",
                copy_command="curl http://127.0.0.1:8000/health",
            ),
            RuntimeTroubleshootingStepResponse(
                title="Check runtime health",
                detail="Shows Ollama, Qdrant, and command-runner status from the backend point of view.",
                copy_command="curl http://127.0.0.1:8000/runtime/health",
            ),
            RuntimeTroubleshootingStepResponse(
                title="Check local database safety",
                detail="Shows active DB path and local data protection hints.",
                copy_command="curl http://127.0.0.1:8000/runtime/local-data",
            ),
        ],
        safe_restart_commands=[
            RuntimeTroubleshootingStepResponse(
                title="Start backend safely",
                detail="Run from the backend directory, using the active virtualenv and Python module execution.",
                copy_command="cd ~/Documents/ai_workspace/backend && source .venv/bin/activate && export VECTOR_STORE=qdrant EMBEDDING_PROVIDER=ollama OLLAMA_EMBEDDING_MODEL=nomic-embed-text LLM_PROVIDER=ollama OLLAMA_LLM_MODEL=llama3.2 && python -m uvicorn app.main:app --reload",
            ),
            RuntimeTroubleshootingStepResponse(
                title="Start frontend",
                detail="Run from the frontend directory. The frontend only calls backend APIs and never executes shell commands.",
                copy_command="cd ~/Documents/ai_workspace/frontend && npm run dev",
            ),
        ],
        safety_note="Troubleshooting is read-only. The frontend only displays or copies commands; it never executes shell commands, starts services, or changes runtime configuration.",
    )


@router.post("/setup-guide", response_model=RuntimeSetupGuideResponse)
def get_runtime_setup_guide(
    request: GetRuntimeSetupGuideRequest,
) -> RuntimeSetupGuideResponse:
    try:
        guide = GetRuntimeSetupGuideUseCase(
            runtime_health_use_case=GetRuntimeHealthUseCase(
                health_checkers=runtime_health_checkers,
                configuration=runtime_health_configuration,
            )
        ).execute(
            GetRuntimeSetupGuideInput(
                assistant_profile_id=request.assistant_profile_id,
                laptop_profile_id=request.laptop_profile_id,
                privacy_mode=request.privacy_mode,
                container_runtime=request.container_runtime,
            )
        )
    except RuntimeSetupGuideValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_runtime_setup_guide_response(guide)


def _troubleshooting_issue(
    component: RuntimeComponentHealth,
) -> RuntimeTroubleshootingIssueResponse | None:
    if component.healthy:
        return None

    severity = "blocked" if component.configured else "review"
    if component.name == "ollama":
        return RuntimeTroubleshootingIssueResponse(
            id=f"ollama-{component.status}",
            title="Ollama needs attention",
            severity=severity,
            component="ollama",
            summary=component.details or "Ollama is not healthy.",
            details="Ollama must be reachable and the configured LLM/embedding models must be installed before local AI answers work reliably.",
            steps=[
                RuntimeTroubleshootingStepResponse(
                    title="Check Ollama service",
                    detail="Verify Ollama responds on the configured base URL.",
                    copy_command="curl http://localhost:11434/api/tags",
                ),
                RuntimeTroubleshootingStepResponse(
                    title="Pull required models",
                    detail="Install the default local LLM and embedding models if they are missing.",
                    copy_command="ollama pull llama3.2 && ollama pull nomic-embed-text",
                ),
            ],
        )

    if component.name == "qdrant":
        return RuntimeTroubleshootingIssueResponse(
            id=f"qdrant-{component.status}",
            title="Qdrant needs attention",
            severity=severity,
            component="qdrant",
            summary=component.details or "Qdrant is not healthy.",
            details="Qdrant is required for persistent local search context when VECTOR_STORE=qdrant.",
            steps=[
                RuntimeTroubleshootingStepResponse(
                    title="Check Qdrant",
                    detail="Verify Qdrant is reachable at the configured URL.",
                    copy_command="curl http://localhost:6333/collections",
                ),
                RuntimeTroubleshootingStepResponse(
                    title="Start Qdrant with Docker",
                    detail="Use this only if Docker is your chosen local runtime.",
                    copy_command="docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant",
                ),
            ],
        )

    if component.name == "command_runner":
        return RuntimeTroubleshootingIssueResponse(
            id=f"command-runner-{component.status}",
            title="Command runner needs attention",
            severity="review",
            component="command_runner",
            summary=component.details or "Command runner is not healthy.",
            details="Command execution remains explicit and policy-gated. Most app features work with the fake command runner.",
            steps=[
                RuntimeTroubleshootingStepResponse(
                    title="Use fake command runner for safe local mode",
                    detail="Recommended while developing the product UI and RAG/reporting features.",
                    copy_command="export COMMAND_RUNNER=fake",
                )
            ],
        )

    return RuntimeTroubleshootingIssueResponse(
        id=f"{component.name}-{component.status}",
        title=f"{component.name} needs attention",
        severity=severity,
        component=component.name,
        summary=component.details or f"{component.name} is not healthy.",
        details="Review runtime health details and restart the backend only after checking local data backups.",
        steps=[],
    )
