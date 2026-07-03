"""Oversized single lines split at soft boundaries, not mid-token."""

import re

from app.core.domain.chunking import _hard_split


def test_long_line_ends_chunks_at_separators_not_mid_token():
    # 60 comma-separated identifiers on ONE line, well over max_chars.
    tokens = [f"identifier_{i:03d}" for i in range(60)]
    line = ", ".join(tokens)
    pieces = _hard_split(line, max_chars=120, overlap=20)

    assert len(pieces) > 1
    # Every chunk except the last ends on a COMPLETE token (soft boundary cut),
    # never mid-identifier like "...identifier_04". (Overlap may seed the START
    # of the next chunk mid-token — that's intentional context bleed.)
    for piece in pieces[:-1]:
        assert len(piece) <= 120
        assert re.search(r"identifier_\d{3}[,\s]*$", piece), piece


def test_unbreakable_line_falls_back_to_char_cut():
    # No separators at all → blind character cut, still bounded and complete.
    line = "a" * 5000
    pieces = _hard_split(line, max_chars=1000, overlap=100)
    assert len(pieces) >= 5
    assert all(len(p) <= 1000 for p in pieces)
    assert all(set(p) == {"a"} for p in pieces)


def test_multiline_unit_uses_line_packing():
    text = "\n".join(f"line number {i}" for i in range(200))
    pieces = _hard_split(text, max_chars=200, overlap=40)
    assert len(pieces) > 1
    # Line packing keeps whole lines together (never splits "line number N").
    for piece in pieces:
        for fragment in piece.split("\n"):
            assert fragment.startswith("line number")


def test_always_makes_progress_no_infinite_loop():
    # overlap >= max_chars must not stall.
    line = ", ".join(str(i) for i in range(400))
    pieces = _hard_split(line, max_chars=50, overlap=60)
    assert len(pieces) > 1
    assert all(len(p) <= 50 for p in pieces)
