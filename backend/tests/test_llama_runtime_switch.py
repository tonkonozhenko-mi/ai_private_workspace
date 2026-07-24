"""Switching the answer model is atomic and honest (0.7.7 beta blocker).

The live failure: "Use this model" stopped the engine and left it down; a manual
"Start engine" then revived a *different* model, while the setup card showed the
one that was picked. Three sources disagreed. These tests pin the contract:

* a successful switch reports the model the process is actually running;
* a switch whose new process fails to start rolls back to the previous model
  (engine stays up) and raises a worded error — never a silent stop/fallback;
* while stopped, status reports no running model (the saved ref is intent, not
  fact);
* "Use this model" on a stopped engine brings the whole engine up on that model.

The process/binary layers are faked, so no real llama-server is needed.
"""

from pathlib import Path

import pytest

import app.adapters.system.llama_runtime_manager as mod
from app.adapters.system.llama_runtime_manager import LlamaRuntimeError, LlamaRuntimeManager
from app.adapters.system.llama_server_process_manager import LlamaServerStartError
from app.core.use_cases.download_gguf_model import GgufModelRef


class _FakeProc:
    """Stand-in for a llama-server process manager: always healthy once made."""

    def __init__(self) -> None:
        self._alive = True
        self.pid = 4321

    def is_running(self) -> bool:
        return self._alive

    def stop(self) -> None:
        self._alive = False


class _FakeDownload:
    """Every model is 'installed' and maps to a throwaway path."""

    app_data_dir = Path("/tmp/does-not-matter")

    def is_installed(self, model) -> bool:  # noqa: ANN001
        return True

    def destination_path(self, model):  # noqa: ANN001
        return Path(f"/tmp/{model.id.replace('/', '__')}.gguf")


@pytest.fixture
def manager(monkeypatch):
    mgr = LlamaRuntimeManager(_FakeDownload())  # type: ignore[arg-type]
    monkeypatch.setattr(mod, "resolve_llama_server_binary_path", lambda: Path("/bin/llama-server"))
    monkeypatch.setattr(mod, "_reap_llama_server_on_port", lambda *a, **k: None)
    # The embedding side is not under test — pretend it comes up.
    monkeypatch.setattr(
        mgr,
        "_ensure_embed_running",
        lambda binary: setattr(mgr, "_embed", _FakeProc()),
    )
    return mgr, monkeypatch


def _fake_starter(bad_ids: set[str]):
    def _start(binary, model):  # noqa: ANN001
        if model.id in bad_ids:
            raise LlamaServerStartError(f"{model.id} won't load")
        return _FakeProc()

    return _start


def test_successful_switch_reports_the_running_model(manager):
    mgr, monkeypatch = manager
    mgr._embed = _FakeProc()  # engine already running
    monkeypatch.setattr(mgr, "_start_llm_server", _fake_starter(bad_ids=set()))

    status = mgr.switch_llm(GgufModelRef(model_id="llama3.2"))

    assert status["running"] is True
    assert status["active_llm_model"] == "llama3.2"
    assert mgr._llm_running_model is not None and mgr._llm_running_model.id == "llama3.2"


def test_failed_switch_rolls_back_and_raises_a_worded_error(manager):
    mgr, monkeypatch = manager
    mgr._embed = _FakeProc()
    # Come up cleanly on llama3.2 first.
    monkeypatch.setattr(mgr, "_start_llm_server", _fake_starter(bad_ids=set()))
    mgr.switch_llm(GgufModelRef(model_id="llama3.2"))

    # Now qwen3-4b refuses to start; the previous model must come back.
    monkeypatch.setattr(mgr, "_start_llm_server", _fake_starter(bad_ids={"qwen3-4b"}))
    with pytest.raises(LlamaRuntimeError) as excinfo:
        mgr.switch_llm(GgufModelRef(model_id="qwen3-4b"))
    assert "Could not start" in str(excinfo.value)

    status = mgr.status()
    assert status["running"] is True  # engine not left down
    assert status["active_llm_model"] == "llama3.2"  # the working model, not the failed one


def test_stopped_engine_reports_no_running_model(manager):
    mgr, monkeypatch = manager
    mgr._embed = _FakeProc()
    monkeypatch.setattr(mgr, "_start_llm_server", _fake_starter(bad_ids=set()))
    mgr.switch_llm(GgufModelRef(model_id="llama3.2"))

    mgr.stop()

    assert mgr._llm_running_model is None
    assert mgr.status()["running"] is False


def test_use_this_model_on_a_stopped_engine_brings_it_up(manager):
    mgr, monkeypatch = manager
    # Engine fully stopped: no processes.
    monkeypatch.setattr(mgr, "_start_llm_server", _fake_starter(bad_ids=set()))

    status = mgr.switch_llm(GgufModelRef(model_id="llama3.2"))

    assert status["running"] is True
    assert status["active_llm_model"] == "llama3.2"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
