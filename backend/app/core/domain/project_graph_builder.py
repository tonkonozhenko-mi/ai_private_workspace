"""Turn the existing analyzers' structured results into a role-neutral
``ProjectGraph``. Pure, deterministic, no LLM — every element keeps its source,
evidence, confidence and status so the UI can show exactly why it's there.

This composes (does not replace) the existing analyzers in
``app/core/use_cases/analyze_*`` via their domain results in
``app/core/domain/analysis.py``.
"""

import json
import os
import re

from app.core.domain.analysis import (
    AnalysisFinding,
    GitHubActionsAnalysisResult,
    GitLabCIAnalysisResult,
    HelmAnalysisResult,
    KubernetesAnalysisResult,
    PythonAnalysisResult,
    ReferenceAnalysisResult,
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
    "prd": "prod",
    "prn": "prod",
    "production": "prod",
    "live": "prod",
    "perf": "perf",
    "demo": "demo",
    "int": "integration",
    "intg": "integration",
    "integration": "integration",
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


def _environments_from_labels(
    labels: list[tuple[str, str]], analyzer: str
) -> list[ProjectEntity]:
    """Infer environments from named labels (e.g. Kubernetes namespaces or
    ``values-<env>.yaml`` filenames). Each label is tokenised on non-alphanumeric
    separators and matched against the canonical environment tokens. Like the
    path-based inference, this is INFERRED (a naming convention), never asserted.

    ``labels`` is a list of ``(label, evidence)`` pairs.
    """
    evidence_by_env: dict[str, list[str]] = {}
    for label, evidence in labels:
        for token in re.split(r"[^a-z0-9]+", label.lower()):
            canonical = _ENV_TOKENS.get(token)
            if canonical:
                evidence_by_env.setdefault(canonical, [])
                if evidence not in evidence_by_env[canonical]:
                    evidence_by_env[canonical].append(evidence)
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
    terraform = ProjectEntity(
        id=_entity_id(EntityType.INFRA_COMPONENT, "terraform"),
        type=EntityType.INFRA_COMPONENT,
        name="Terraform",
        analyzer="terraform",
        # A meaningful representative root (main/backend/providers.tf), not a
        # random file. None when there is no obvious root.
        source_file=result.root_files[0] if result.root_files else None,
        metadata={
            "files": str(result.total_terraform_files),
            "remote_state": str(result.has_backend_config),
            "modules": str(result.has_modules),
            "providers": ", ".join(result.providers),
            "root_files": str(len(result.root_files)),
        },
    )
    entities: list[ProjectEntity] = [terraform]
    relations: list[ProjectRelation] = []

    environments = environments_from_paths(result.files, "terraform")
    entities.extend(environments)
    # Connect Terraform to the environments it manages so the map reads as a flow.
    for env in environments:
        relations.append(
            ProjectRelation(
                id=_relation_id(terraform.id, RelationType.CONFIGURES, env.id),
                source_entity_id=terraform.id,
                target_entity_id=env.id,
                relation_type=RelationType.CONFIGURES,
                analyzer="terraform",
                source_file=env.source_file,
            )
        )

    # Cloud services provisioned by these resources, grouped by (provider, service).
    cloud_entities, cloud_relations = _cloud_entities(
        result.cloud_resources, terraform.id, "terraform"
    )
    entities.extend(cloud_entities)
    relations.extend(cloud_relations)

    findings = _findings(result.findings, "terraform", FindingCategory.CONFIGURATION)
    return entities, relations, findings


def _cloud_entities(
    cloud_resources, source_entity_id: str, analyzer: str
) -> tuple[list[ProjectEntity], list[ProjectRelation]]:
    """Group raw cloud resource refs into one entity per (provider, service)."""
    from app.core.domain.cloud_catalog import cloud_for_resource

    grouped: dict[tuple[str, str], dict] = {}
    for ref in cloud_resources:
        mapped = cloud_for_resource(ref.resource_type)
        if mapped is None:
            continue
        provider, service = mapped
        key = (provider, service)
        bucket = grouped.setdefault(
            key, {"count": 0, "source": ref.source_file, "types": set()}
        )
        bucket["count"] += 1
        bucket["types"].add(ref.resource_type)

    entities: list[ProjectEntity] = []
    relations: list[ProjectRelation] = []
    for (provider, service), data in sorted(grouped.items()):
        name = f"{provider} · {service}"
        entity = ProjectEntity(
            id=_entity_id(EntityType.CLOUD_SERVICE, name),
            type=EntityType.CLOUD_SERVICE,
            name=name,
            analyzer=analyzer,
            source_file=data["source"],
            metadata={
                "provider": provider,
                "service": service,
                "resources": str(data["count"]),
            },
        )
        entities.append(entity)
        relations.append(
            ProjectRelation(
                id=_relation_id(source_entity_id, RelationType.PROVISIONS, entity.id),
                source_entity_id=source_entity_id,
                target_entity_id=entity.id,
                relation_type=RelationType.PROVISIONS,
                analyzer=analyzer,
                source_file=data["source"],
            )
        )
    return entities, relations


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
    relations: list[ProjectRelation] = []
    for workflow in result.workflows:
        name = workflow.name or os.path.basename(workflow.path)
        triggers_json = json.dumps(
            [
                {
                    "event": t.event,
                    "branches": t.branches,
                    "branches_ignore": t.branches_ignore,
                    "tags": t.tags,
                    "paths": t.paths,
                    "cron": t.cron,
                }
                for t in workflow.trigger_rules
            ]
        )
        pipeline = ProjectEntity(
            id=_entity_id(EntityType.PIPELINE, name),
            type=EntityType.PIPELINE,
            name=name,
            analyzer="github_actions",
            source_file=workflow.path,
            metadata={
                "triggers": ", ".join(workflow.triggers),
                "jobs": str(workflow.jobs_count),
                "uses_secrets": str(workflow.has_secrets_reference),
                "triggers_json": triggers_json,
            },
        )
        entities.append(pipeline)
        for job_name in workflow.job_names:
            # Namespace the job id by workflow so identically named jobs in
            # different workflows stay distinct.
            job = ProjectEntity(
                id=_entity_id(EntityType.PIPELINE_JOB, f"{name}-{job_name}"),
                type=EntityType.PIPELINE_JOB,
                name=job_name,
                analyzer="github_actions",
                source_file=workflow.path,
                metadata={"pipeline": name},
            )
            entities.append(job)
            relations.append(
                ProjectRelation(
                    id=_relation_id(pipeline.id, RelationType.INCLUDES, job.id),
                    source_entity_id=pipeline.id,
                    target_entity_id=job.id,
                    relation_type=RelationType.INCLUDES,
                    analyzer="github_actions",
                    source_file=workflow.path,
                )
            )
    findings = _findings(result.findings, "github_actions", FindingCategory.DEPLOYMENT)
    return entities, relations, findings


def from_kubernetes(
    result: KubernetesAnalysisResult,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    first_source = result.workloads[0].source_file if result.workloads else None
    platform = ProjectEntity(
        id=_entity_id(EntityType.INFRA_COMPONENT, "kubernetes"),
        type=EntityType.INFRA_COMPONENT,
        name="Kubernetes",
        analyzer="kubernetes",
        source_file=first_source,
        metadata={
            "manifests": str(result.manifests_count),
            "workloads": str(len(result.workloads)),
            "services": str(result.services_count),
            "namespaces": ", ".join(result.namespaces),
        },
    )
    entities: list[ProjectEntity] = [platform]
    relations: list[ProjectRelation] = []

    for workload in result.workloads:
        service = ProjectEntity(
            id=_entity_id(EntityType.SERVICE, workload.name),
            type=EntityType.SERVICE,
            name=workload.name,
            analyzer="kubernetes",
            confidence=Confidence.HIGH,
            status=EvidenceStatus.CONFIRMED,
            source_file=workload.source_file,
            metadata={
                "kind": workload.kind,
                "namespace": workload.namespace or "",
                "replicas": "" if workload.replicas is None else str(workload.replicas),
            },
        )
        entities.append(service)
        relations.append(
            ProjectRelation(
                id=_relation_id(platform.id, RelationType.DEPLOYS, service.id),
                source_entity_id=platform.id,
                target_entity_id=service.id,
                relation_type=RelationType.DEPLOYS,
                analyzer="kubernetes",
                source_file=workload.source_file,
                evidence=[f"{workload.kind} '{workload.name}'"],
            )
        )
        for image_name in workload.images:
            image = ProjectEntity(
                id=_entity_id(EntityType.CONTAINER_IMAGE, image_name),
                type=EntityType.CONTAINER_IMAGE,
                name=image_name,
                analyzer="kubernetes",
                source_file=workload.source_file,
            )
            entities.append(image)
            relations.append(
                ProjectRelation(
                    id=_relation_id(service.id, RelationType.RUNS, image.id),
                    source_entity_id=service.id,
                    target_entity_id=image.id,
                    relation_type=RelationType.RUNS,
                    analyzer="kubernetes",
                    source_file=workload.source_file,
                    evidence=[f"{workload.name} runs image {image_name}"],
                )
            )

    # Namespaces whose names carry an environment token are inferred environments.
    entities.extend(
        _environments_from_labels([(ns, ns) for ns in result.namespaces], "kubernetes")
    )
    findings = _findings(result.findings, "kubernetes", FindingCategory.RELIABILITY)
    return entities, relations, findings


def from_helm(
    result: HelmAnalysisResult,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    if not result.charts:
        return [], [], _findings(result.findings, "helm", FindingCategory.DEPLOYMENT)

    platform = ProjectEntity(
        id=_entity_id(EntityType.INFRA_COMPONENT, "helm"),
        type=EntityType.INFRA_COMPONENT,
        name="Helm",
        analyzer="helm",
        source_file=result.charts[0].chart_file,
        metadata={"charts": str(len(result.charts))},
    )
    entities: list[ProjectEntity] = [platform]
    relations: list[ProjectRelation] = []
    env_labels: list[tuple[str, str]] = []

    for chart in result.charts:
        service = ProjectEntity(
            id=_entity_id(EntityType.SERVICE, chart.name),
            type=EntityType.SERVICE,
            name=chart.name,
            analyzer="helm",
            confidence=Confidence.HIGH,
            status=EvidenceStatus.CONFIRMED,
            source_file=chart.chart_file,
            metadata={
                "version": chart.version or "",
                "app_version": chart.app_version or "",
                "templates": str(chart.templates_count),
            },
        )
        entities.append(service)
        relations.append(
            ProjectRelation(
                id=_relation_id(platform.id, RelationType.DEPLOYS, service.id),
                source_entity_id=platform.id,
                target_entity_id=service.id,
                relation_type=RelationType.DEPLOYS,
                analyzer="helm",
                source_file=chart.chart_file,
                evidence=[f"Helm chart '{chart.name}'"],
            )
        )
        for value_file in chart.value_files:
            env_labels.append((os.path.basename(value_file), value_file))

    entities.extend(_environments_from_labels(env_labels, "helm"))
    findings = _findings(result.findings, "helm", FindingCategory.DEPLOYMENT)
    return entities, relations, findings


def from_python(
    result: PythonAnalysisResult,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    has_app = bool(result.frameworks or result.entrypoints or result.modules)
    if not has_app:
        return [], [], _findings(result.findings, "python", FindingCategory.GENERAL)

    app_name = (
        f"{result.frameworks[0]} application" if result.frameworks else "Python application"
    )
    application = ProjectEntity(
        id=_entity_id(EntityType.APPLICATION, app_name),
        type=EntityType.APPLICATION,
        name=app_name,
        analyzer="python",
        source_file=result.entrypoints[0] if result.entrypoints else None,
        metadata={
            "frameworks": ", ".join(result.frameworks),
            "entrypoints": str(len(result.entrypoints)),
            "modules": str(len(result.modules)),
            "has_tests": str(result.has_tests),
        },
    )
    entities: list[ProjectEntity] = [application]
    relations: list[ProjectRelation] = []

    module_ids: dict[str, str] = {}
    for module in result.modules:
        entity = ProjectEntity(
            id=_entity_id(EntityType.MODULE, module.name),
            type=EntityType.MODULE,
            name=module.name,
            analyzer="python",
            confidence=Confidence.HIGH,
            status=EvidenceStatus.CONFIRMED,
            source_file=module.path,
            metadata={"internal_imports": str(len(module.internal_imports))},
        )
        entities.append(entity)
        module_ids[module.name] = entity.id
        relations.append(
            ProjectRelation(
                id=_relation_id(application.id, RelationType.INCLUDES, entity.id),
                source_entity_id=application.id,
                target_entity_id=entity.id,
                relation_type=RelationType.INCLUDES,
                analyzer="python",
                source_file=module.path,
            )
        )

    # Internal module → module import edges (the project's own architecture).
    for module in result.modules:
        for target in module.internal_imports:
            target_id = module_ids.get(target)
            if target_id is None:
                continue
            source_id = module_ids[module.name]
            relations.append(
                ProjectRelation(
                    id=_relation_id(source_id, RelationType.DEPENDS_ON, target_id),
                    source_entity_id=source_id,
                    target_entity_id=target_id,
                    relation_type=RelationType.DEPENDS_ON,
                    analyzer="python",
                    evidence=[f"{module.name} imports {target}"],
                )
            )

    for dep in result.notable_dependencies:
        dep_entity = ProjectEntity(
            id=_entity_id(EntityType.DEPENDENCY, dep),
            type=EntityType.DEPENDENCY,
            name=dep,
            analyzer="python",
            source_file=result.dependency_files[0] if result.dependency_files else None,
        )
        entities.append(dep_entity)
        relations.append(
            ProjectRelation(
                id=_relation_id(application.id, RelationType.DEPENDS_ON, dep_entity.id),
                source_entity_id=application.id,
                target_entity_id=dep_entity.id,
                relation_type=RelationType.DEPENDS_ON,
                analyzer="python",
            )
        )

    findings = _findings(result.findings, "python", FindingCategory.GENERAL)
    return entities, relations, findings


def from_references(
    result: ReferenceAnalysisResult,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    entities: list[ProjectEntity] = []
    for ref in result.references:
        entities.append(
            ProjectEntity(
                id=_entity_id(EntityType.REFERENCE, f"{ref.kind}:{ref.value}"),
                type=EntityType.REFERENCE,
                name=ref.value,
                analyzer="references",
                source_file=ref.source_file or None,
                metadata={"kind": ref.kind, "count": str(ref.count)},
            )
        )
    return entities, [], []


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
    kubernetes: KubernetesAnalysisResult | None = None,
    helm: HelmAnalysisResult | None = None,
    python: PythonAnalysisResult | None = None,
    references: ReferenceAnalysisResult | None = None,
    scan_paths: list[str] | None = None,
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
    if kubernetes is not None:
        absorb(from_kubernetes(kubernetes), "kubernetes")
    if helm is not None:
        absorb(from_helm(helm), "helm")
    if python is not None:
        absorb(from_python(python), "python")
    if references is not None:
        absorb(from_references(references), "references")

    # Important files become config_file entities (with a plain-language reason),
    # so the "Important files" section is part of the same evidence graph.
    for important in important_files(scan_paths or []):
        path = important["path"]
        entity_id = _entity_id(EntityType.CONFIG_FILE, path)
        entities.setdefault(
            entity_id,
            ProjectEntity(
                id=entity_id,
                type=EntityType.CONFIG_FILE,
                name=path,
                analyzer="scan",
                source_file=path,
                metadata={"reason": important["reason"]},
            ),
        )

    return ProjectGraph(
        workspace_id=workspace_id,
        entities=list(entities.values()),
        relations=list(relations.values()),
        findings=findings,
        analyzers_run=analyzers_run,
        analyzers_skipped=list(analyzers_skipped or []),
    )
