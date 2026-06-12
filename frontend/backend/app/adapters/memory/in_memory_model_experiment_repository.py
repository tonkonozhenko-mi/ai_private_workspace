from app.core.domain.model_experiment_run import ModelExperimentRun


class InMemoryModelExperimentRepository:
    def __init__(self) -> None:
        self._runs: dict[str, ModelExperimentRun] = {}

    def save(self, run: ModelExperimentRun) -> ModelExperimentRun:
        self._runs[run.id] = run
        return run

    def get(self, run_id: str) -> ModelExperimentRun | None:
        return self._runs.get(run_id)

    def list_by_workspace(
        self,
        workspace_id: str,
        limit: int = 20,
    ) -> list[ModelExperimentRun]:
        runs = sorted(
            (
                run
                for run in self._runs.values()
                if run.workspace_id == workspace_id
            ),
            key=lambda run: (run.created_at, run.id),
            reverse=True,
        )
        return runs[: max(0, limit)]
