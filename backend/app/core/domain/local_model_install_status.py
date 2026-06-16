from dataclasses import dataclass
from typing import Any

from app.core.domain.model_catalog import LocalModelDefinition


@dataclass(frozen=True)
class LocalInstalledModel:
    name: str
    display_name: str | None
    size_bytes: int | None
    modified_at: str | None
    parameter_size: str | None
    quantization_level: str | None
    context_length: int | None
    embedding_length: int | None
    capabilities: list[str]


@dataclass(frozen=True)
class LocalModelStatusItem:
    provider: str
    model: str
    model_type: str
    display_name: str
    recommended: bool
    status: str
    detail: str
    installed_as: str | None
    size_bytes: int | None
    modified_at: str | None
    parameter_size: str | None
    quantization_level: str | None
    context_length: int | None
    embedding_length: int | None
    capabilities: list[str]
    install_command: str


@dataclass(frozen=True)
class LocalModelInstallStatus:
    title: str
    summary: str
    status: str
    provider: str
    runtime_reachable: bool
    runtime_url: str
    installed_count: int
    items: list[LocalModelStatusItem]
    safety_notes: list[str]


def build_local_model_install_status(
    catalog_models: list[LocalModelDefinition],
    installed_models: list[LocalInstalledModel],
    runtime_reachable: bool,
    runtime_url: str,
    error: str | None = None,
) -> LocalModelInstallStatus:
    # The lighter model is the first-run default (fast download, runs on more
    # Macs). Heavier/sharper models like qwen2.5-coder stay available as an
    # upgrade in the Models catalog. Only index 0 is flagged "recommended".
    preferred = [
        ("llm", "llama3.2"),
        ("llm", "qwen2.5-coder"),
        ("embedding", "nomic-embed-text"),
    ]
    catalog_by_key = {
        (model.model_type, model.model_name): model
        for model in catalog_models
        if model.provider == "ollama"
    }

    install_targets = [catalog_by_key[key] for key in preferred if key in catalog_by_key]
    if not install_targets:
        install_targets = [model for model in catalog_models if model.provider == "ollama"][:3]

    installed_by_name = {model.name: model for model in installed_models}
    known_target_keys = {
        (model.provider, model.model_name, model.model_type) for model in install_targets
    }
    install_targets.extend(
        model
        for model in catalog_models
        if model.provider == "ollama"
        and _find_installed(model.model_name, installed_by_name) is not None
        and (model.provider, model.model_name, model.model_type) not in known_target_keys
    )
    items = [
        _build_item(
            model, installed_by_name, recommended=index == 0 or model.model_type == "embedding"
        )
        for index, model in enumerate(install_targets)
    ]

    if not runtime_reachable:
        status = "runtime_unreachable"
        summary = (
            error
            or f"Ollama is not reachable at {runtime_url}. Start Ollama to see installed models."
        )
        items = [
            LocalModelStatusItem(
                provider=item.provider,
                model=item.model,
                model_type=item.model_type,
                display_name=item.display_name,
                recommended=item.recommended,
                status="unknown",
                detail="Cannot verify until Ollama is reachable.",
                installed_as=None,
                size_bytes=None,
                modified_at=None,
                parameter_size=None,
                quantization_level=None,
                context_length=None,
                embedding_length=None,
                capabilities=list(item.capabilities),
                install_command=item.install_command,
            )
            for item in items
        ]
    elif all(item.status == "installed" for item in items):
        status = "ready"
        summary = "Recommended local models are installed and ready for workspace setup."
    elif any(item.status == "installed" for item in items):
        status = "partially_ready"
        summary = "Some recommended local models are installed. Missing models can be pulled manually or through the future approved worker."
    else:
        status = "missing_models"
        summary = "Ollama is reachable, but the recommended local models are not installed yet."

    return LocalModelInstallStatus(
        title="Installed local models",
        summary=summary,
        status=status,
        provider="ollama",
        runtime_reachable=runtime_reachable,
        runtime_url=runtime_url,
        installed_count=len(installed_models) if runtime_reachable else 0,
        items=items,
        safety_notes=[
            "This check is read-only and only reads the Ollama model list.",
            "It never downloads, deletes, starts, rebuilds, or executes MCP tools.",
            "Embedding changes still require an explicit index rebuild later.",
        ],
    )


def parse_ollama_installed_models(payload: dict[str, Any]) -> list[LocalInstalledModel]:
    raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        raise ValueError("Ollama response did not include a models list")

    parsed: list[LocalInstalledModel] = []
    for raw_model in raw_models:
        if not isinstance(raw_model, dict):
            continue
        name = raw_model.get("name") or raw_model.get("model")
        if not isinstance(name, str) or not name.strip():
            continue
        size = raw_model.get("size")
        details = raw_model.get("details") if isinstance(raw_model.get("details"), dict) else {}
        capabilities = raw_model.get("capabilities")
        parsed.append(
            LocalInstalledModel(
                name=name.strip(),
                display_name=raw_model.get("model")
                if isinstance(raw_model.get("model"), str)
                else None,
                size_bytes=size if isinstance(size, int) else None,
                modified_at=(
                    raw_model.get("modified_at")
                    if isinstance(raw_model.get("modified_at"), str)
                    else None
                ),
                parameter_size=(
                    details.get("parameter_size")
                    if isinstance(details.get("parameter_size"), str)
                    else None
                ),
                quantization_level=(
                    details.get("quantization_level")
                    if isinstance(details.get("quantization_level"), str)
                    else None
                ),
                context_length=(
                    details.get("context_length")
                    if isinstance(details.get("context_length"), int)
                    else None
                ),
                embedding_length=(
                    details.get("embedding_length")
                    if isinstance(details.get("embedding_length"), int)
                    else None
                ),
                capabilities=[
                    capability for capability in capabilities if isinstance(capability, str)
                ]
                if isinstance(capabilities, list)
                else [],
            )
        )
    return parsed


def _build_item(
    catalog_model: LocalModelDefinition,
    installed_by_name: dict[str, LocalInstalledModel],
    recommended: bool,
) -> LocalModelStatusItem:
    installed = _find_installed(catalog_model.model_name, installed_by_name)
    if installed:
        status = "installed"
        detail = "Available locally in Ollama."
    else:
        status = "missing"
        detail = "Not found in the local Ollama model list."

    return LocalModelStatusItem(
        provider=catalog_model.provider,
        model=catalog_model.model_name,
        model_type=catalog_model.model_type,
        display_name=catalog_model.display_name,
        recommended=recommended,
        status=status,
        detail=detail,
        installed_as=installed.name if installed else None,
        size_bytes=installed.size_bytes if installed else None,
        modified_at=installed.modified_at if installed else None,
        parameter_size=installed.parameter_size if installed else None,
        quantization_level=installed.quantization_level if installed else None,
        context_length=installed.context_length if installed else None,
        embedding_length=installed.embedding_length if installed else None,
        capabilities=list(installed.capabilities if installed else catalog_model.capabilities),
        install_command=f"ollama pull {catalog_model.model_name}",
    )


def _find_installed(
    required_model: str,
    installed_by_name: dict[str, LocalInstalledModel],
) -> LocalInstalledModel | None:
    candidates = {
        required_model,
        f"{required_model}:latest",
        required_model.removesuffix(":latest"),
    }
    for name, installed in installed_by_name.items():
        if name in candidates or name.removesuffix(":latest") in candidates:
            return installed
    return None
