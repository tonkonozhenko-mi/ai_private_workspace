"""The index build must honor the workspace's chosen search engine.

Live-observed bug: onboarding recorded the workspace's embedding selection as
llamacpp, but the app-global embedding delegate was still pointed at Ollama
when "Build search context" ran. The build succeeded — into a vector space the
workspace could never search — so Models showed "NEEDS CONTEXT INDEX" right
after a successful build and Ask fell back to general conversation.

_align_embedding_backend_with_selection() is the guard: before any index
build it re-points the delegate at the workspace's selected engine, and fails
loudly (RuntimeError with a recoverable message) when that engine can't be
activated.
"""

from types import SimpleNamespace

import pytest

import app.api.routes.workspaces as workspaces_routes
from app.api.routes.workspaces import _align_embedding_backend_with_selection


class FakeDelegate:
    def __init__(self, provider_name: str, fail: bool = False) -> None:
        self.provider_name = provider_name
        self.model_name = "fake-embed"
        self.fail = fail
        self.embedded: list[str] = []

    def embed_text(self, text: str) -> list[float]:
        if self.fail:
            raise ConnectionError("engine down")
        self.embedded.append(text)
        return [0.1, 0.2]


class FakeSwitchable:
    def __init__(self, delegate: FakeDelegate) -> None:
        self._delegate = delegate

    @property
    def provider_name(self) -> str:
        return self._delegate.provider_name

    def set_delegate(self, delegate) -> None:
        self._delegate = delegate


def _selection(provider: str | None):
    if provider is None:
        return None
    return SimpleNamespace(
        selected_embedding=SimpleNamespace(provider=provider, model="nomic-embed-text")
    )


def _install(monkeypatch, *, selected_provider, active_provider, new_delegate):
    switchable = FakeSwitchable(FakeDelegate(active_provider))
    monkeypatch.setattr(workspaces_routes, "embedding_provider", switchable)
    monkeypatch.setattr(
        workspaces_routes,
        "workspace_model_selection_repository",
        SimpleNamespace(get=lambda workspace_id: _selection(selected_provider)),
    )

    import app.api.dependencies as dependencies

    monkeypatch.setattr(
        dependencies,
        "build_embedding_for_backend",
        lambda backend: new_delegate,
    )
    monkeypatch.setattr(
        dependencies,
        "runtime_state_store",
        SimpleNamespace(set_active_backend=lambda backend: None),
    )
    return switchable


def test_realigns_delegate_when_selection_disagrees(monkeypatch) -> None:
    """The live-bug scenario: workspace selected ollama, delegate on llamacpp."""
    new_delegate = FakeDelegate("ollama")
    switchable = _install(
        monkeypatch,
        selected_provider="ollama",
        active_provider="llamacpp",
        new_delegate=new_delegate,
    )

    _align_embedding_backend_with_selection("ws-1")

    assert switchable.provider_name == "ollama"
    # The new delegate was probed before being trusted.
    assert new_delegate.embedded == ["ok"]


def test_noop_when_already_aligned(monkeypatch) -> None:
    new_delegate = FakeDelegate("ollama")
    switchable = _install(
        monkeypatch,
        selected_provider="ollama",
        active_provider="ollama",
        new_delegate=new_delegate,
    )

    _align_embedding_backend_with_selection("ws-1")

    # No switch, no probe — the aligned path must not disturb a working engine.
    assert switchable.provider_name == "ollama"
    assert new_delegate.embedded == []


def test_noop_without_selection(monkeypatch) -> None:
    new_delegate = FakeDelegate("ollama")
    switchable = _install(
        monkeypatch,
        selected_provider=None,
        active_provider="llamacpp",
        new_delegate=new_delegate,
    )

    _align_embedding_backend_with_selection("ws-1")

    assert switchable.provider_name == "llamacpp"


def test_fails_loudly_when_selected_engine_is_down(monkeypatch) -> None:
    """A dead engine must stop the build with a recoverable message — not let
    it proceed and silently produce an unsearchable index."""
    new_delegate = FakeDelegate("ollama", fail=True)
    switchable = _install(
        monkeypatch,
        selected_provider="ollama",
        active_provider="llamacpp",
        new_delegate=new_delegate,
    )

    with pytest.raises(RuntimeError) as excinfo:
        _align_embedding_backend_with_selection("ws-1")

    assert "rebuild the search context" in str(excinfo.value)
    # The broken delegate must NOT have been installed.
    assert switchable.provider_name == "llamacpp"
