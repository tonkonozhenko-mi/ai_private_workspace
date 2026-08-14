"""A dropped download keeps what it already fetched.

Reported from the beta: large models "just stop". Not reproduced on demand —
these are multi-gigabyte files over a domestic link, and the failure is the
link, not the app. But the app's response to it was the problem. Every failure
deleted the ``.part`` file, so a blip at minute forty threw away forty minutes
and the next attempt started at zero. On a connection that drops regularly that
is a download which can never finish, however many times you press the button.

The first fix did not work, and these tests are why nobody noticed. They each
wrote a ``.part`` by hand and passed the *true* file size as the expected one —
a sequence that never happens. In the app the expected size comes from the
catalog, where it is a round approximation with a comment saying so, and the
server reports the exact byte count. The two never matched, so every resume was
refused and every partial file deleted. Eight green tests, and the feature was a
no-op on every model the app offers.

So these drive the interruption through the downloader itself, and the size the
caller passes is deliberately wrong wherever the real one would be.

Two things must not be traded away for the convenience. The atomic publish —
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

# The downloader reads in 1 MiB chunks, so a fixture smaller than one chunk
# never reaches the write loop at all: a drop mid-transfer loses the buffer and
# leaves an empty ``.part``, and every "it resumed" assertion becomes a test of
# the fixture instead of the code. Three chunks, dropping after one and a half.
CHUNK = 1024 * 1024
WHOLE = bytes(range(256)) * (3 * CHUNK // 256)
KEPT = CHUNK  # what survives a drop at 1.5 chunks: the last whole chunk written

# What the catalog carries: a round number, near the truth and never equal to it.
CATALOG_GUESS = 4_000_000


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


def _drops_mid_transfer():
    """A server that hands over part of the file and then the link dies."""
    byte_count = CHUNK + CHUNK // 2

    def handler(request: httpx.Request) -> httpx.Response:
        start = _range_start(request)
        if start:
            return httpx.Response(
                206,
                content=WHOLE[start:],
                headers={"content-range": f"bytes {start}-{len(WHOLE) - 1}/{len(WHOLE)}"},
            )

        def _cut_off():
            yield WHOLE[:byte_count]
            raise httpx.ReadError("connection dropped")

        return httpx.Response(
            200,
            headers={"content-length": str(len(WHOLE))},
            content=_cut_off(),
        )

    return handler


def _interrupted_download(tmp_path, downloader: HuggingFaceGgufDownloader) -> None:
    with pytest.raises(GgufDownloadError):
        downloader.download(
            url="https://example.invalid/model.gguf",
            destination_path=str(tmp_path / "model.gguf"),
            expected_size_bytes=CATALOG_GUESS,
        )


def test_a_second_attempt_continues_from_the_bytes_the_first_one_left(tmp_path):
    """The whole feature, in the order it actually happens."""
    part = tmp_path / "model.gguf.part"
    asked_for: list[str | None] = []

    def recording(handler):
        def wrapped(request: httpx.Request) -> httpx.Response:
            asked_for.append(request.headers.get("range"))
            return handler(request)

        return wrapped

    dropping = HuggingFaceGgufDownloader(client=_server(recording(_drops_mid_transfer())))
    _interrupted_download(tmp_path, dropping)
    assert part.read_bytes() == WHOLE[:KEPT], "the dropped attempt kept nothing"

    result = HuggingFaceGgufDownloader(client=_server(recording(_serves_the_whole_file))).download(
        url="https://example.invalid/model.gguf",
        destination_path=str(tmp_path / "model.gguf"),
        expected_size_bytes=CATALOG_GUESS,
    )

    assert asked_for == [None, f"bytes={KEPT}-"]  # only the tail was fetched
    assert (tmp_path / "model.gguf").read_bytes() == WHOLE
    assert not part.exists()
    assert result == str(tmp_path / "model.gguf")


def test_an_approximate_catalog_size_does_not_defeat_resuming(tmp_path):
    """The bug this file exists to prevent from returning.

    Identity comes from what the server said when the bytes were stored, not
    from the caller's estimate. Here the estimate is wrong in both directions in
    turn, and neither may matter."""
    for guess in (len(WHOLE) + 500_000, len(WHOLE) - 4, None):
        for stale in tmp_path.glob("model.gguf*"):
            stale.unlink()
        asked_for: list[str | None] = []

        def recording(handler):
            def wrapped(request: httpx.Request) -> httpx.Response:
                asked_for.append(request.headers.get("range"))
                return handler(request)

            return wrapped

        dropping = HuggingFaceGgufDownloader(client=_server(recording(_drops_mid_transfer())))
        with pytest.raises(GgufDownloadError):
            dropping.download(
                url="https://example.invalid/model.gguf",
                destination_path=str(tmp_path / "model.gguf"),
                expected_size_bytes=guess,
            )
        HuggingFaceGgufDownloader(client=_server(recording(_serves_the_whole_file))).download(
            url="https://example.invalid/model.gguf",
            destination_path=str(tmp_path / "model.gguf"),
            expected_size_bytes=guess,
        )

        assert asked_for == [None, f"bytes={KEPT}-"], f"guess={guess} broke the resume"
        assert (tmp_path / "model.gguf").read_bytes() == WHOLE


def test_progress_counts_the_resumed_bytes_too(tmp_path):
    """Otherwise a resume shows a bar that restarts at 0% and finishes early —
    the same download reported two different ways depending on how it began."""
    _interrupted_download(
        tmp_path, HuggingFaceGgufDownloader(client=_server(_drops_mid_transfer()))
    )
    seen: list[tuple[int, int | None]] = []

    HuggingFaceGgufDownloader(client=_server(_serves_the_whole_file)).download(
        url="https://example.invalid/model.gguf",
        destination_path=str(tmp_path / "model.gguf"),
        expected_size_bytes=CATALOG_GUESS,
        progress_callback=lambda done, total: seen.append((done, total)),
    )

    assert seen[-1] == (len(WHOLE), len(WHOLE))
    assert all(done > KEPT for done, _ in seen)


def test_a_network_drop_keeps_what_was_downloaded_and_says_so(tmp_path):
    part = tmp_path / "model.gguf.part"

    with pytest.raises(GgufDownloadError) as failure:
        HuggingFaceGgufDownloader(client=_server(_drops_mid_transfer())).download(
            url="https://example.invalid/model.gguf",
            destination_path=str(tmp_path / "model.gguf"),
            expected_size_bytes=CATALOG_GUESS,
        )

    assert part.read_bytes() == WHOLE[:KEPT], "the partial download was thrown away again"
    assert not (tmp_path / "model.gguf").exists()
    # And it says so, rather than leaving the person guessing what to do next.
    assert "continue from where it stopped" in str(failure.value)


def test_cancelling_throws_the_partial_file_away(tmp_path):
    with pytest.raises(GgufDownloadCancelledError):
        HuggingFaceGgufDownloader(client=_server(_serves_the_whole_file)).download(
            url="https://example.invalid/model.gguf",
            destination_path=str(tmp_path / "model.gguf"),
            expected_size_bytes=CATALOG_GUESS,
            cancellation_check=lambda: True,
        )

    # Both the bytes and the note about where they came from.
    assert list(tmp_path.glob("model.gguf*")) == []


def test_leftovers_from_a_different_file_are_never_appended_to(tmp_path):
    """The hazard resuming introduces, and the one that must not be shipped.

    A ``.part`` left by an older revision of the same filename would be appended
    to and then atomically published — a corrupt model that passes every check
    the app makes, because the app only checks that the file is there and big
    enough.

    The download no longer stops to complain about this; the person asked for the
    model, so it is fetched whole. What matters is that the stale bytes are gone
    from the result, and this asserts on the bytes, not on a message."""
    _interrupted_download(
        tmp_path, HuggingFaceGgufDownloader(client=_server(_drops_mid_transfer()))
    )
    replaced = bytes(range(255, -1, -1)) * (2 * CHUNK // 256)

    def serves_another_file(request: httpx.Request) -> httpx.Response:
        start = _range_start(request)
        if start:
            return httpx.Response(
                206,
                content=replaced[start:],
                headers={"content-range": f"bytes {start}-{len(replaced) - 1}/{len(replaced)}"},
            )
        return httpx.Response(
            200, content=replaced, headers={"content-length": str(len(replaced))}
        )

    HuggingFaceGgufDownloader(client=_server(serves_another_file)).download(
        url="https://example.invalid/model.gguf",
        destination_path=str(tmp_path / "model.gguf"),
        expected_size_bytes=CATALOG_GUESS,
    )

    published = (tmp_path / "model.gguf").read_bytes()
    assert published == replaced
    assert WHOLE[:KEPT] not in published
    assert not (tmp_path / "model.gguf.part").exists()


def test_a_range_past_the_end_of_the_served_file_starts_over(tmp_path):
    """A 416 means these bytes are not part of what is being served."""
    _interrupted_download(
        tmp_path, HuggingFaceGgufDownloader(client=_server(_drops_mid_transfer()))
    )
    shorter = WHOLE[: CHUNK // 2]

    def refuses_the_range(request: httpx.Request) -> httpx.Response:
        if _range_start(request):
            return httpx.Response(416, content=b"")
        return httpx.Response(200, content=shorter, headers={"content-length": str(len(shorter))})

    HuggingFaceGgufDownloader(client=_server(refuses_the_range)).download(
        url="https://example.invalid/model.gguf",
        destination_path=str(tmp_path / "model.gguf"),
        expected_size_bytes=CATALOG_GUESS,
    )

    assert (tmp_path / "model.gguf").read_bytes() == shorter


def test_a_server_that_ignores_range_simply_starts_over(tmp_path):
    """Not every host honours Range. Answering 200 with the whole file is a
    legitimate reply to it, and the result must still be a correct file — not
    the tail appended to the head."""
    _interrupted_download(
        tmp_path, HuggingFaceGgufDownloader(client=_server(_drops_mid_transfer()))
    )
    seen: list[tuple[int, int | None]] = []

    def ignores_range(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=WHOLE, headers={"content-length": str(len(WHOLE))})

    HuggingFaceGgufDownloader(client=_server(ignores_range)).download(
        url="https://example.invalid/model.gguf",
        destination_path=str(tmp_path / "model.gguf"),
        expected_size_bytes=CATALOG_GUESS,
        progress_callback=lambda done, total: seen.append((done, total)),
    )

    assert (tmp_path / "model.gguf").read_bytes() == WHOLE
    assert seen[-1] == (len(WHOLE), len(WHOLE))


def test_a_leftover_from_an_older_version_is_not_resumed(tmp_path):
    """Upgrading over a ``.part`` written before any of this existed: nothing
    recorded where those bytes came from, so they are not trusted."""
    (tmp_path / "model.gguf.part").write_bytes(WHOLE[:KEPT])
    asked_for: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked_for.append(request.headers.get("range"))
        return _serves_the_whole_file(request)

    HuggingFaceGgufDownloader(client=_server(handler)).download(
        url="https://example.invalid/model.gguf",
        destination_path=str(tmp_path / "model.gguf"),
        expected_size_bytes=CATALOG_GUESS,
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
            expected_size_bytes=CATALOG_GUESS,
        )

    assert not destination.exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
