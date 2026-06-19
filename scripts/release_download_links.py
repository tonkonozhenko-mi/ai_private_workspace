#!/usr/bin/env python3
"""Build a platform-grouped "Downloads" markdown block for a GitHub Release.

Reads the release's assets (JSON from `gh release view --json assets`) from the
ASSETS_JSON environment variable and prints a tidy Downloads section grouped by
platform — macOS (Apple Silicon / Intel) and Windows — with direct download
links. Only user-facing installers (.dmg, NSIS .exe) are listed; updater
artifacts (.sig, .tar.gz, latest.json) are intentionally skipped.

Usage (in CI):
    ASSETS_JSON="$(gh release view "$TAG" --repo "$REPO" --json assets)" \
        python3 scripts/release_download_links.py "$REPO" "$TAG"

Because the download URL is derived from <repo>/<tag>/<asset-name>, the links
are correct regardless of the exact file names the bundler produced.
"""

import json
import os
import sys
import urllib.parse


def _link(repo: str, tag: str, label: str, name: str) -> str:
    url = f"https://github.com/{repo}/releases/download/{tag}/" + urllib.parse.quote(name)
    return f"- [{label}]({url})"


def build_downloads(repo: str, tag: str, assets: list[dict]) -> str:
    mac: list[str] = []
    win: list[str] = []
    for asset in assets:
        name = asset.get("name", "")
        low = name.lower()
        if low.endswith(".dmg"):
            if "aarch64" in low or "arm64" in low:
                mac.append(_link(repo, tag, "Apple Silicon (arm64)", name))
            elif "x64" in low or "x86_64" in low or "intel" in low:
                mac.append(_link(repo, tag, "Intel (x64)", name))
            else:
                mac.append(_link(repo, tag, "macOS", name))
        elif low.endswith("setup.exe"):
            win.append(_link(repo, tag, "Windows x64 installer (.exe)", name))

    if not mac and not win:
        return ""

    lines: list[str] = ["## Downloads", ""]
    if mac:
        lines += ["### macOS", *sorted(set(mac)), ""]
    if win:
        lines += ["### Windows", *sorted(set(win)), ""]
    return "\n".join(lines).rstrip()


def main() -> int:
    if len(sys.argv) != 3:
        sys.stderr.write("usage: release_download_links.py <owner/repo> <tag>\n")
        return 2
    repo, tag = sys.argv[1], sys.argv[2]
    try:
        assets = json.loads(os.environ.get("ASSETS_JSON", "{}")).get("assets", [])
    except json.JSONDecodeError:
        assets = []
    print(build_downloads(repo, tag, assets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
