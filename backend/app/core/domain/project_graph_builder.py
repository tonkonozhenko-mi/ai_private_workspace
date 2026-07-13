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
from dataclasses import replace

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
from app.core.domain.api_surface import ApiSurface
from app.core.domain.js_modules import JsFacts
from app.core.domain.knowledge_base import KnowledgeBase, area_family
from app.core.domain.ownership import OwnershipFacts
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
    Severity,
)
from app.core.domain.source_files import dominant_source_language
from app.core.domain.sql_schema import (
    SqlSchema,
    orphan_tables,
    tables_without_primary_key,
    unindexed_foreign_keys,
)
from app.core.domain.test_suites import TestFacts

# One stray .ts helper in a Terraform repo is not "a TypeScript application".
# Three files is the point where the code is the project, not a footnote.
_MIN_SOURCE_FILES_FOR_APPLICATION = 3


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
                # The environment's root directory (e.g. "accounts/dev/"), not a
                # random deep file — reads as the place the env actually lives.
                source_file=_env_root(evidence, env),
                metadata={"evidence_paths": str(len(evidence))},
            )
        )
    return entities


def _env_root(evidence: list[str], env: str) -> str | None:
    """Directory prefix up to and including the environment segment, from the
    shallowest evidence path. e.g. accounts/dev/us-east-1/x.tf -> accounts/dev/."""
    if not evidence:
        return None
    shallowest = min(evidence, key=lambda p: (p.count("/"), len(p)))
    segments = shallowest.split("/")
    for index, segment in enumerate(segments):
        if _ENV_TOKENS.get(segment.lower()) == env:
            return "/".join(segments[: index + 1]) + "/"
    return shallowest


def _environments_from_labels(labels: list[tuple[str, str]], analyzer: str) -> list[ProjectEntity]:
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
        # An aggregate over many files has no single meaningful source — a lone
        # representative path just reads as noise, so don't pin one.
        source_file=None,
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
        bucket = grouped.setdefault(key, {"count": 0, "source": ref.source_file, "types": set()})
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
            source_file=None,
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
    entities.extend(_environments_from_labels([(ns, ns) for ns in result.namespaces], "kubernetes"))
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

    app_name = f"{result.frameworks[0]} application" if result.frameworks else "Python application"
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


