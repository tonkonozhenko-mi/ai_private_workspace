"""A dropped download keeps what it already fetched.

Reported from the beta: large models "just stop". Not reproduced on demand —
these are multi-gigabyte files over a domestic link, and the failure is the
link, not the app. But the app's response to it was the problem. Every failure
deleted the ``.part`` file, so a blip at minute forty threw away forty minutes
and the next attempt started at zero. On a connection that drops regularly that
is a download which can never finish, however many times you press the button.

The bytes now stay, and the next attempt sends a Range header to continue from
them. Cancelling still deletes: that is a decision, not an interruption.

Two things must not be traded away for that convenience. The atomic publish —
only a whole file ever appears at the final path — and the refusal to append to
bytes that came from a different file, which would produce a corrupt model that
looks perfectly installed.
"""

import httpx
import pytest

from app.adapters.system.huggingface_gguf_downloader import HuggingFaceGgufDownloader
from app.core.ports.gguf_downloader import (
    GgufDownloadCancelledError,
    GgufDownloadError,
)

WHOLE = b"GGUF" + bytes(range(60))  # 64 bytes standing in for a multi-GB model


def _server(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def _range_start(request: httpx.Request) -> int:
    header = request.headers.get("range")
    if not header:
        return 0
    return int(header.removeprefix("bytes=").partition("-")[0])


def _serves_the_whole_file(request: httpx.Request) -> httpx.Response:
    start = _range_start(request)
    if start:
        return httpx.Response(
            206,
            content=WHOLE[start:],
            headers={"content-range": f"bytes {start}-{len(WHOLE) - 1}/{len(WHOLE)}"},
        )
    return httpx.Response(200, content=WHOLE, headers={"content-length": str(len(WHOLE))})


def test_a_second_attempt_continues_from_the_bytes_already_on_disk(tmp_path):
    destination = tmp_path / "model.gguf"
    part = tmp_path / "model.gguf.part"
    part.write_bytes(WHOLE[:40])  # what the dropped attempt left behind
    asked_for: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked_for.append(request.headers.get("range"))
        return _serves_the_whole_file(request)

    downloader = HuggingFaceGgufDownloader(client=_server(handler))
    result = downloader.download(
        url="https://example.invalid/model.gguf",
        destination_path=str(destination),
        expected_size_bytes=len(WHOLE),
    )

    assert asked_for == ["bytes=40-"]  # only the tail was fetched
    assert destination.read_bytes() == WHOLE
    assert not part.exists()
    assert result == str(destination)


def test_progress_counts_the_resumed_bytes_too(tmp_path):
    """Otherwise a resume shows a bar that restarts at 0% and finishes early —
    the same download reported two different ways depending on how it began."""
    part = tmp_path / "model.gguf.part"
    part.write_bytes(WHOLE[:40])
    seen: list[tuple[int, int | None]] = []

    HuggingFaceGgufDownloader(client=_server(_serves_the_whole_file)).download(
        url="https://example.invalid/model.gguf",
        destination_path=str(tmp_path / "model.gguf"),
        expected_size_bytes=len(WHOLE),
        progress_callback=lambda done, total: seen.append((done, total)),
    )

    assert seen[-1] == (len(WHOLE), len(WHOLE))
    assert all(done > 40 for done, _ in seen)


def test_a_network_drop_keeps_what_was_downloaded(tmp_path):
    destination = tmp_path / "model.gguf"
    part = tmp_path / "model.gguf.part"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("connection dropped", request=request)

    part.write_bytes(WHOLE[:40])
    with pytest.raises(GgufDownloadError) as failure:
        HuggingFaceGgufDownloader(client=_server(handler)).download(
            url="https://example.invalid/model.gguf",
            destination_path=str(destination),
            expected_size_bytes=len(WHOLE),
        )

    assert part.exists(), "the partial download was thrown away again"
    assert part.read_bytes() == WHOLE[:40]
    assert not destination.exists()
    # And it says so, rather than leaving the person guessing what to do next.
    assert "continue from where it stopped" in str(failure.value)


def test_cancelling_throws_the_partial_file_away(tmp_path):
    part = tmp_path / "model.gguf.part"

    with pytest.raises(GgufDownloadCancelledError):
        HuggingFaceGgufDownloader(client=_server(_serves_the_whole_file)).download(
            url="https://example.invalid/model.gguf",
            destination_path=str(tmp_path / "model.gguf"),
            expected_size_bytes=len(WHOLE),
            cancellation_check=lambda: True,
        )

    assert not part.exists()


def test_leftovers_from_a_different_file_are_never_appended_to(tmp_path):
    """The hazard resuming introduces, and the one that must not be shipped.

    A ``.part`` left by an older revision of the same filename would be appended
    to and then atomically published — a corrupt model that passes every check
    the app makes, because the app only checks that the file is there and big
    enough."""
    part = tmp_path / "model.gguf.part"
    part.write_bytes(b"bytes from some other build")

    def handler(request: httpx.Request) -> httpx.Response:
        start = _range_start(request)
        # The server's file is a different size from the one those bytes belong to.
        return httpx.Response(
            206,
            content=WHOLE[start:],
            headers={"content-range": f"bytes {start}-{len(WHOLE) - 1}/{len(WHOLE) + 5000}"},
        )

    with pytest.raises(GgufDownloadError) as failure:
        HuggingFaceGgufDownloader(client=_server(handler)).download(
            url="https://example.invalid/model.gguf",
            destination_path=str(tmp_path / "model.gguf"),
            expected_size_bytes=len(WHOLE),
        )

    assert not part.exists()
    assert not (tmp_path / "model.gguf").exists()
    assert "start the download again" in str(failure.value)


def test_a_server_that_ignores_range_simply_starts_over(tmp_path):
    """Not every host honours Range. Answering 200 with the whole file is a
    legitimate reply to it, and the result must still be a correct file — not
    the tail appended to the head."""
    destination = tmp_path / "model.gguf"
    (tmp_path / "model.gguf.part").write_bytes(WHOLE[:40])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=WHOLE, headers={"content-length": str(len(WHOLE))})

    seen: list[tuple[int, int | None]] = []
    HuggingFaceGgufDownloader(client=_server(handler)).download(
        url="https://example.invalid/model.gguf",
        destination_path=str(destination),
        expected_size_bytes=len(WHOLE),
        progress_callback=lambda done, total: seen.append((done, total)),
    )

    assert destination.read_bytes() == WHOLE
    assert seen[-1] == (len(WHOLE), len(WHOLE))


def test_without_a_known_size_nothing_is_resumed(tmp_path):
    """No expected size means no way to tell a resumable tail from a stale file,
    so the honest move is to fetch it again."""
    (tmp_path / "model.gguf.part").write_bytes(WHOLE[:40])
    asked_for: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked_for.append(request.headers.get("range"))
        return httpx.Response(200, content=WHOLE, headers={"content-length": str(len(WHOLE))})

    HuggingFaceGgufDownloader(client=_server(handler)).download(
        url="https://example.invalid/model.gguf",
        destination_path=str(tmp_path / "model.gguf"),
        expected_size_bytes=None,
    )

    assert asked_for == [None]
    assert (tmp_path / "model.gguf").read_bytes() == WHOLE


def test_a_partial_file_never_appears_at_the_final_path(tmp_path):
    """The invariant resuming must not cost: what is at the destination is a
    whole model or nothing."""
    destination = tmp_path / "model.gguf"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"upstream is having a day")

    with pytest.raises(GgufDownloadError):
        HuggingFaceGgufDownloader(client=_server(handler)).download(
            url="https://example.invalid/model.gguf",
            destination_path=str(destination),
            expected_size_bytes=len(WHOLE),
        )

    assert not destination.exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
