"""Turn the existing analyzers' structured results into a role-neutral
``ProjectGraph``. Pure, deterministic, no LLM — every element keeps its source,
evidence, confidence and status so the UI can show exactly why it's there.

This composes (does not replace) the existing analyzers in
``app/core/use_cases/analyze_*`` via their domain results in
``app/core/domain/analysis.py``.
"""

import os
import re

from app.core.domain.analysis import (
    AnalysisFinding,
    GitHubActionsAnalysisResult,
    GitLabCIAnalysisResult,
    TerraformAnalysisResult,
    TerragruntAnalysisResult,
)
from app.core.domain.project_graph import (
    Confidence,
    EntityType,
    EvidenceStatus,
    FindingCategory,
    ProjectEntity,
    ProjectFinding,
    ProjectGraph,
    ProjectRelation,
    RelationType,
)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "item"


def _entity_id(entity_type: str, name: str) -> str:
    return f"{entity_type}:{_slug(name)}"


def _relation_id(source_id: str, relation_type: str, target_id: str) -> str:
    return f"{source_id}|{relation_type}|{target_id}"


# Canonical environments keyed by the directory tokens that imply them. Detection
# is INFERRED (a naming convention), never CONFIRMED — we never assert a folder
# is an environment without saying it came from naming.
_ENV_TOKENS: dict[str, str] = {
    "dev": "dev",
    "develop": "dev",
    "development": "dev",
    "stg": "staging",
    "stage": "staging",
    "staging": "staging",
    "uat": "uat",
    "qa": "qa",
    "test": "test",
    "preprod": "preprod",
    "pre-prod": "preprod",
    "prod": "prod",
    "production": "prod",
    "sandbox": "sandbox",
    "sbx": "sandbox",
    "mgmt": "management",
    "mngt": "management",
    "management": "management",
}


def _path_segments(path: str) -> list[str]:
    return [seg for seg in re.split(r"[\\/]+", path) if seg]


def environments_from_paths(paths: list[str], analyzer: str) -> list[ProjectEntity]:
    """Infer environment entities from environment-like directory segments."""
    evidence_by_env: dict[str, list[str]] = {}
    for path in paths:
        for seg in _path_segments(path):
            canonical = _ENV_TOKENS.get(seg.lower())
            if canonical:
                evidence_by_env.setdefault(canonical, [])
                if path not in evidence_by_env[canonical]:
                    evidence_by_env[canonical].append(path)
    entities: list[ProjectEntity] = []
    for env, evidence in sorted(evidence_by_env.items()):
        entities.append(
            ProjectEntity(
                id=_entity_id(EntityType.ENVIRONMENT, env),
                type=EntityType.ENVIRONMENT,
                name=env,
                analyzer=analyzer,
                confidence=Confidence.MEDIUM,
                status=EvidenceStatus.INFERRED,
                source_file=evidence[0],
                metadata={"evidence_paths": str(len(evidence))},
            )
        )
    return entities


def _finding_category(finding: AnalysisFinding, default: str) -> str:
    text = f"{finding.title} {finding.description}".lower()
    if any(word in text for word in ("secret", "iam", "permission", "public", "root", "plaintext")):
        return FindingCategory.SECURITY
    if any(word in text for word in ("state", "approval", "deploy", "registry", "rollback")):
        return FindingCategory.DEPLOYMENT
    if any(word in text for word in ("replica", "health", "limit", "backup", "retry", "latest")):
        return FindingCategory.RELIABILITY
    if any(word in text for word in ("test", "coverage", "lint")):
        return FindingCategory.TESTING
    if any(word in text for word in ("monitor", "alert", "log", "metric")):
        return FindingCategory.OBSERVABILITY
    return default


def _findings(
    findings: list[AnalysisFinding], analyzer: str, default_category: str
) -> list[ProjectFinding]:
    out: list[ProjectFinding] = []
    for finding in findings:
        out.append(
            ProjectFinding(
                id=f"{analyzer}:{finding.id}",
                category=_finding_category(finding, default_category),
                severity=finding.severity,
                title=finding.title,
                explanation=finding.description,
                analyzer=analyzer,
                confidence=Confidence.HIGH,
                source_file=finding.evidence[0] if finding.evidence else None,
                evidence=list(finding.evidence),
            )
        )
    return out


