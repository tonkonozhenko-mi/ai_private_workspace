from collections.abc import Callable
from typing import Protocol


class GgufDownloadError(RuntimeError):
    pass


class GgufDownloadCancelledError(RuntimeError):
    pass


class GgufDownloaderPort(Protocol):
    def download(
        self,
        url: str,
        destination_path: str,
        expected_size_bytes: int | None = None,
        progress_callback: Callable[[int, int | None], None] | None = None,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> str:
        """Download ``url`` to ``destination_path`` and return the final path.

        Implementations stream to a temporary file and atomically move it into
        place on success, so a cancelled or failed download never leaves a
        half-written model file. ``progress_callback`` receives
        ``(bytes_done, total_bytes_or_None)``.
        """
