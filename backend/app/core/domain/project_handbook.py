"""Deterministic project handbook — a compact, human-readable summary of the
project assembled from the evidence graph. It doubles as durable LLM context
(a distilled "what this project is") and as something the user can read.

No LLM: every line comes straight from graph facts, so the handbook never invents.
"""

from app.core.domain.project_graph import EntityType, ProjectGraph

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


def build_handbook(graph: ProjectGraph) -> str:
    infra = sorted({e.name for e in graph.entities_of_type(EntityType.INFRA_COMPONENT)})
    pipelines = sorted({e.name for e in graph.entities_of_type(EntityType.PIPELINE)})
    environments = sorted({e.name for e in graph.entities_of_type(EntityType.ENVIRONMENT)})
    services = sorted({e.name for e in graph.entities_of_type(EntityType.SERVICE)})
    applications = graph.entities_of_type(EntityType.APPLICATION)
    cloud = sorted({e.name for e in graph.entities_of_type(EntityType.CLOUD_SERVICE)})
    modules = sorted({e.name for e in graph.entities_of_type(EntityType.MODULE)})
    config_files = graph.entities_of_type(EntityType.CONFIG_FILE)

    frameworks: set[str] = set()
    for app in applications:
        raw = app.metadata.get("frameworks", "")
        frameworks |= {f.strip() for f in raw.split(",") if f.strip()}

    lines: list[str] = ["# Project handbook", ""]

    # One-line nature of the project.
    parts: list[str] = []
    if applications:
        app_part = "a Python application"
        if frameworks:
            app_part += " (" + ", ".join(sorted(frameworks)) + ")"
        parts.append(app_part)
    if infra:
        parts.append("infrastructure-as-code with " + ", ".join(infra))
    if pipelines:
        parts.append(f"{len(pipelines)} CI/CD pipeline(s)")
    overview = (
        "This project is " + "; ".join(parts) + "."
        if parts
        else "No supported technologies were detected in this project yet."
    )
    lines += ["## Overview", overview, ""]

    if environments:
        lines += [
            "## Environments",
            "Inferred from naming (confirm with the team): " + ", ".join(environments),
            "",
        ]
    if infra or cloud:
        lines.append("## Infrastructure & cloud")
        if infra:
            lines.append("Tools: " + ", ".join(infra) + ".")
        if cloud:
            lines.append("Cloud services: " + ", ".join(cloud) + ".")
        lines.append("")
    if services or modules:
        lines.append("## Components")
        if services:
            lines.append("Services: " + ", ".join(services[:20]) + ".")
        if modules:
            lines.append("Modules: " + ", ".join(modules[:20]) + ".")
        lines.append("")
    if pipelines:
        lines += ["## CI/CD", "Pipelines: " + ", ".join(pipelines) + ".", ""]

    if config_files:
        files = [e.name for e in config_files][:8]
        lines += ["## Where to start reading", ", ".join(files), ""]

    if graph.findings:
        top = sorted(graph.findings, key=lambda f: _SEVERITY_ORDER.get(f.severity, 9))[:5]
        lines.append(f"## Risks ({len(graph.findings)} flagged)")
        for f in top:
            lines.append(f"- [{f.severity}] {f.title}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
