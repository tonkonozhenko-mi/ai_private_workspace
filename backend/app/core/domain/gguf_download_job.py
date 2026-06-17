from dataclasses import dataclass, field, replace
from datetime import UTC, datetime


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class GgufDownloadJob:
    """Tracks one background GGUF model download (LLM or embedding).

    Statuses: ``queued`` → ``running`` → ``succeeded`` | ``failed`` |
    ``cancelled``. Progress is reported in bytes; ``total_bytes`` may be ``None``
    until the server reports a content length.
    """

    id: str
    model_id: str
    name: str
    model_type: str  # "llm" | "embedding"
    status: str = "queued"
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    error: str | None = None
    destination_path: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @property
    def progress_percent(self) -> int | None:
        if not self.total_bytes:
            return None
        return max(0, min(100, round(self.downloaded_bytes / self.total_bytes * 100)))

    @property
    def is_terminal(self) -> bool:
        return self.status in {"succeeded", "failed", "cancelled"}

    def with_progress(self, downloaded: int, total: int | None) -> "GgufDownloadJob":
        return replace(
            self,
            status="running",
            downloaded_bytes=downloaded,
            total_bytes=total if total is not None else self.total_bytes,
            updated_at=_now(),
        )

    def succeeded(self, destination_path: str) -> "GgufDownloadJob":
        return replace(
            self,
            status="succeeded",
            destination_path=destination_path,
            updated_at=_now(),
        )

    def failed(self, error: str) -> "GgufDownloadJob":
        return replace(self, status="failed", error=error, updated_at=_now())

    def cancelled(self) -> "GgufDownloadJob":
        return replace(self, status="cancelled", updated_at=_now())
