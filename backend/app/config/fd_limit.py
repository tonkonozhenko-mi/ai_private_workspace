"""Raise the process file-descriptor limit at startup.

Why this exists (live incident, 2026-07-05): macOS gives GUI-launched
processes a soft RLIMIT_NOFILE of 256. The packaged backend runs SQLite with
a connection per operation, serves a polling frontend (job progress every
second, workspace state every 3 s — each fanning out to several endpoints),
and talks to two llama-server processes over HTTP. During a 3,577-file
"Build search context" the process hovered at the ceiling for minutes and
finally hit ``OSError: [Errno 24] Too many open files`` at ~93%%:
the index job died, and every later SQLite open failed with
"unable to open database file" until restart.

Raising the soft limit toward the hard limit (typically ``unlimited`` /
very large on macOS) removes the whole failure class. Best-effort by
design: if the platform refuses, the app still boots — we just keep the
old ceiling and log what happened.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("uvicorn.error.ai_private_workspace.fd_limit")

# Comfortable headroom: polling storm + SQLite churn + engine sockets stay
# well under a thousand; 8192 leaves room for big projects and future work.
TARGET_SOFT_LIMIT = 8192


def raise_fd_limit(target: int = TARGET_SOFT_LIMIT) -> tuple[int, int] | None:
    """Raise RLIMIT_NOFILE's soft limit to ``min(target, hard)``.

    Returns the (old_soft, new_soft) pair when a change was made, or None
    when unsupported (non-POSIX) or already high enough. Never raises.
    """
    try:
        import resource
    except ImportError:  # Windows: no resource module; select() limits differ.
        return None

    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if hard == resource.RLIM_INFINITY:
            new_soft = target
        else:
            new_soft = min(target, hard)
        if new_soft <= soft:
            return None
        resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
        logger.info(
            "Raised open-file limit: soft %d -> %d (hard: %s)",
            soft,
            new_soft,
            "unlimited" if hard == resource.RLIM_INFINITY else hard,
        )
        return (soft, new_soft)
    except Exception:  # noqa: BLE001 - never block boot over a ulimit
        logger.warning("Could not raise the open-file limit; keeping the default.")
        return None
