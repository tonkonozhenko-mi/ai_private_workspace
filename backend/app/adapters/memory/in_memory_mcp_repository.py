from app.core.domain.mcp_server import WorkspaceMCPServerConfig


class InMemoryMCPRepository:
    def __init__(self) -> None:
        self._configs: dict[tuple[str, str], WorkspaceMCPServerConfig] = {}

    def save_config(self, config: WorkspaceMCPServerConfig) -> WorkspaceMCPServerConfig:
        self._configs[(config.workspace_id, config.id)] = config
        return config

    def get_config(self, workspace_id: str, config_id: str) -> WorkspaceMCPServerConfig | None:
        return self._configs.get((workspace_id, config_id))

    def list_configs(self, workspace_id: str) -> list[WorkspaceMCPServerConfig]:
        configs = [
            config
            for (stored_workspace_id, _), config in self._configs.items()
            if stored_workspace_id == workspace_id
        ]
        return sorted(configs, key=lambda item: item.updated_at, reverse=True)

    def delete_config(self, workspace_id: str, config_id: str) -> bool:
        return self._configs.pop((workspace_id, config_id), None) is not None
