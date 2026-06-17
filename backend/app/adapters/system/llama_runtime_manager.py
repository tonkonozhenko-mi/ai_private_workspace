"""Orchestrate the local llama.cpp runtime: one ``llama-server`` for answers and
one (``--embedding``) for search, started from the bundled binary against the
downloaded GGUF models.

Everything degrades gracefully: if the binary is not bundled (e.g. a local
Ollama-only build) or the models are not downloaded yet, ``start`` raises a
clear error and the app stays on Ollama. Nothing here runs unless the user picks
the llama.cpp backend.
"""

import threading

from app.adapters.system.llama_server_process_manager import LlamaServerProcessManager
from app.config.settings import resolve_llama_server_binary_path
from app.core.domain.gguf_catalog import default_gguf_embedding, default_gguf_llm
from app.core.use_cases.download_gguf_model import DownloadGgufModelUseCase


class LlamaRuntimeError(RuntimeError):
    pass


class LlamaRuntimeManager:
    def __init__(
        self,
        download_use_case: DownloadGgufModelUseCase,
        host: str = "127.0.0.1",
        llm_port: int = 8080,
        embed_port: int = 8081,
    ) -> None:
        self._dl = download_use_case
        self._host = host
        self._llm_port = llm_port
        self._embed_port = embed_port
        self._llm: LlamaServerProcessManager | None = None
        self._embed: LlamaServerProcessManager | None = None
        self._lock = threading.Lock()

    def _running(self) -> bool:
        return (
            self._llm is not None
            and self._llm.is_running()
            and self._embed is not None
            and self._embed.is_running()
        )

    def status(self) -> dict:
        binary = resolve_llama_server_binary_path()
        llm_model = default_gguf_llm()
        embed_model = default_gguf_embedding()
        running = self._running()
        return {
            "binary_available": binary is not None,
            "binary_path": str(binary) if binary is not None else None,
            "models_ready": self._dl.is_installed(llm_model)
            and self._dl.is_installed(embed_model),
            "running": running,
            "llm_url": f"http://{self._host}:{self._llm_port}" if running else None,
            "embed_url": f"http://{self._host}:{self._embed_port}" if running else None,
        }

    def start(self) -> dict:
        binary = resolve_llama_server_binary_path()
        if binary is None:
            raise LlamaRuntimeError(
                "The llama.cpp engine is not bundled in this build yet. "
                "Run scripts/fetch_llama_server.sh or use a packaged release."
            )
        llm_model = default_gguf_llm()
        embed_model = default_gguf_embedding()
        if not self._dl.is_installed(llm_model):
            raise LlamaRuntimeError("The answer model has not been downloaded yet.")
        if not self._dl.is_installed(embed_model):
            raise LlamaRuntimeError("The search model has not been downloaded yet.")

        with self._lock:
            if self._running():
                return self.status()
            self._llm = LlamaServerProcessManager(binary, host=self._host)
            self._llm.start(self._dl.destination_path(llm_model), self._llm_port)
            self._embed = LlamaServerProcessManager(binary, host=self._host)
            self._embed.start(
                self._dl.destination_path(embed_model), self._embed_port, embedding=True
            )
        return self.status()

    def stop(self) -> dict:
        with self._lock:
            if self._llm is not None:
                self._llm.stop()
            if self._embed is not None:
                self._embed.stop()
        return self.status()
