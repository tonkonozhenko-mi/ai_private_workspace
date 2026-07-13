"""The machine has the last word.

The arithmetic says a window is affordable; llama-server, holding the actual
memory, may disagree. When it refuses to come up, the window halves and we try
again — down to the 8192 that has always worked — and each step says why.
"""

import app.adapters.system.llama_runtime_manager as runtime
from app.adapters.system.llama_server_process_manager import LlamaServerStartError
from app.core.domain.context_window_choice import MIN_CONTEXT
from app.core.domain.gguf_catalog import default_gguf_llm


class _FussyServer:
    """Starts only when the window is at or below ``accepts``."""

    started: list[int] = []

    def __init__(self, binary, host="127.0.0.1", context_size=4096) -> None:
        self.context_size = context_size
        self.stopped = False

    def start(self, model_path, port, embedding=False, reranking=False):
        _FussyServer.started.append(self.context_size)
        if self.context_size > _FussyServer.accepts:
            raise LlamaServerStartError(f"failed to allocate KV cache for {self.context_size}")
        return f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        self.stopped = True


class _Downloads:
    """Every model is "installed", at a path nothing ever opens — these tests are
    about the ladder, not about reading a real GGUF."""

    def is_installed(self, model) -> bool:
        return True

    def destination_path(self, model) -> str:
        return f"{model.id}.gguf"


def _manager(monkeypatch, accepts: int, chosen: int):
    _FussyServer.started = []
    _FussyServer.accepts = accepts
    monkeypatch.setattr(runtime, "LlamaServerProcessManager", _FussyServer)
    manager = runtime.LlamaRuntimeManager(_Downloads())
    # The window is chosen from the model and the machine; here we fix it so the
    # test is about the ladder, not the arithmetic (that is tested elsewhere).
    monkeypatch.setattr(manager, "_choose_llm_context", lambda model: (chosen, 131072))
    return manager


def test_the_window_steps_down_until_the_engine_starts(monkeypatch, capsys):
    manager = _manager(monkeypatch, accepts=16384, chosen=32768)

    server = manager._start_llm_server("llama-server", default_gguf_llm())

    assert _FussyServer.started == [32768, 16384]
    assert server.context_size == 16384
    assert manager.status()["llm_context_max_tokens"] == 131072
    # The reason is in the log, so a smaller window is never a mystery.
    assert "retrying with 16,384" in capsys.readouterr().out


def test_it_stops_at_the_window_that_always_worked(monkeypatch):
    manager = _manager(monkeypatch, accepts=MIN_CONTEXT, chosen=32768)

    manager._start_llm_server("llama-server", default_gguf_llm())

    assert _FussyServer.started == [32768, 16384, MIN_CONTEXT]


def test_a_machine_that_cannot_hold_even_that_gets_an_honest_error(monkeypatch):
    manager = _manager(monkeypatch, accepts=0, chosen=8192)

    try:
        manager._start_llm_server("llama-server", default_gguf_llm())
    except runtime.LlamaRuntimeError as exc:
        assert "smallest window" in str(exc)
    else:  # pragma: no cover - the fake refuses everything
        raise AssertionError("a server that never starts must not report success")
