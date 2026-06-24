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
    RelationType,
)
from app.core.domain.risk_explanation import explain_finding
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
            # Calm, review-oriented framing (why it may matter, what to check
            # manually, plain-language confidence) — derived deterministically.
            "explained": explain_finding(f).as_dict(),
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


def _ci_branch_fires(branches: list[str], ignore: list[str], samples: list[str]) -> bool:
    """Would a push to any of ``samples`` trigger, given branch filters?"""
    import fnmatch

    def matches(patterns: list[str], name: str) -> bool:
        return any(fnmatch.fnmatch(name, p) for p in patterns)

    for name in samples:
        included = (not branches) or matches(branches, name)
        ignored = matches(ignore, name) if ignore else False
        if included and not ignored:
            return True
    return False


_CI_DEFAULT_BRANCHES = ["main", "master"]
_CI_FEATURE_SAMPLES = ["feature/example", "topic-branch", "fix/bug-123"]


def present_ci(graph: ProjectGraph) -> dict:
    """Plain-language "what runs when" derived from GitHub Actions triggers stored
    on the pipeline entities. Deterministic; honest that job-level ``rules`` may
    further gate execution."""
    import json

    pipelines = [
        e for e in graph.entities_of_type(EntityType.PIPELINE) if e.metadata.get("triggers_json")
    ]
    if not pipelines:
        return {"has_data": False, "scenarios": []}

    # pipeline id -> [job names]
    jobs_by_pipeline: dict[str, list[str]] = {}
    job_names = {j.id: j.name for j in graph.entities_of_type(EntityType.PIPELINE_JOB)}
    for r in graph.relations_of_type(RelationType.INCLUDES):
        if r.target_entity_id in job_names:
            jobs_by_pipeline.setdefault(r.source_entity_id, []).append(
                job_names[r.target_entity_id]
            )

    scenarios = {
        "push_feature": {
            "key": "push_feature",
            "label": "Push to a feature branch",
            "workflows": [],
        },
        "push_default": {
            "key": "push_default",
            "label": "Push or merge to the default branch",
            "workflows": [],
        },
        "pull_request": {
            "key": "pull_request",
            "label": "Open or update a pull request",
            "workflows": [],
        },
        "tag": {"key": "tag", "label": "Push a tag or publish a release", "workflows": []},
        "schedule": {"key": "schedule", "label": "On a schedule", "workflows": []},
        "manual": {"key": "manual", "label": "Run manually", "workflows": []},
    }

    for pipeline in pipelines:
        try:
            rules = json.loads(pipeline.metadata.get("triggers_json", "[]"))
        except (ValueError, TypeError):
            rules = []
        hits: set[str] = set()
        cron_notes: list[str] = []
        for rule in rules:
            event = rule.get("event", "")
            branches = rule.get("branches") or []
            ignore = rule.get("branches_ignore") or []
            tags = rule.get("tags") or []
            cron = rule.get("cron") or []
            if event == "push":
                if tags and not branches:
                    hits.add("tag")
                else:
                    if _ci_branch_fires(branches, ignore, _CI_FEATURE_SAMPLES):
                        hits.add("push_feature")
                    if _ci_branch_fires(branches, ignore, _CI_DEFAULT_BRANCHES):
                        hits.add("push_default")
                    if tags:
                        hits.add("tag")
            elif event in ("pull_request", "pull_request_target"):
                hits.add("pull_request")
            elif event == "release":
                hits.add("tag")
            elif event == "schedule":
                hits.add("schedule")
                cron_notes.extend(cron)
            elif event == "workflow_dispatch":
                hits.add("manual")
        entry = {
            "name": pipeline.name,
            "jobs": sorted(jobs_by_pipeline.get(pipeline.id, [])),
            "source_file": pipeline.source_file,
        }
        if cron_notes:
            entry["cron"] = cron_notes
        for key in hits:
            scenarios[key]["workflows"].append(dict(entry))

    ordered = [s for s in scenarios.values() if s["workflows"]]
    return {"has_data": bool(ordered), "scenarios": ordered}


def present_cloud(graph: ProjectGraph) -> dict:
    """Group the provisioned cloud services by provider for the Cloud tab."""
    services = graph.entities_of_type(EntityType.CLOUD_SERVICE)
    by_provider: dict[str, list[dict]] = {}
    for entity in services:
        provider = entity.metadata.get("provider", "Cloud")
        by_provider.setdefault(provider, []).append(
            {
                "service": entity.metadata.get("service", entity.name),
                "resources": int(entity.metadata.get("resources", "0") or "0"),
                "source_file": entity.source_file,
            }
        )
    providers = [
        {
            "provider": provider,
            "services": sorted(items, key=lambda s: (-s["resources"], s["service"])),
            "service_count": len(items),
        }
        for provider, items in sorted(by_provider.items())
    ]
    return {"providers": providers, "total_services": len(services)}


def present_references(graph: ProjectGraph) -> dict:
    """Group external references (URLs / ARNs / module sources) by kind."""
    refs = graph.entities_of_type(EntityType.REFERENCE)
    by_kind: dict[str, list[dict]] = {}
    for entity in refs:
        kind = entity.metadata.get("kind", "other")
        by_kind.setdefault(kind, []).append(
            {
                "value": entity.name,
                "count": int(entity.metadata.get("count", "1") or "1"),
                "source_file": entity.source_file,
            }
        )
    groups = [
        {
            "kind": kind,
            "items": sorted(items, key=lambda r: (-r["count"], r["value"])),
        }
        for kind, items in sorted(by_kind.items())
    ]
    return {"groups": groups, "total": len(refs)}


def present_project_intelligence(graph: ProjectGraph, lens: RoleLens) -> dict:
    services = graph.entities_of_type(EntityType.SERVICE)
    environments = graph.entities_of_type(EntityType.ENVIRONMENT)
    pipelines = graph.entities_of_type(EntityType.PIPELINE)
    pipeline_jobs = graph.entities_of_type(EntityType.PIPELINE_JOB)
    infra = graph.entities_of_type(EntityType.INFRA_COMPONENT)
    images = graph.entities_of_type(EntityType.CONTAINER_IMAGE)
    config_files = graph.entities_of_type(EntityType.CONFIG_FILE)
    applications = graph.entities_of_type(EntityType.APPLICATION)
    modules = graph.entities_of_type(EntityType.MODULE)
    dependencies = graph.entities_of_type(EntityType.DEPENDENCY)

    frameworks: set[str] = set()
    for app in applications:
        raw = app.metadata.get("frameworks", "")
        frameworks |= {f.strip() for f in raw.split(",") if f.strip()}

    technology_chips = sorted(
        {e.name for e in infra}
        | {p.name for p in pipelines}
        | {d.name for d in dependencies}
        | frameworks
    )

    # A purely factual one-line description; the LLM (separately) elaborates.
    parts: list[str] = []
    if applications:
        app_part = "Python application"
        if frameworks:
            app_part += " (" + ", ".join(sorted(frameworks)) + ")"
        if modules:
            app_part += f", {len(modules)} module(s)"
        parts.append(app_part)
    if infra:
        parts.append("infrastructure: " + ", ".join(sorted(e.name for e in infra)))
    if pipelines:
        parts.append(f"{len(pipelines)} CI/CD pipeline(s)")
    if environments:
        parts.append(
            f"{len(environments)} environment(s): "
            + ", ".join(sorted(e.name for e in environments))
        )
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
