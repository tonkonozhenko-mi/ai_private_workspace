"""The locked build must never ship a package older than we declared safe.

Two files disagree about versions and only one of them is installed:

* ``requirements.txt`` holds the FLOORS (``fastapi>=0.141.1``). Dependabot and
  our security triage raise these — several exist purely to clear a CVE.
* ``requirements.lock`` holds the EXACT pins, and it is what CI, the release
  workflow, the Windows build and the desktop packaging install. It is what
  actually ships.

Raising a floor does nothing on its own: unless somebody regenerates the lock,
the app keeps shipping the old version while the repository claims otherwise.
That already happened once — ``pytest`` sat at 8.4.2 in the lock, carrying
CVE-2025-71176, while the floor read ``>=9.1.1`` (see CHANGELOG 0.6.x). It was
fixed by hand, one package at a time, and no guard was added — so it came back
on four packages at once.

This test is that guard. It is deliberately dumb: compare the two files, fail
loudly, name the packages. Nothing here reaches the network.

When this test fails, regenerate the lock rather than editing it by hand:

    cd backend
    python -m venv .venv-lock && . .venv-lock/bin/activate
    pip install -r requirements.txt
    pip freeze --exclude-editable > requirements.lock
    # then restore the uvloop platform marker at the bottom of the file

If a floor genuinely cannot be met (the new version needs a newer Python than
we build with), that is a decision, not a lint failure: lower the floor, or
raise the Python, and say which in the commit message.
"""

import re
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_LOCK = _BACKEND / "requirements.lock"
_REQUIREMENTS = (
    _BACKEND / "requirements.txt",
    _BACKEND / "requirements-qdrant.txt",
)

# "fastapi>=0.141.1,<1.0" and "uvicorn[standard]>=0.52.0,<1.0" alike.
_FLOOR_RE = re.compile(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]+\])?>=([0-9][^,;\s]*)")
_PIN_RE = re.compile(r"^([A-Za-z0-9_.\-]+)==([^;\s]+)")


def _canonical(name: str) -> str:
    """PyPI treats '_' and '-' alike and is case-insensitive (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _version_key(version: str) -> tuple[int, ...]:
    """Numeric release segments only — enough to order the pins we hold, and it
    never raises on a suffix like '1.2.3.post1' or '2026.5.20'."""
    return tuple(int(part) for part in re.findall(r"\d+", version)[:4])


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _locked_versions() -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in _LOCK.read_text(encoding="utf-8").splitlines():
        match = _PIN_RE.match(_strip_comment(raw))
        if match:
            pins[_canonical(match.group(1))] = match.group(2)
    return pins


def _declared_floors() -> dict[str, str]:
    floors: dict[str, str] = {}
    for path in _REQUIREMENTS:
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = _strip_comment(raw)
            if not line or line.startswith("-"):
                continue
            match = _FLOOR_RE.match(line)
            if match:
                floors[_canonical(match.group(1))] = match.group(2)
    return floors


def test_the_lock_actually_holds_pins():
    # A guard that silently reads an empty file guards nothing.
    assert len(_locked_versions()) > 10


def test_every_declared_floor_is_also_declared_somewhere():
    assert len(_declared_floors()) > 5


def test_no_locked_package_is_older_than_its_declared_floor():
    locked = _locked_versions()
    behind = []
    for name, floor in sorted(_declared_floors().items()):
        pinned = locked.get(name)
        if pinned is None:
            continue  # optional extra (e.g. qdrant) not part of the shipped lock
        if _version_key(pinned) < _version_key(floor):
            behind.append(f"{name}: lock has {pinned}, requirements floor is >={floor}")
    assert not behind, (
        "requirements.lock ships versions older than requirements.txt declares safe.\n"
        "The lock is what CI and the release build install, so these are the versions\n"
        "users actually get:\n  " + "\n  ".join(behind) + "\n"
        "Regenerate the lock (see this file's docstring) rather than editing it by hand."
    )


def test_the_regeneration_recipe_is_written_down():
    # The reason this drifts is that nobody knows how to rebuild the lock. If the
    # recipe leaves this file, the guard becomes a nag instead of a fix.
    doc = Path(__file__).read_text(encoding="utf-8")
    assert "pip freeze" in doc and "requirements.lock" in doc


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
