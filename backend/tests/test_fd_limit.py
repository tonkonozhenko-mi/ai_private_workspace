"""The backend must raise its open-file soft limit at startup.

Live incident: the packaged app (macOS GUI default: soft limit 256) died at
93%% of a 3,577-file index build with OSError 24, taking every later SQLite
open down with it. raise_fd_limit() is the guard; these tests pin its
contract: raise toward the hard limit, never above it, never crash.
"""

import resource

from app.config.fd_limit import raise_fd_limit


def _get_limits() -> tuple[int, int]:
    return resource.getrlimit(resource.RLIMIT_NOFILE)


def test_raises_soft_limit_when_below_target() -> None:
    soft, hard = _get_limits()
    try:
        # Simulate the constrained GUI environment within our own hard limit.
        low = min(256, soft)
        resource.setrlimit(resource.RLIMIT_NOFILE, (low, hard))

        result = raise_fd_limit(target=min(1024, hard if hard != resource.RLIM_INFINITY else 1024))

        new_soft, _ = _get_limits()
        assert result is not None
        assert new_soft > low
        assert new_soft >= result[1]
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))


def test_never_exceeds_hard_limit() -> None:
    soft, hard = _get_limits()
    try:
        result = raise_fd_limit(target=2**30)
        new_soft, new_hard = _get_limits()
        assert new_hard == hard
        if hard != resource.RLIM_INFINITY:
            assert new_soft <= hard
        # Either it raised (result set) or it was already at the ceiling (None).
        assert result is None or result[1] > result[0]
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))


def test_noop_when_already_high_enough() -> None:
    soft, hard = _get_limits()
    try:
        assert raise_fd_limit(target=soft) is None
        assert _get_limits()[0] == soft
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
