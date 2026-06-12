from typing import Protocol

from app.core.domain.project_scan import ProjectScanResult


class ProjectScanRepositoryPort(Protocol):
    def save_latest_scan(self, workspace_id: str, scan_result: ProjectScanResult) -> None:
        """Persist the latest project scan result for a workspace."""

    def get_latest_scan(self, workspace_id: str) -> ProjectScanResult | None:
        """Return the latest project scan result for a workspace, if it exists."""