def from_sql_schema(
    schema: SqlSchema,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    """The data model, as the project itself wrote it down.

    Findings are stated as facts a DBA can act on, never as verdicts: a table with no
    primary key may be a deliberate append-only log, and an unindexed foreign key on a
    tiny lookup table costs nothing. We say what is there and why it usually matters.
    """
    entities: list[ProjectEntity] = []
    relations: list[ProjectRelation] = []
    findings: list[ProjectFinding] = []

    for table in schema.tables:
        entities.append(
            ProjectEntity(
                id=_entity_id(EntityType.TABLE, table.name),
                type=EntityType.TABLE,
                name=table.name,
                analyzer="sql",
                source_file=table.source_file or None,
                metadata={
                    "columns": ", ".join(column.name for column in table.columns[:24]),
                    "columns_count": str(len(table.columns)),
                    "primary_key": ", ".join(table.primary_key),
                    "kind": "view" if table.is_view else "table",
                },
            )
        )

    for foreign_key in schema.foreign_keys:
        source_id = _entity_id(EntityType.TABLE, foreign_key.from_table)
        target_id = _entity_id(EntityType.TABLE, foreign_key.to_table)
        column = foreign_key.from_column or "foreign key"
        relations.append(
            ProjectRelation(
                id=_relation_id(source_id, RelationType.REFERENCES, target_id),
                source_entity_id=source_id,
                target_entity_id=target_id,
                relation_type=RelationType.REFERENCES,
                analyzer="sql",
                source_file=foreign_key.source_file,
                evidence=[f"{foreign_key.from_table}.{column} references {foreign_key.to_table}"],
            )
        )

    for index, migration in enumerate(schema.migrations, start=1):
        name = migration.path.rsplit("/", 1)[-1]
        entities.append(
            ProjectEntity(
                id=_entity_id(EntityType.MIGRATION, migration.path),
                type=EntityType.MIGRATION,
                name=name,
                analyzer="sql",
                source_file=migration.path,
                metadata={
                    "order": str(index),
                    "creates": ", ".join(migration.creates),
                    "alters": ", ".join(migration.alters),
                    "drops": ", ".join(migration.drops),
                },
            )
        )

    missing_pk = tables_without_primary_key(schema)
    if missing_pk:
        findings.append(
            ProjectFinding(
                id="sql:tables_without_primary_key",
                category=FindingCategory.RELIABILITY,
                severity=Severity.MEDIUM,
                title=f"{len(missing_pk)} table(s) have no primary key",
                explanation=(
                    "No PRIMARY KEY is declared for "
                    + ", ".join(missing_pk[:6])
                    + ". Rows in these tables cannot be addressed individually, which makes "
                    "replication, de-duplication and safe updates harder. An append-only log "
                    "may not need one — the others usually do."
                ),
                analyzer="sql",
                evidence=missing_pk[:12],
                recommendation="Confirm each is intentional; add a key where it is not.",
            )
        )

    unindexed = unindexed_foreign_keys(schema)
    if unindexed:
        findings.append(
            ProjectFinding(
                id="sql:unindexed_foreign_keys",
                category=FindingCategory.RELIABILITY,
                severity=Severity.LOW,
                title=f"{len(unindexed)} table(s) reference another table with no index",
                explanation=(
                    "These tables have a foreign key but no index on the referencing side: "
                    + ", ".join(unindexed[:6])
                    + ". Joins scan, and a DELETE on the parent takes a lock while it checks "
                    "children. On a small table this costs nothing; on a large one it is the "
                    "usual cause of a slow query nobody can explain."
                ),
                analyzer="sql",
                evidence=unindexed[:12],
            )
        )

    orphans = orphan_tables(schema)
    if orphans:
        findings.append(
            ProjectFinding(
                id="sql:unreferenced_tables",
                category=FindingCategory.GENERAL,
                severity=Severity.INFO,
                title=f"{len(orphans)} table(s) stand alone in the schema",
                explanation=(
                    "Nothing references these and they reference nothing: "
                    + ", ".join(orphans[:8])
                    + ". Some are dead; some are the most important table in the system "
                    "(an events log, an audit trail). Worth a glance, not an alarm."
                ),
                analyzer="sql",
                evidence=orphans[:12],
            )
        )

    return entities, relations, findings


def from_knowledge_base(
    base: KnowledgeBase,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    """A wiki's own facts: its pages, the areas its titles announce, its decisions —
    and the two things that quietly rot a knowledge base.

    The findings are deliberately mild in tone and specific in evidence. A page nobody
    links to is *reported*, not condemned: it may be a new page, or a leaf everyone
    reaches from search. A page a year old is only worth mentioning when other pages
    still point at it — that is when out-of-date stops being harmless.

    None of that is true of a repository's documents. A hundred READMEs in an
    infrastructure monorepo do not link to one another and were never meant to; telling
    their author that "nothing links to" each of them is the mirror image of telling a
    wiki it has no tests. So when the collection is not a knowledge base
    (``base.is_knowledge_base``), the documents are listed and nothing more is claimed
    about them.
    """
    entities: list[ProjectEntity] = []
    relations: list[ProjectRelation] = []
    findings: list[ProjectFinding] = []
    knowledge = base.is_knowledge_base

    for area, count in base.areas.items():
        entities.append(
            ProjectEntity(
                id=_entity_id(EntityType.TOPIC, area),
                type=EntityType.TOPIC,
                name=area,
                analyzer="documentation",
                metadata={"pages": str(count)},
            )
        )

    for document in base.documents:
        entity_type = EntityType.DECISION if document.is_decision else EntityType.DOCUMENT
        entities.append(
            ProjectEntity(
                id=_entity_id(entity_type, document.path),
                type=entity_type,
                name=document.title,
                analyzer="documentation",
                source_file=document.path,
                metadata={
                    "area": document.area or "",
                    # Only a knowledge base has a link graph worth reading. In a
                    # repository this number would be zero for every document and would
                    # be read as an accusation.
                    **(
                        {"linked_from": str(base.inbound_links.get(document.path, 0))}
                        if knowledge
                        else {}
                    ),
                    "attachments": str(len(document.attachments)),
                    "diagrams": ", ".join(document.diagrams[:3]),
                },
            )
        )
        family = area_family(document.area)
        if family:
            topic_id = _entity_id(EntityType.TOPIC, family)
            page_id = _entity_id(entity_type, document.path)
            relations.append(
                ProjectRelation(
                    id=_relation_id(topic_id, RelationType.INCLUDES, page_id),
                    source_entity_id=topic_id,
                    target_entity_id=page_id,
                    relation_type=RelationType.INCLUDES,
                    analyzer="documentation",
                    source_file=document.path,
                )
            )
        for target in document.links_to:
            target_type = (
                EntityType.DECISION
                if any(d.path == target and d.is_decision for d in base.documents)
                else EntityType.DOCUMENT
            )
            source_id = _entity_id(entity_type, document.path)
            target_id = _entity_id(target_type, target)
            relations.append(
                ProjectRelation(
                    id=_relation_id(source_id, RelationType.REFERENCES, target_id),
                    source_entity_id=source_id,
                    target_entity_id=target_id,
                    relation_type=RelationType.REFERENCES,
                    analyzer="documentation",
                    source_file=document.path,
                )
            )

    if not knowledge:
        # A repository's documents are listed, and that is all. Everything below reads
        # a wiki's link graph, which this collection does not have and never had.
        return entities, relations, findings

    for document in base.stale_but_relied_on():
        inbound = base.inbound_links.get(document.path, 0)
        findings.append(
            ProjectFinding(
                id=f"documentation:stale:{document.path}",
                category=FindingCategory.DOCUMENTATION,
                severity=Severity.MEDIUM,
                title=f'"{document.title}" has not changed in over a year',
                explanation=(
                    f"{inbound} other pages link to it, so it is still being treated as "
                    "the source of truth. Old is not wrong — but old and relied upon is "
                    "worth a look."
                ),
                analyzer="documentation",
                evidence=[document.path],
            )
        )

    # No links between the pages at all — say so once, plainly, instead of accusing
    # every page in the folder of being unreachable. A browser-saved wiki keeps its
    # links as URLs back to the original site, so nothing on disk points at anything
    # else on disk; that is a fact about the export, not a problem with the writing.
    if base.documents and not base.has_link_graph:
        findings.append(
            ProjectFinding(
                id="documentation:no_link_graph",
                category=FindingCategory.DOCUMENTATION,
                severity=Severity.INFO,
                title="These pages carry no links to each other",
                explanation=(
                    "The export kept the text but not the links between pages — they "
                    "most likely still point back at the original wiki. Nothing is "
                    "wrong with the pages; it means this map cannot show which of them "
                    "are central and which are forgotten. Search and Ask read all "
                    f"{len(base.documents)} of them regardless."
                ),
                analyzer="documentation",
            )
        )

    orphans = base.orphans
    if orphans:
        findings.append(
            ProjectFinding(
                id="documentation:orphan_pages",
                category=FindingCategory.DOCUMENTATION,
                severity=Severity.LOW,
                title=f"{len(orphans)} pages nothing links to",
                explanation=(
                    "No other page points at them, so they are found only by searching. "
                    "That is not a defect — an entry point is an orphan by definition — "
                    "but it is where unread pages hide: "
                    + ", ".join(document.title for document in orphans[:5])
                    + ("…" if len(orphans) > 5 else "")
                ),
                analyzer="documentation",
                evidence=[document.path for document in orphans[:10]],
            )
        )

    return entities, relations, findings


def from_tests(
    facts: TestFacts,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    """Where the tests are, what runs them, and what nothing mentions."""
    entities: list[ProjectEntity] = []
    findings: list[ProjectFinding] = []

    for suite in facts.suites:
        entities.append(
            ProjectEntity(
                id=_entity_id(EntityType.TEST_SUITE, suite.path),
                type=EntityType.TEST_SUITE,
                name=suite.path,
                analyzer="tests",
                source_file=suite.path,
                metadata={
                    "files": str(suite.files_count),
                    "test_cases": str(suite.test_cases),
                    "skipped": str(suite.skipped_cases),
                    "frameworks": ", ".join(suite.frameworks),
                    "run_with": ", ".join(facts.run_commands[:2]),
                },
            )
        )

    # Only a project that HAS code can be missing tests for it. A folder of
    # documentation was being told, in red, that it had no test files — a true
    # sentence about something it never claimed to be.
    if not facts.suites and facts.source_files > 0:
        findings.append(
            ProjectFinding(
                id="tests:no_tests_found",
                category=FindingCategory.TESTING,
                severity=Severity.HIGH,
                title="No test files were found",
                explanation=(
                    "The scan found no file that lives in a test directory or imports a test "
                    "framework. Either this project has no automated tests, or they live "
                    "somewhere the scan does not reach."
                ),
                analyzer="tests",
            )
        )

    if facts.skipped_cases:
        findings.append(
            ProjectFinding(
                id="tests:skipped_cases",
                category=FindingCategory.TESTING,
                severity=Severity.LOW,
                title=f"{facts.skipped_cases} test(s) are skipped",
                explanation=(
                    "These tests exist but do not run (skip / xfail / it.skip). A skipped test "
                    "protects nothing while still looking like coverage on the dashboard."
                ),
                analyzer="tests",
            )
        )

    if facts.untested_areas:
        findings.append(
            ProjectFinding(
                id="tests:areas_no_test_mentions",
                category=FindingCategory.TESTING,
                severity=Severity.MEDIUM,
                title=f"{len(facts.untested_areas)} area(s) are not mentioned by any test",
                explanation=(
                    "No test file so much as names: "
                    + ", ".join(facts.untested_areas[:6])
                    + ". This is not a coverage measurement — we do not run the tests — but it "
                    "is a good place for a tester to start asking."
                ),
                analyzer="tests",
                evidence=facts.untested_areas[:12],
            )
        )

    if facts.suites and not facts.ci_test_jobs:
        findings.append(
            ProjectFinding(
                id="tests:not_run_in_ci",
                category=FindingCategory.TESTING,
                severity=Severity.MEDIUM,
                title="Tests exist, but no CI job looks like it runs them",
                explanation=(
                    "The project has tests, and none of the pipeline's job names mention test, "
                    "spec or check. Tests that only run on a laptop stop running."
                ),
                analyzer="tests",
            )
        )

    return entities, [], findings


def from_javascript(
    facts: JsFacts,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    """A JS/TS codebase as an application with modules — the same shape the Python
    analyzer produces, so the map does not care which language it is looking at."""
    if not facts.modules and not facts.frameworks:
        return [], [], []

    entities: list[ProjectEntity] = []
    relations: list[ProjectRelation] = []

    app_name = (
        f"{facts.frameworks[0]} application" if facts.frameworks else "JavaScript application"
    )
    application = ProjectEntity(
        id=_entity_id(EntityType.APPLICATION, app_name),
        type=EntityType.APPLICATION,
        name=app_name,
        analyzer="javascript",
        source_file=facts.entrypoints[0] if facts.entrypoints else None,
        metadata={
            "frameworks": ", ".join(facts.frameworks),
            "package": facts.package_name or "",
            "entrypoints": str(len(facts.entrypoints)),
            "modules": str(len(facts.modules)),
            "scripts": ", ".join(list(facts.scripts)[:8]),
        },
    )
    entities.append(application)

    module_ids: dict[str, str] = {}
    for module in facts.modules:
        entity_id = _entity_id(EntityType.MODULE, module.name)
        module_ids[module.name] = entity_id
        entities.append(
            ProjectEntity(
                id=entity_id,
                type=EntityType.MODULE,
                name=module.name,
                analyzer="javascript",
                source_file=module.path,
            )
        )
        relations.append(
            ProjectRelation(
                id=_relation_id(application.id, RelationType.INCLUDES, entity_id),
                source_entity_id=application.id,
                target_entity_id=entity_id,
                relation_type=RelationType.INCLUDES,
                analyzer="javascript",
            )
        )

    for module in facts.modules:
        source_id = module_ids[module.name]
        for target in module.internal_imports:
            target_id = module_ids.get(target)
            if not target_id or target_id == source_id:
                continue
            relations.append(
                ProjectRelation(
                    id=_relation_id(source_id, RelationType.DEPENDS_ON, target_id),
                    source_entity_id=source_id,
                    target_entity_id=target_id,
                    relation_type=RelationType.DEPENDS_ON,
                    analyzer="javascript",
                    evidence=[f"{module.name} imports {target}"],
                )
            )

    for dependency in facts.notable_dependencies:
        dependency_id = _entity_id(EntityType.DEPENDENCY, dependency)
        entities.append(
            ProjectEntity(
                id=dependency_id,
                type=EntityType.DEPENDENCY,
                name=dependency,
                analyzer="javascript",
            )
        )
        relations.append(
            ProjectRelation(
                id=_relation_id(application.id, RelationType.DEPENDS_ON, dependency_id),
                source_entity_id=application.id,
                target_entity_id=dependency_id,
                relation_type=RelationType.DEPENDS_ON,
                analyzer="javascript",
            )
        )

    return entities, relations, []


def from_api_surface(
    surface: ApiSurface,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    """The verbs the system offers its users, and the nouns it speaks in."""
    entities: list[ProjectEntity] = []

    for endpoint in surface.endpoints[:200]:
        entities.append(
            ProjectEntity(
                id=_entity_id(EntityType.API_ENDPOINT, endpoint.label),
                type=EntityType.API_ENDPOINT,
                name=endpoint.label,
                analyzer="api",
                source_file=endpoint.source_file,
                metadata={
                    "method": endpoint.method.upper(),
                    "path": endpoint.path,
                    "handler": endpoint.handler or "",
                },
            )
        )

    for entity_name in surface.domain_entities[:60]:
        entities.append(
            ProjectEntity(
                id=_entity_id(EntityType.DOMAIN_ENTITY, entity_name),
                type=EntityType.DOMAIN_ENTITY,
                name=entity_name,
                analyzer="api",
            )
        )

    return entities, [], []


def from_ownership(
    facts: OwnershipFacts,
) -> tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]]:
    """The manager's own fact: where the knowledge is concentrated.

    Named carefully. Someone being the sole author of a file is not a failing — it is
    information. The risk is the *concentration*, and only in code that is alive.
    """
    if not facts.single_owner_files:
        return [], [], []

    people = ", ".join(f"{name} ({count})" for name, count in facts.key_people[:3])
    paths = [file.path for file in facts.single_owner_files[:8]]
    finding = ProjectFinding(
        id="ownership:single_owner_files",
        category=FindingCategory.RELIABILITY,
        severity=Severity.MEDIUM if facts.bus_factor <= 2 else Severity.LOW,
        title=(
            f"{len(facts.single_owner_files)} actively-changed file(s) have effectively one author"
        ),
        explanation=(
            "One person has written nearly all of the history of these files: "
            + ", ".join(paths)
            + f". Concentrated in: {people}. That is not a fault — it is where the project's "
            "knowledge lives, and what it would lose if that person were unavailable."
        ),
        analyzer="ownership",
        evidence=paths,
        recommendation="Pair or review across these files before they become the only copy.",
    )
    return [], [], [finding]


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
    (
        re.compile(
            r"(^|/)(package\.json|pyproject\.toml|requirements\.txt|go\.mod|cargo\.toml|pom\.xml)$"
        ),
        70,
        "Dependency manifest",
    ),
    (re.compile(r"(^|/)readme(\.md|\.rst|\.txt)?$", re.IGNORECASE), 60, "Project README"),
    (re.compile(r"(^|/)(variables|outputs)\.tf$"), 55, "Terraform interface"),
]


def important_files(paths: list[str], limit: int = 12) -> list[dict[str, str]]:
    """Score and rank a few *distinct* entry points, each with a plain reason.

    "Where to start reading" must be a short, varied list — not ten copies of the
    same file. Infra repos have hundreds of identically-named files (e.g.
    ``terragrunt.hcl`` in every directory); we keep only one representative per
    filename (the shallowest, most root-like one), so the list reads as genuine
    starting points rather than a directory dump.
    """
    scored: dict[str, tuple[int, str]] = {}
    for path in paths:
        for pattern, score, reason in _IMPORTANT_FILE_RULES:
            if pattern.search(path):
                existing = scored.get(path)
                if existing is None or score > existing[0]:
                    scored[path] = (score, reason)
                break
    # Higher score first, then shallower path, then name — so the representative
    # kept for a repeated filename is the most root-level one.
    ranked = sorted(scored.items(), key=lambda item: (-item[1][0], item[0].count("/"), item[0]))
    out: list[dict[str, str]] = []
    seen_basenames: set[str] = set()
    for path, (_, reason) in ranked:
        basename = path.rsplit("/", 1)[-1].lower()
        if basename in seen_basenames:
            continue
        seen_basenames.add(basename)
        out.append({"path": path, "reason": reason})
        if len(out) >= limit:
            break
    return out


def from_source_scan(source_paths: list[str]) -> ProjectEntity | None:
    """The application entity for a codebase that has no analyzer of its own.

    Only Python is analyzed properly, so a TypeScript, Go or Java repository used to
    produce an empty graph and introduce itself as "unknown". The scan already knows
    what the code is written in — say so. Deliberately shallow (one entity, no
    modules or imports): enough for the project to have a name and a kind. A real
    analyzer per language is separate work.
    """
    language, file_count = dominant_source_language(source_paths)
    if not language or file_count < _MIN_SOURCE_FILES_FOR_APPLICATION:
        return None

    name = f"{language} application"
    return ProjectEntity(
        id=_entity_id(EntityType.APPLICATION, name),
        type=EntityType.APPLICATION,
        name=name,
        analyzer="scan",
        metadata={"language": language, "source_files": str(file_count)},
    )


def role_fact_contributions(
    *,
    sql_schema: SqlSchema | None = None,
    tests: TestFacts | None = None,
    javascript: JsFacts | None = None,
    api_surface: ApiSurface | None = None,
    ownership: OwnershipFacts | None = None,
    knowledge_base: KnowledgeBase | None = None,
) -> list[tuple[tuple[list[ProjectEntity], list[ProjectRelation], list[ProjectFinding]], str]]:
    """The facts the roles other than DevOps came for, ready to be absorbed.

    Each is skipped when the project has nothing of that kind: a repository with no
    SQL has no schema, and saying so is a truthful map — not a broken one. Kept out
    of build_project_graph so that composing the graph stays one flat, readable list
    of analyzers rather than a wall of guard clauses.
    """
    contributions = []
    if knowledge_base is not None and knowledge_base.documents:
        contributions.append((from_knowledge_base(knowledge_base), "documentation"))
    if sql_schema is not None and sql_schema.tables:
        contributions.append((from_sql_schema(sql_schema), "sql"))
    if tests is not None:
        contributions.append((from_tests(tests), "tests"))
    if javascript is not None:
        contributions.append((from_javascript(javascript), "javascript"))
    if api_surface is not None and (api_surface.endpoints or api_surface.domain_entities):
        contributions.append((from_api_surface(api_surface), "api"))
    if ownership is not None and ownership.files:
        contributions.append((from_ownership(ownership), "ownership"))
    return contributions


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
    sql_schema: SqlSchema | None = None,
    tests: TestFacts | None = None,
    javascript: JsFacts | None = None,
    api_surface: ApiSurface | None = None,
    ownership: OwnershipFacts | None = None,
    knowledge_base: KnowledgeBase | None = None,
    scan_paths: list[str] | None = None,
    source_paths: list[str] | None = None,
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

    # Terragrunt commonly owns the backend (a remote_state block in terragrunt.hcl),
    # so a Terraform stack with no `backend` block in .tf is expected, not a problem.
    # Reflect reality: mark Terraform's remote state as managed and drop the false
    # "no backend block" finding so it doesn't read as a risk.
    if terragrunt is not None and getattr(terragrunt, "has_remote_state", False):
        tf_id = _entity_id(EntityType.INFRA_COMPONENT, "terraform")
        tf = entities.get(tf_id)
        if tf is not None:
            entities[tf_id] = replace(
                tf,
                metadata={**tf.metadata, "remote_state": "True", "remote_state_via": "Terragrunt"},
            )
        findings = [f for f in findings if f.id != "terraform:terraform_backend_missing"]
    elif terragrunt is not None:
        # Terragrunt is here but we did not see its remote_state — most likely because
        # it lives in a parent terragrunt.hcl we did not read. "No backend block found"
        # then reads as a hole in the setup, when the truth is that Terragrunt generates
        # those blocks. Say what we actually know, and where to look.
        findings = [
            (
                replace(
                    finding,
                    severity=Severity.LOW,
                    title="Terraform has no backend block of its own",
                    explanation=(
                        "Terragrunt is in use here, and it generates the backend block for "
                        "each stack — so its absence from the .tf files is expected, not a "
                        "gap. Worth confirming once: the remote_state block in terragrunt.hcl "
                        "is where the state actually lives."
                    ),
                )
                if finding.id == "terraform:terraform_backend_missing"
                else finding
            )
            for finding in findings
        ]

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
    for triple, analyzer in role_fact_contributions(
        sql_schema=sql_schema,
        tests=tests,
        javascript=javascript,
        api_surface=api_surface,
        ownership=ownership,
        knowledge_base=knowledge_base,
    ):
        absorb(triple, analyzer)

    source_application = from_source_scan(source_paths or [])
    if source_application is not None:
        entities.setdefault(source_application.id, source_application)
        analyzers_run.append("source_scan")

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

    graph = ProjectGraph(
        workspace_id=workspace_id,
        entities=list(entities.values()),
        relations=list(relations.values()),
        findings=findings,
        analyzers_run=analyzers_run,
        analyzers_skipped=list(analyzers_skipped or []),
    )
    return replace(graph, findings=_tempered_by_project_kind(graph))


def _tempered_by_project_kind(graph: ProjectGraph) -> list[ProjectFinding]:
    """How loudly a fact is stated depends on what kind of project it is stated about.

    "No test files were found", in red, on an infrastructure monorepo: true, and wrong
    in tone. There is no application here to unit-test; the absence is a thing to be
    aware of, not a defect to answer for. The fact does not change — only how hard it
    knocks.
    """
    from app.core.domain.project_type import KIND_INFRASTRUCTURE, classify_project

    if classify_project(graph).kind != KIND_INFRASTRUCTURE:
        return list(graph.findings)
    return [
        (
            replace(
                finding,
                severity=Severity.INFO,
                explanation=(
                    "This is an infrastructure project, so there may be nothing here to "
                    "unit-test — the checks that matter are usually plan/validate in CI. "
                    "Worth knowing rather than worth fixing."
                ),
            )
            if finding.id == "tests:no_tests_found"
            else finding
        )
        for finding in graph.findings
    ]
