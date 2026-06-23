#!/usr/bin/env python3
"""Render a JUnit XML test report as GitHub-flavoured Markdown.

Used in CI to turn ``pytest --junitxml`` output into a readable summary on the
workflow run page (via ``$GITHUB_STEP_SUMMARY``). No third-party actions and no
extra dependencies — just the standard library — so it adds nothing to the
supply chain and needs no elevated permissions.

Usage::

    python scripts/ci_test_summary.py backend/test-results.xml >> "$GITHUB_STEP_SUMMARY"
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET


def _aggregate(root: ET.Element) -> dict[str, float]:
    """Sum counts across one or more <testsuite> elements."""
    suites = root.iter("testsuite")
    totals = {"tests": 0.0, "failures": 0.0, "errors": 0.0, "skipped": 0.0, "time": 0.0}
    for suite in suites:
        for key in totals:
            totals[key] += float(suite.get(key, 0) or 0)
    return totals


def _failures(root: ET.Element, limit: int = 20) -> list[str]:
    """Collect the names of failing/erroring test cases for a short list."""
    out: list[str] = []
    for case in root.iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            classname = case.get("classname", "")
            name = case.get("name", "")
            out.append(f"{classname}::{name}" if classname else name)
            if len(out) >= limit:
                break
    return out


def main(path: str) -> int:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        print(f"### ⚠️ Test report unavailable\n\nCould not read `{path}`: {exc}")
        return 0  # don't fail the job just because the summary couldn't render

    t = _aggregate(root)
    total = int(t["tests"])
    failures = int(t["failures"])
    errors = int(t["errors"])
    skipped = int(t["skipped"])
    passed = total - failures - errors - skipped
    ok = failures == 0 and errors == 0
    icon = "✅" if ok else "❌"

    lines = [
        f"## {icon} Backend tests",
        "",
        "| Result | Count |",
        "| --- | ---: |",
        f"| ✅ Passed | {passed} |",
        f"| ❌ Failed | {failures} |",
        f"| 💥 Errors | {errors} |",
        f"| ⏭️ Skipped | {skipped} |",
        f"| **Total** | **{total}** |",
        "",
        f"Finished in {t['time']:.1f}s.",
    ]

    if not ok:
        names = _failures(root)
        lines += ["", "### Failing tests", ""]
        lines += [f"- `{n}`" for n in names]
        if len(names) >= 20:
            lines.append("- … (truncated)")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "test-results.xml"))
