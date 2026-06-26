"""Unit tests for the optional llama-server performance flags (`_perf_args`).

These exercise pure argument construction; no process is spawned.
"""

from app.adapters.system.llama_server_process_manager import LlamaServerProcessManager


def _mgr(tmp_path):
    return LlamaServerProcessManager(binary_path=tmp_path / "llama-server")


def _model(tmp_path):
    p = tmp_path / "model.gguf"
    p.write_bytes(b"x")
    return p


def test_flash_attn_on_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("AI_WORKSPACE_LLAMA_FLASH_ATTN", raising=False)
    monkeypatch.delenv("AI_WORKSPACE_LLAMA_PARALLEL", raising=False)
    args = _mgr(tmp_path)._perf_args(_model(tmp_path))
    assert "-fa" in args
    assert "--slot-save-path" in args
    # GPU offload is intentionally never used (skipped for Windows safety).
    assert "-ngl" not in args


def test_flash_attn_opt_out(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WORKSPACE_LLAMA_FLASH_ATTN", "0")
    assert "-fa" not in _mgr(tmp_path)._perf_args(_model(tmp_path))


def test_parallel_default_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("AI_WORKSPACE_LLAMA_PARALLEL", raising=False)
    assert "--parallel" not in _mgr(tmp_path)._perf_args(_model(tmp_path))


def test_parallel_opt_in(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WORKSPACE_LLAMA_PARALLEL", "3")
    args = _mgr(tmp_path)._perf_args(_model(tmp_path))
    assert "--parallel" in args
    assert "3" in args
