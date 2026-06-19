"""Deterministic projection of a ``ProjectGraph`` through a ``RoleLens``.

Turns the role-neutral graph into the sections the UI shows (summary,
infrastructure, deployment, environments, risks, important files, questions),
ordered/prioritised for the role. No LLM here — every value comes straight from
the graph facts. The LLM (separately) only writes prose over these same facts.
"""

from app.core.domain.project_graph import (
    EntityType,
    ProjectFinding,
    ProjectGraph,
)
from app.core.domain.role_lens import RoleLens, Section

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


def _ordered_findings(findings: list[ProjectFinding], lens: RoleLens) -> list[dict]:
    highlighted = {c: i for i, c in enumerate(lens.highlighted_finding_categories)}

    def sort_key(finding: ProjectFinding) -> tuple[int, int]:
        category_rank = highlighted.get(finding.category, len(highlighted) + 1)
        severity_rank = _SEVERITY_ORDER.get(finding.severity, 99)
        return (category_rank, severity_rank)

    return [
        {
            "id": f.id,
            "category": f.category,
            "severity": f.severity,
            "title": f.title,
            "explanation": f.explanation,
            "source_file": f.source_file,
            "evidence": list(f.evidence),
            "confidence": f.confidence,
            "recommendation": f.recommendation,
            "analyzer": f.analyzer,
        }
        for f in sorted(findings, key=sort_key)
    ]


def _entity_dict(entity) -> dict:
    return {
        "id": entity.id,
        "type": entity.type,
        "name": entity.name,
        "status": entity.status,
        "confidence": entity.confidence,
        "source_file": entity.source_file,
        "analyzer": entity.analyzer,
        "metadata": dict(entity.metadata),
    }


def _team_questions(graph: ProjectGraph) -> list[dict]:
    """Honest gap-based questions (not asserted defects). Each says why it's asked."""
    questions: list[dict] = []
    envs = {e.name for e in graph.entities_of_type(EntityType.ENVIRONMENT)}
    infra = {e.name for e in graph.entities_of_type(EntityType.INFRA_COMPONENT)}
    pipelines = graph.entities_of_type(EntityType.PIPELINE)
    finding_text = " ".join(f"{f.title} {f.explanation}".lower() for f in graph.findings)

    if {"prod", "production"} & envs and "rollback" not in finding_text:
        questions.append(
            {
                "question": "A production environment was found, but no rollback process was detected. How are bad deploys rolled back?",
                "reason": "production environment detected; no rollback evidence",
            }
        )
    if "Terraform" in infra or "Terragrunt" in infra:
        questions.append(
            {
                "question": "Infrastructure-as-code was found. Where is Terraform state stored, and is it locked?",
                "reason": "Terraform/Terragrunt detected; state backend/locking not confirmed",
            }
        )
    if pipelines and "approval" not in finding_text:
        questions.append(
            {
                "question": "CI/CD pipelines were found. Is the production deploy gated by an approval step?",
                "reason": "pipelines detected; an approval gate was not detected",
            }
        )
    if not envs:
        questions.append(
            {
                "question": "No environments were detected from the directory structure. How are dev / staging / prod separated?",
                "reason": "no environment naming convention found",
            }
        )
    return questions


def present_project_graph(graph: ProjectGraph) -> dict:
    """Role-neutral node/edge projection for the interactive map. The graph facts
    are the same regardless of role; only the lens-based sections re-order them."""
    return {
        "nodes": [
            {
                "id": e.id,
                "type": e.type,
                "name": e.name,
                "status": e.status,
                "confidence": e.confidence,
                "analyzer": e.analyzer,
                "source_file": e.source_file,
            }
            for e in graph.entities
        ],
        "edges": [
            {
                "id": r.id,
                "source": r.source_entity_id,
                "target": r.target_entity_id,
                "type": r.relation_type,
            }
            for r in graph.relations
        ],
    }


def present_project_intelligence(graph: ProjectGraph, lens: RoleLens) -> dict:
    services = graph.entities_of_type(EntityType.SERVICE)
    environments = graph.entities_of_type(EntityType.ENVIRONMENT)
    pipelines = graph.entities_of_type(EntityType.PIPELINE)
    pipeline_jobs = graph.entities_of_type(EntityType.PIPELINE_JOB)
    infra = graph.entities_of_type(EntityType.INFRA_COMPONENT)
    images = graph.entities_of_type(EntityType.CONTAINER_IMAGE)
    config_files = graph.entities_of_type(EntityType.CONFIG_FILE)

    technology_chips = sorted({e.name for e in infra} | {p.name for p in pipelines})

    # A purely factual one-line description; the LLM (separately) elaborates.
    parts: list[str] = []
    if infra:
        parts.append("infrastructure: " + ", ".join(sorted(e.name for e in infra)))
    if pipelines:
        parts.append(f"{len(pipelines)} CI/CD pipeline(s)")
    if environments:
        parts.append(f"{len(environments)} environment(s): " + ", ".join(sorted(e.name for e in environments)))
    description = (
        "Detected " + "; ".join(parts) + "." if parts else "No supported technologies detected yet."
    )

    return {
        "role": lens.role,
        "role_label": lens.label,
        "section_order": list(lens.section_order),
        "analyzers_run": list(graph.analyzers_run),
        "analyzers_skipped": list(graph.analyzers_skipped),
        Section.SUMMARY: {
            "description": description,
            "technology_chips": technology_chips,
            "counts": {
                "services": len(services),
                "environments": len(environments),
                "pipelines": len(pipelines),
                "infrastructure": len(infra),
            },
        },
        Section.INFRASTRUCTURE: {
            "components": [_entity_dict(e) for e in infra],
            "images": [_entity_dict(e) for e in images],
        },
        Section.DEPLOYMENT: {
            "pipelines": [
                {
                    **_entity_dict(p),
                    "jobs": [
                        _entity_dict(j)
                        for j in pipeline_jobs
                        if any(
                            r.source_entity_id == p.id and r.target_entity_id == j.id
                            for r in graph.relations
                        )
                    ],
                }
                for p in pipelines
            ],
        },
        Section.ENVIRONMENTS: {
            "environments": [_entity_dict(e) for e in environments],
        },
        Section.RISKS: {
            "findings": _ordered_findings(graph.findings, lens),
            "highlighted_categories": list(lens.highlighted_finding_categories),
        },
        Section.IMPORTANT_FILES: {
            "files": [
                {"path": e.name, "reason": e.metadata.get("reason", "")} for e in config_files
            ],
        },
        Section.QUESTIONS: {
            "questions": _team_questions(graph),
        },
    }
