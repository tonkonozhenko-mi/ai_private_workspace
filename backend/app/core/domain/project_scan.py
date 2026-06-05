from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectFile:
    path: str
    extension: str | None
    size_bytes: int
    detected_type: str


@dataclass(frozen=True)
class DetectedSkill:
    name: str
    confidence: str
    evidence: list[str]


@dataclass(frozen=True)
class ProjectScanResult:
    project_path: str
    total_files: int
    scanned_files: int
    skipped_files: int
    total_size_bytes: int
    detected_skills: list[DetectedSkill]
    files: list[ProjectFile]


class ProjectFileList(list[ProjectFile]):
    def __init__(
        self,
        files: list[ProjectFile],
        total_files: int,
        skipped_files: int,
        total_size_bytes: int,
    ) -> None:
        super().__init__(files)
        self.total_files = total_files
        self.skipped_files = skipped_files
        self.total_size_bytes = total_size_bytes
