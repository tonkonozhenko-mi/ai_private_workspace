from typing import Protocol


class AppPreferencesRepositoryPort(Protocol):
    """Stores the app-level user preferences as one opaque JSON blob.

    Global (one per install), not workspace-scoped. The backend treats the
    contents as opaque so the frontend preference shape can evolve without a
    backend schema change.
    """

    def get(self) -> dict | None:
        """Return the stored preferences, or None if nothing was ever saved."""

    def save(self, values: dict) -> dict:
        """Persist (replace) the preferences blob and return what was stored."""
