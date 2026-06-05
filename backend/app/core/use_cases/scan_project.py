from dataclasses import dataclass

from app.core.domain.project_scan import DetectedSkill, ProjectScanResult
from app.core.ports.file_system import FileSystemPort


CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
SKILL_ORDER = [
    "Terraform",
    "Python",
    "Docker",
    "Helm",
    "Kubernetes",
    "GitLab CI",
    "GitHub Actions",
    "Documentation",
    "YAML/Configuration",
    "Shell scripts",
]


@dataclass(frozen=True)
class ScanProjectInput:
    project_path: str


class ProjectScanError(ValueError):
    pass


class ScanProjectUseCase:
    def __init__(self, file_system: FileSystemPort) -> None:
        self.file_system = file_system

    def execute(self, request: ScanProjectInput) -> ProjectScanResult:
        if not self.file_system.path_exists(request.project_path):
            raise ProjectScanError("Project path does not exist")
        if not self.file_system.is_directory(request.project_path):
            raise ProjectScanError("Project path is not a directory")

        files = self.file_system.list_files(request.project_path)
        detected_skills = self._detect_skills(files)
        skipped_files = getattr(files, "skipped_files", 0)
        total_files = getattr(files, "total_files", len(files) + skipped_files)
        total_size_bytes = getattr(
            files,
            "total_size_bytes",
            sum(project_file.size_bytes for project_file in files),
        )

        return ProjectScanResult(
            project_path=request.project_path,
            total_files=total_files,
            scanned_files=len(files),
            skipped_files=skipped_files,
            total_size_bytes=total_size_bytes,
            detected_skills=detected_skills,
            files=list(files),
        )

    def _detect_skills(self, files) -> list[DetectedSkill]:
        skills: dict[str, DetectedSkill] = {}

        for project_file in files:
            detected_type = project_file.detected_type

            if detected_type == "terraform":
                self._record_skill(skills, "Terraform", "high", project_file.path)
            elif detected_type == "python":
                self._record_skill(skills, "Python", "high", project_file.path)
            elif detected_type == "docker":
                self._record_skill(skills, "Docker", "high", project_file.path)
            elif detected_type == "helm":
                self._record_skill(skills, "Helm", "high", project_file.path)
            elif detected_type == "kubernetes":
                self._record_skill(skills, "Kubernetes", "high", project_file.path)
            elif detected_type == "gitlab_ci":
                self._record_skill(skills, "GitLab CI", "high", project_file.path)
            elif detected_type == "github_actions":
                self._record_skill(skills, "GitHub Actions", "high", project_file.path)
            elif detected_type == "markdown":
                self._record_skill(skills, "Documentation", "high", project_file.path)
            elif detected_type == "shell":
                self._record_skill(skills, "Shell scripts", "high", project_file.path)

            if project_file.extension in {".yml", ".yaml"}:
                self._record_skill(
                    skills,
                    "YAML/Configuration",
                    "medium",
                    project_file.path,
                )

        return [skills[name] for name in SKILL_ORDER if name in skills]

    @staticmethod
    def _record_skill(
        skills: dict[str, DetectedSkill],
        name: str,
        confidence: str,
        evidence: str,
    ) -> None:
        existing_skill = skills.get(name)
        if existing_skill is None:
            skills[name] = DetectedSkill(
                name=name,
                confidence=confidence,
                evidence=[evidence],
            )
            return

        if evidence not in existing_skill.evidence:
            existing_skill.evidence.append(evidence)

        if CONFIDENCE_ORDER[confidence] > CONFIDENCE_ORDER[existing_skill.confidence]:
            skills[name] = DetectedSkill(
                name=name,
                confidence=confidence,
                evidence=existing_skill.evidence,
            )
