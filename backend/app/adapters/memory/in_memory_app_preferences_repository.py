class InMemoryAppPreferencesRepository:
    def __init__(self) -> None:
        self._values: dict | None = None

    def get(self) -> dict | None:
        return dict(self._values) if self._values is not None else None

    def save(self, values: dict) -> dict:
        self._values = dict(values)
        return dict(self._values)
