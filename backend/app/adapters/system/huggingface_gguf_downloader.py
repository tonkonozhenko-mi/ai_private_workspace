"""Stream a GGUF model file from a URL (e.g. Hugging Face) to local disk.

Safe-by-construction: the file is written to a ``.part`` temp path and only
atomically renamed into place once the full download completes, so a cancel,
crash, or network drop never leaves a truncated model that looks installed.
"""

from collections.abc import Callable
from pathlib import Path

import httpx

from app.core.ports.gguf_downloader import (
    GgufDownloadCancelledError,
    GgufDownloadError,
)

_CHUNK_BYTES = 1024 * 1024  # 1 MiB


class HuggingFaceGgufDownloader:
    def __init__(self, timeout_seconds: int = 60, client: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self._client = client

    def download(
        self,
        url: str,
        destination_path: str,
        expected_size_bytes: int | None = None,
        progress_callback: Callable[[int, int | None], None] | None = None,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> str:
        destination = Path(destination_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        part_path = destination.with_suffix(destination.suffix + ".part")

        client = self._client or httpx.Client(follow_redirects=True)
        owns_client = self._client is None
        downloaded = 0
        try:
            with client.stream("GET", url, timeout=self.timeout_seconds) as response:
                if response.status_code >= 400:
                    raise GgufDownloadError(
                        f"Download failed with HTTP {response.status_code} for {url}"
                    )
                total = _content_length(response) or expected_size_bytes
                with open(part_path, "wb") as handle:
                    for chunk in response.iter_bytes(_CHUNK_BYTES):
                        if cancellation_check is not None and cancellation_check():
                            raise GgufDownloadCancelledError("Model download cancelled")
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback is not None:
                            progress_callback(downloaded, total)
        except (GgufDownloadCancelledError, GgufDownloadError):
            _safe_unlink(part_path)
            raise
        except httpx.HTTPError as exc:
            _safe_unlink(part_path)
            raise GgufDownloadError(f"Network error downloading {url}: {exc}") from exc
        finally:
            if owns_client:
                client.close()

        # Atomic publish: only a fully-downloaded file ever appears at the path.
        part_path.replace(destination)
        return str(destination)


def _content_length(response: "httpx.Response") -> int | None:
    raw = response.headers.get("content-length")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
