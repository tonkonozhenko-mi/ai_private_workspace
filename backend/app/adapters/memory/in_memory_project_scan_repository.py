from app.core.domain.project_scan import ProjectScanResult


class InMemoryProjectScanRepository:
    def __init__(self) -> None:
        self._latest_scans: dict[str, ProjectScanResult] = {}

    def save_latest_scan(self, workspace_id: str, scan_result: ProjectScanResult) -> None:
        self._latest_scans[workspace_id] = scan_result

    def get_latest_scan(self, workspace_id: str) -> ProjectScanResult | None:
        return self._latest_scans.get(workspace_id)
