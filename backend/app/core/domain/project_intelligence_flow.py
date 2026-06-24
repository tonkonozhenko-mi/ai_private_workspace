"""Deterministic M3 derivations over the role-neutral graph.

Two read-only projections, both pure functions of the graph (no LLM):

* ``derive_deployment_flow`` — how code appears to reach an environment, as an
  ordered set of stages (Source & CI → Build artifacts → Deploy → Environments)
  plus honest *gaps* where the chain is broken or unconfirmed.
* ``compare_environments`` — a side-by-side of the inferred environments and the
  evidence behind each, so a reader can see coverage at a glance.

Everything here is evidence-backed: a stage or gap only appears because of
entities/relations the analyzers actually produced.
"""

from app.core.domain.project_graph import (
    EntityType,
    ProjectGraph,
    RelationType,
)


def _image_built_in_ci(graph: ProjectGraph) -> set[str]:
    """Image entity ids that a CI job RUNS (i.e. are produced/used in CI)."""
    job_ids = {e.id for e in graph.entities_of_type(EntityType.PIPELINE_JOB)}
    return {
        r.target_entity_id
        for r in graph.relations_of_type(RelationType.RUNS)
        if r.source_entity_id in job_ids
    }


def _image_deployed(graph: ProjectGraph) -> set[str]:
    """Image entity ids that a service RUNS (i.e. are deployed at runtime)."""
    service_ids = {e.id for e in graph.entities_of_type(EntityType.SERVICE)}
    return {
        r.target_entity_id
        for r in graph.relations_of_type(RelationType.RUNS)
        if r.source_entity_id in service_ids
    }


def derive_deployment_flow(graph: ProjectGraph) -> dict:
    pipelines = graph.entities_of_type(EntityType.PIPELINE)
    jobs = graph.entities_of_type(EntityType.PIPELINE_JOB)
    images = graph.entities_of_type(EntityType.CONTAINER_IMAGE)
    services = graph.entities_of_type(EntityType.SERVICE)
    environments = graph.entities_of_type(EntityType.ENVIRONMENT)
    platforms = graph.entities_of_type(EntityType.INFRA_COMPONENT)

    built = _image_built_in_ci(graph)
    deployed = _image_deployed(graph)

    stages = [
        {
            "key": "source_ci",
            "label": "Source & CI",
            "count": len(pipelines),
            "detail": (
                f"{len(pipelines)} pipeline(s), {len(jobs)} job(s)"
                if pipelines
                else "No CI/CD pipeline detected"
            ),
        },
        {
            "key": "build",
            "label": "Build artifacts",
            "count": len(images),
            "detail": (
                f"{len(images)} container image(s)" if images else "No container images detected"
            ),
        },
        {
            "key": "deploy",
            "label": "Deploy",
            "count": len(services),
            "detail": (
                f"{len(services)} service(s) via {', '.join(sorted(p.name for p in platforms)) or 'no platform'}"
                if services
                else "No deployable services detected"
            ),
        },
        {
            "key": "environments",
            "label": "Environments",
            "count": len(environments),
            "detail": (
                ", ".join(sorted(e.name for e in environments))
                if environments
                else "No environments inferred"
            ),
        },
    ]

    gaps: list[dict] = []
    if pipelines and not images:
        gaps.append(
            {
                "title": "CI detected, but no image build found",
                "explanation": "Pipelines were detected but no container image is built or referenced. The artifact a deploy would use is unclear.",
            }
        )
    if services and not pipelines:
        gaps.append(
            {
                "title": "Services deployed without a detected pipeline",
                "explanation": "Deployable services were found but no CI/CD pipeline was detected. How they are built and released is not visible in the files.",
            }
        )
    # Images that runtime services use but no CI job appears to build.
    deployed_not_built = deployed - built
    if deployed_not_built and jobs:
        names = sorted(e.name for e in images if e.id in deployed_not_built)
        gaps.append(
            {
                "title": "Deployed image not built in CI",
                "explanation": (
                    "These images are deployed by a service but no CI job was found that builds them: "
                    + ", ".join(names[:5])
                    + ("…" if len(names) > 5 else "")
                    + ". They may be built elsewhere or pulled from an external registry."
                ),
            }
        )
    if not environments:
        gaps.append(
            {
                "title": "No environments inferred",
                "explanation": "No environment naming was found in paths, namespaces or values files, so promotion (dev → staging → prod) cannot be traced.",
            }
        )

    return {"stages": stages, "gaps": gaps}


def compare_environments(graph: ProjectGraph) -> dict:
    """Side-by-side of the inferred environments and the evidence behind each."""
    environments = sorted(graph.entities_of_type(EntityType.ENVIRONMENT), key=lambda e: e.name)
    rows = [
        {
            "name": e.name,
            "analyzer": e.analyzer,
            "status": e.status,
            "confidence": e.confidence,
            "source_file": e.source_file,
            "evidence_count": int(e.metadata.get("evidence_paths", "0") or "0"),
        }
        for e in environments
    ]
    names = {e.name for e in environments}
    has_prod = bool({"prod", "production"} & names)
    has_nonprod = bool(names - {"prod", "production"})

    if not rows:
        summary = "No environments were inferred from the project's files."
    elif has_prod and has_nonprod:
        summary = f"{len(rows)} environments inferred, including a production environment and at least one pre-production environment."
    elif has_prod:
        summary = "A production environment was inferred, but no separate pre-production environment was found."
    else:
        summary = f"{len(rows)} non-production environment(s) inferred; no production environment was detected by name."

    return {"environments": rows, "summary": summary, "has_production": has_prod}
