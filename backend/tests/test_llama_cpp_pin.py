"""The bundled llama.cpp version is pinned in exactly one place.

It used to live in three: the fetch script's default and two workflows. They drifted
— which is how a release could ship a llama-server nobody had tested. The pin is a
build-time fact, not a runtime one, so nothing in the app reads it; this test is the
only thing standing between us and a fourth copy.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PIN_FILE = _ROOT / "scripts" / "llama_cpp_version.txt"
_TAG_RE = re.compile(r"^b\d{3,6}$")
# A llama.cpp build tag written literally, e.g. b9789.
_HARDCODED_TAG_RE = re.compile(r"\bb\d{4,6}\b")


def _pin() -> str:
    lines = [
        line.strip()
        for line in _PIN_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert len(lines) == 1, "the pin file must hold exactly one version"
    return lines[0]


def test_the_pin_is_a_real_llama_cpp_build_tag():
    assert _TAG_RE.match(_pin()), _pin()


def test_the_fetch_script_reads_the_pin_instead_of_carrying_its_own():
    script = (_ROOT / "scripts" / "fetch_llama_server.sh").read_text(encoding="utf-8")
    assert "llama_cpp_version.txt" in script
    assert not _HARDCODED_TAG_RE.search(script), "the script must not carry its own pin"


def test_no_workflow_carries_a_second_copy_of_the_pin():
    for workflow in sorted((_ROOT / ".github" / "workflows").glob("*.yml")):
        found = _HARDCODED_TAG_RE.findall(workflow.read_text(encoding="utf-8"))
        assert not found, f"{workflow.name} hardcodes a llama.cpp tag: {found}"