def from_terraform(
    result: TerraformAnalysisResult,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    entities: list[ProjectEntity] = [
        ProjectEntity(
            id=_entity_id(EntityType.INFRA_COMPONENT, "terraform"),
            type=EntityType.INFRA_COMPONENT,
            name="Terraform",
            analyzer="terraform",
            source_file=result.files[0] if result.files else None,
            metadata={
                "files": str(result.total_terraform_files),
                "remote_state": str(result.has_backend_config),
                "modules": str(result.has_modules),
            },
        )
    ]
    entities.extend(environments_from_paths(result.files, "terraform"))
    findings = _findings(result.findings, "terraform", FindingCategory.CONFIGURATION)
    return entities, [], findings


def from_terragrunt(
    result: TerragruntAnalysisResult,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    entities: list[ProjectEntity] = [
        ProjectEntity(
            id=_entity_id(EntityType.INFRA_COMPONENT, "terragrunt"),
            type=EntityType.INFRA_COMPONENT,
            name="Terragrunt",
            analyzer="terragrunt",
            source_file=result.files[0] if result.files else None,
            metadata={
                "files": str(result.total_terragrunt_files),
                "remote_state": str(result.has_remote_state),
                "dependencies": str(result.has_dependencies),
            },
        )
    ]
    entities.extend(environments_from_paths(result.files, "terragrunt"))
    findings = _findings(result.findings, "terragrunt", FindingCategory.CONFIGURATION)
    return entities, [], findings


def from_gitlab_ci(
    result: GitLabCIAnalysisResult,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    pipeline = ProjectEntity(
        id=_entity_id(EntityType.PIPELINE, "gitlab-ci"),
        type=EntityType.PIPELINE,
        name="GitLab CI",
        analyzer="gitlab_ci",
        source_file=result.file_path,
        metadata={"stages": ", ".join(result.stages), "jobs": str(result.jobs_count)},
    )
    entities: list[ProjectEntity] = [pipeline]
    relations: list[ProjectRelation] = []
    for job in result.jobs:
        job_entity = ProjectEntity(
            id=_entity_id(EntityType.PIPELINE_JOB, job.name),
            type=EntityType.PIPELINE_JOB,
            name=job.name,
            analyzer="gitlab_ci",
            source_file=result.file_path,
            metadata={"stage": job.stage or "", "image": job.image or ""},
        )
        entities.append(job_entity)
        relations.append(
            ProjectRelation(
                id=_relation_id(pipeline.id, RelationType.INCLUDES, job_entity.id),
                source_entity_id=pipeline.id,
                target_entity_id=job_entity.id,
                relation_type=RelationType.INCLUDES,
                analyzer="gitlab_ci",
                source_file=result.file_path,
            )
        )
        if job.image:
            image = ProjectEntity(
                id=_entity_id(EntityType.CONTAINER_IMAGE, job.image),
                type=EntityType.CONTAINER_IMAGE,
                name=job.image,
                analyzer="gitlab_ci",
                source_file=result.file_path,
            )
            entities.append(image)
            relations.append(
                ProjectRelation(
                    id=_relation_id(job_entity.id, RelationType.RUNS, image.id),
                    source_entity_id=job_entity.id,
                    target_entity_id=image.id,
                    relation_type=RelationType.RUNS,
                    analyzer="gitlab_ci",
                    source_file=result.file_path,
                    evidence=[f"job '{job.name}' uses image {job.image}"],
                )
            )
    findings = _findings(result.findings, "gitlab_ci", FindingCategory.DEPLOYMENT)
    return entities, relations, findings


def from_github_actions(
    result: GitHubActionsAnalysisResult,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    entities: list[ProjectEntity] = []
    for workflow in result.workflows:
        name = workflow.name or os.path.basename(workflow.path)
        entities.append(
            ProjectEntity(
                id=_entity_id(EntityType.PIPELINE, name),
                type=EntityType.PIPELINE,
                name=name,
                analyzer="github_actions",
                source_file=workflow.path,
                metadata={
                    "triggers": ", ".join(workflow.triggers),
                    "jobs": str(workflow.jobs_count),
                    "uses_secrets": str(workflow.has_secrets_reference),
                },
            )
        )
    findings = _findings(result.findings, "github_actions", FindingCategory.DEPLOYMENT)
    return entities, [], findings


# Deterministic "important file" scoring: a path's importance comes from its
# role (entrypoint, infra root, CI, env root, dependency manifest, docs), not
# from an LLM guess. Returns (path, score, reason) tuples, highest first.
_IMPORTANT_FILE_RULES: list[tuple[re.Pattern[str], int, str]] = [
    (re.compile(r"(^|/)\.github/workflows/.+\.ya?ml$"), 90, "CI/CD workflow"),
    (re.compile(r"(^|/)\.gitlab-ci\.ya?ml$"), 90, "CI/CD pipeline definition"),
    (re.compile(r"(^|/)terragrunt\.hcl$"), 85, "Terragrunt configuration"),
    (re.compile(r"(^|/)(main|backend|providers?|versions)\.tf$"), 80, "Terraform root"),
    (re.compile(r"(^|/)dockerfile$", re.IGNORECASE), 80, "Container build"),
    (re.compile(r"(^|/)docker-compose\.ya?ml$"), 75, "Compose services"),
    (re.compile(r"(^|/)(package\.json|pyproject\.toml|requirements\.txt|go\.mod|cargo\.toml|pom\.xml)$"), 70, "Dependency manifest"),
    (re.compile(r"(^|/)readme(\.md|\.rst|\.txt)?$", re.IGNORECASE), 60, "Project README"),
    (re.compile(r"(^|/)(variables|outputs)\.tf$"), 55, "Terraform interface"),
]


def important_files(paths: list[str], limit: int = 12) -> list[dict[str, str]]:
    """Score and rank notable files with a plain-language reason for each."""
    scored: dict[str, tuple[int, str]] = {}
    for path in paths:
        for pattern, score, reason in _IMPORTANT_FILE_RULES:
            if pattern.search(path):
                existing = scored.get(path)
                if existing is None or score > existing[0]:
                    scored[path] = (score, reason)
                break
    ranked = sorted(scored.items(), key=lambda item: (-item[1][0], item[0]))
    return [{"path": path, "reason": reason} for path, (_, reason) in ranked[:limit]]


def build_project_graph(
    workspace_id: str,
    *,
    terraform: TerraformAnalysisResult | None = None,
    terragrunt: TerragruntAnalysisResult | None = None,
    gitlab_ci: GitLabCIAnalysisResult | None = None,
    github_actions: GitHubActionsAnalysisResult | None = None,
    analyzers_skipped: list[str] | None = None,
) -> ProjectGraph:
    """Compose all available analyzer results into one role-neutral graph.

    De-duplicates entities by id (e.g. the same environment seen by both
    Terraform and Terragrunt) and reports which analyzers ran vs were skipped.
    """
    entities: dict[str, ProjectEntity] = {}
    relations: dict[str, ProjectRelation] = {}
    findings: list[ProjectFinding] = []
    analyzers_run: list[str] = []

    def absorb(
        triple: tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]],
        analyzer: str,
    ) -> None:
        ents, rels, finds = triple
        for entity in ents:
            entities.setdefault(entity.id, entity)
        for rel in rels:
            relations.setdefault(rel.id, rel)
        findings.extend(finds)
        analyzers_run.append(analyzer)

    if terraform is not None:
        absorb(from_terraform(terraform), "terraform")
    if terragrunt is not None:
        absorb(from_terragrunt(terragrunt), "terragrunt")
    if gitlab_ci is not None:
        absorb(from_gitlab_ci(gitlab_ci), "gitlab_ci")
    if github_actions is not None:
        absorb(from_github_actions(github_actions), "github_actions")

    return ProjectGraph(
        workspace_id=workspace_id,
        entities=list(entities.values()),
        relations=list(relations.values()),
        findings=findings,
        analyzers_run=analyzers_run,
        analyzers_skipped=list(analyzers_skipped or []),
    )
