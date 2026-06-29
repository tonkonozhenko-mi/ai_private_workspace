"""Read and update the app-level user preferences (one global JSON blob)."""

from app.core.ports.app_preferences_repository import AppPreferencesRepositoryPort


class AppPreferencesValidationError(ValueError):
    pass


class ManageAppPreferencesUseCase:
    def __init__(self, repository: AppPreferencesRepositoryPort) -> None:
        self.repository = repository

    def get(self) -> dict:
        return self.repository.get() or {}

    def update(self, patch: dict) -> dict:
        """Shallow-merge ``patch`` into the stored preferences and persist.

        The frontend sends the full preferences object on each change, so this
        is effectively a replace; the merge keeps any keys the client omits.
        """
        if not isinstance(patch, dict):
            raise AppPreferencesValidationError("Preferences must be an object")
        current = self.repository.get() or {}
        merged = {**current, **patch}
        return self.repository.save(merged)
