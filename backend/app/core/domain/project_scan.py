from dataclasses import dataclass, field

from app.core.domain.skill import SkillMatch


@dataclass(frozen=True)
class ProjectFile:
    path: str
    extension: str | None
    size_bytes: int
    detected_type: str
    modified_at: float | None = None


DetectedSkill = SkillMatch


@dataclass(frozen=True)
class ProjectScanResult:
    project_path: str
    total_files: int
    scanned_files: int
    skipped_files: int
    total_size_bytes: int
    detected_skills: list[SkillMatch]
    files: list[ProjectFile]
    # Files the walk found and the DEFAULT rules cut before anything looked at
    # them. Not indexed, not counted in `scanned_files`, not part of `files` —
    # they exist only so the app can admit they were never read.
    #
    # The distinction they carry is the whole point. A file the person excluded
    # is "not asked for", and we say nothing about it. A file cut by rules they
    # never wrote is "not seen", and saying nothing about that is how a repo can
    # be scanned, indexed and answering questions with its infrastructure
    # entirely invisible. Empty when the person authored their own rules.
    unseen_files: list[ProjectFile] = field(default_factory=list)


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
