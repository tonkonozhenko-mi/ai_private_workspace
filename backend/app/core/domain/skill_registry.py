from app.core.domain.project_scan import ProjectFile
from app.core.domain.skill import SkillCategory, SkillDefinition, SkillMatch

CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


class SkillRegistry:
    def __init__(self, definitions: list[SkillDefinition] | None = None) -> None:
        self.definitions = definitions or DEFAULT_SKILL_DEFINITIONS

    def detect_skills(self, files: list[ProjectFile]) -> list[SkillMatch]:
        matches: dict[str, SkillMatch] = {}

        for project_file in files:
            file_signals = self._file_signals(project_file)

            for definition in self.definitions:
                confidence = self._confidence_for(definition, file_signals)
                if confidence is None:
                    continue

                self._record_match(matches, definition, confidence, project_file.path)

        return [
            matches[definition.name]
            for definition in self.definitions
            if definition.name in matches
        ]

    @staticmethod
    def _file_signals(project_file: ProjectFile) -> set[str]:
        signals = {project_file.detected_type}

        if project_file.extension in {".yml", ".yaml"}:
            signals.add("yaml")
        if project_file.extension == ".json":
            signals.add("json")

        return signals

    @staticmethod
    def _confidence_for(
        definition: SkillDefinition,
        file_signals: set[str],
    ) -> str | None:
        if definition.high_confidence_file_types or definition.medium_confidence_file_types:
            high_confidence_file_types = definition.high_confidence_file_types
        else:
            high_confidence_file_types = definition.file_types
        medium_confidence_file_types = definition.medium_confidence_file_types

        if file_signals.intersection(high_confidence_file_types):
            return "high"
        if file_signals.intersection(medium_confidence_file_types):
            return "medium"
        if file_signals.intersection(definition.file_types):
            return "low"

        return None

    @staticmethod
    def _record_match(
        matches: dict[str, SkillMatch],
        definition: SkillDefinition,
        confidence: str,
        evidence: str,
    ) -> None:
        existing_match = matches.get(definition.name)
        if existing_match is None:
            matches[definition.name] = SkillMatch(
                name=definition.name,
                category=definition.category,
                confidence=confidence,
                evidence=[evidence],
            )
            return

        evidence_items = existing_match.evidence
        if evidence not in evidence_items and len(evidence_items) < definition.evidence_limit:
            evidence_items = [*evidence_items, evidence]

        if CONFIDENCE_ORDER[confidence] > CONFIDENCE_ORDER[existing_match.confidence]:
            matches[definition.name] = SkillMatch(
                name=definition.name,
                category=definition.category,
                confidence=confidence,
                evidence=evidence_items,
            )
            return

        matches[definition.name] = SkillMatch(
            name=existing_match.name,
            category=existing_match.category,
            confidence=existing_match.confidence,
            evidence=evidence_items,
        )


DEFAULT_SKILL_DEFINITIONS = [
    SkillDefinition(
        name="Terraform",
        category=SkillCategory.DEVOPS.value,
        description="Infrastructure as code using Terraform.",
        file_types=["terraform"],
    ),
    SkillDefinition(
        name="Terragrunt",
        category=SkillCategory.DEVOPS.value,
        description="Terragrunt configuration for Terraform orchestration.",
        file_types=["terragrunt"],
    ),
    SkillDefinition(
        name="Python",
        category=SkillCategory.DEVELOPER.value,
        description="Python application or scripting code.",
        file_types=["python"],
    ),
    SkillDefinition(
        name="Docker",
        category=SkillCategory.DEVOPS.value,
        description="Container images or Docker-based workflows.",
        file_types=["docker"],
    ),
    SkillDefinition(
        name="Helm",
        category=SkillCategory.DEVOPS.value,
        description="Helm charts for Kubernetes package management.",
        file_types=["helm"],
    ),
    SkillDefinition(
        name="Kubernetes",
        category=SkillCategory.DEVOPS.value,
        description="Kubernetes manifests and deployment configuration.",
        file_types=["kubernetes"],
    ),
    SkillDefinition(
        name="GitLab CI",
        category=SkillCategory.DEVOPS.value,
        description="GitLab CI/CD pipeline configuration.",
        file_types=["gitlab_ci"],
    ),
    SkillDefinition(
        name="GitHub Actions",
        category=SkillCategory.DEVOPS.value,
        description="GitHub Actions workflow configuration.",
        file_types=["github_actions"],
    ),
    SkillDefinition(
        name="Documentation",
        category=SkillCategory.DOCUMENTATION.value,
        description="Markdown documentation.",
        file_types=["markdown"],
    ),
    SkillDefinition(
        name="YAML/Configuration",
        category=SkillCategory.GENERAL.value,
        description="Generic YAML configuration files.",
        file_types=["yaml"],
        high_confidence_file_types=[],
        medium_confidence_file_types=["yaml"],
    ),
    SkillDefinition(
        name="Shell scripts",
        category=SkillCategory.DEVOPS.value,
        description="Shell scripts and command automation.",
        file_types=["shell"],
    ),
    SkillDefinition(
        name="JSON/Configuration",
        category=SkillCategory.GENERAL.value,
        description="Generic JSON configuration files.",
        file_types=["json"],
        high_confidence_file_types=[],
        medium_confidence_file_types=["json"],
    ),
]
