"""Tiny on-disk store for runtime choices that must survive a backend restart.

Currently it remembers which embedding/answer engine the user activated
("ollama" or "llamacpp"). Without this, the in-memory active backend resets to
the env default on every restart, so an index built with llama.cpp embeddings
would silently be searched with Ollama embeddings (or vice-versa). Persisting the
choice lets the app re-activate the same engine on startup and keep index and
search on the same vectorizer.
"""

import json
import threading
from pathlib import Path

_VALID_BACKENDS = {"ollama", "llamacpp"}


class RuntimeStateStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def get_active_backend(self) -> str | None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        value = data.get("active_backend") if isinstance(data, dict) else None
        return value if value in _VALID_BACKENDS else None

    def set_active_backend(self, backend: str) -> None:
        backend = backend.strip().lower()
        if backend not in _VALID_BACKENDS:
            return
        self._update("active_backend", backend)

    def get_llamacpp_llm_model(self) -> str | None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        value = data.get("llamacpp_llm_model") if isinstance(data, dict) else None
        return value if isinstance(value, str) and value else None

    def set_llamacpp_llm_model(self, model_id: str) -> None:
        model_id = (model_id or "").strip()
        if model_id:
            self._update("llamacpp_llm_model", model_id)

    def _update(self, key: str, value: str) -> None:
        with self._lock:
            data: dict = {}
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, ValueError):
                data = {}
            data[key] = value
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            tmp.replace(self._path)
