from dataclasses import dataclass


@dataclass(frozen=True)
class ReportSection:
    title: str
    content: str
    bullets: list[str]


@dataclass(frozen=True)
class ProjectOverviewReport:
    workspace_id: str
    title: str
    summary: str
    sections: list[ReportSection]
    generated_from: list[str]
