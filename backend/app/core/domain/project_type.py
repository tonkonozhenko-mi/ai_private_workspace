"""Deterministic project-type classification for the first-screen summary.

The graph faithfully records *everything* it finds — a lone helper `.py` in a
Terraform repo still creates a "Python application" entity. The old summary led
with that entity unconditionally, so a pure-infra repo was announced as "Detected
Python application". This picks the *dominant* signal instead and leads with it,
so the first thing the user reads matches what the project actually is.

Pure and deterministic (a weighted count over graph entities); no LLM, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.project_graph import EntityType, ProjectGraph

KIND_APPLICATION = "application"
KIND_INFRASTRUCTURE = "infrastructure"
KIND_MIXED = "mixed"
KIND_UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProjectClassification:
    kind: str
    # A short human lead for the summary line, e.g. "FastAPI application" or
    # "infrastructure project (Terraform, CI/CD)".
    label: str
    application_score: int
    infrastructure_score: int


def _languages(graph: ProjectGraph) -> list[str]:
    """Languages named by application entities. The scan supplies this for the
    codebases that have no analyzer yet (TypeScript, Go, Java …), so the summary can
    say what the project is written in instead of defaulting to Python."""
    languages: list[str] = []
    for app in graph.entities_of_type(EntityType.APPLICATION):
        language = app.metadata.get("language", "").strip()
        if language and language not in languages:
            languages.append(language)
    return languages


def _application_signal(graph: ProjectGraph) -> tuple[int, list[str], int]:
    """Return (score, frameworks, module_count) for the app side."""
    applications = graph.entities_of_type(EntityType.APPLICATION)
    modules = graph.entities_of_type(EntityType.MODULE)
    services = graph.entities_of_type(EntityType.SERVICE)
    frameworks: list[str] = []
    for app in applications:
        for fw in app.metadata.get("frameworks", "").split(","):
            fw = fw.strip()
            if fw and fw not in frameworks:
                frameworks.append(fw)
    # A real app announces itself with a framework or several modules; a stray
    # script (modules≈1, no framework) barely registers.
    score = 0
    if frameworks:
        score += 3
    if applications:
        score += 1
    score += min(len(modules), 5)
    score += min(len(services), 3)
    return score, frameworks, len(modules)


# Which analyzer ran → the friendly tool name shown in the infra headline.
_ANALYZER_TOOL = {
    "terraform": "Terraform",
    "terragrunt": "Terragrunt",
    "cloudformation": "CloudFormation",
    "kubernetes": "Kubernetes",
    "helm": "Helm",
    "github_actions": "CI/CD",
    "gitlab_ci": "CI/CD",
}


def _infra_tools(graph: ProjectGraph) -> list[str]:
    """Friendly infra tool names for the headline, from the analyzers that fired —
    cleaner than raw entity names (e.g. 'Terraform', 'CI/CD' not 'aws_s3_bucket')."""
    tools: list[str] = []
    for analyzer in graph.analyzers_run:
        name = _ANALYZER_TOOL.get(analyzer)
        if name and name not in tools:
            tools.append(name)
    return tools


def _infrastructure_signal(graph: ProjectGraph) -> tuple[int, list[str]]:
    """Return (score, friendly tool names) for the infra side."""
    infra = graph.entities_of_type(EntityType.INFRA_COMPONENT)
    pipelines = graph.entities_of_type(EntityType.PIPELINE)
    cloud = graph.entities_of_type(EntityType.CLOUD_SERVICE)
    score = len(infra) + len(pipelines) + min(len(cloud), 3)
    return score, _infra_tools(graph)


def classify_project(graph: ProjectGraph) -> ProjectClassification:
    """Pick the dominant project kind and a lead label. Ties, and any repo with a
    real app *and* real infra, read as 'mixed' (led by whichever scores higher)."""
    app_score, frameworks, _modules = _application_signal(graph)
    infra_score, infra_tools = _infrastructure_signal(graph)

    # Lead with the framework when one is known, then the language the code is
    # actually written in. "Python application" is the last resort, not the default:
    # calling a TypeScript repo a Python one is worse than saying nothing.
    if frameworks:
        app_label = f"{frameworks[0]} application"
    else:
        languages = _languages(graph)
        app_label = f"{languages[0]} application" if languages else "Python application"
    infra_label = "infrastructure project"
    if infra_tools:
        infra_label += " (" + ", ".join(infra_tools[:3]) + ")"

    if app_score == 0 and infra_score == 0:
        return ProjectClassification(KIND_UNKNOWN, "", 0, 0)

    # Infrastructure leads when it outweighs a weak/absent app signal. A genuine
    # app (framework or several modules) that also has infra is "mixed", led by
    # the app — that's what the user came to build.
    if infra_score > app_score:
        kind = KIND_MIXED if app_score >= 3 else KIND_INFRASTRUCTURE
        label = infra_label
    elif app_score > 0:
        kind = KIND_MIXED if infra_score >= 2 else KIND_APPLICATION
        label = app_label
    else:
        kind = KIND_INFRASTRUCTURE
        label = infra_label

    return ProjectClassification(kind, label, app_score, infra_score)
