"""External benchmark corpora: public repositories pinned to exact commits.

The in-repo golden set proves regressions; it cannot prove generality — a
benchmark whose corpus is its own repository is a take-my-word-for-it number.
These corpora are other people's projects, chosen one per project kind the app
claims to understand, each pinned to a commit so a run is reproducible
byte-for-byte and the published questions can never quietly drift onto easier
content.

The protocol that keeps the numbers honest:

1. Questions are **pre-registered**: written from reading the pinned tree and
   committed BEFORE the first scored run. They are never edited to fit results;
   a bad question is retired in a commit that says so.
2. The corpus commit is **pinned**; ``python -m eval.prepare`` fetches exactly
   that commit. Upgrading a pin is a commit that re-registers the questions.
3. Every corpus runs twice per report: the full pipeline, and ``--baseline``
   (plain vector top-k, fixed threshold, no keyword search, no correction) —
   the same questions, so the pipeline's value is a measured difference, not
   an adjective.

Checkouts live under ``build/eval-corpora/<name>`` (gitignored).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

# Repo root: backend/eval/corpora.py -> backend -> root
_ROOT = Path(__file__).resolve().parents[2]
CORPORA_DIR = _ROOT / "build" / "eval-corpora"


@dataclass(frozen=True)
class Corpus:
    name: str
    git_url: str
    commit: str  # full 40-char sha — a moving ref would unpin the questions
    kind: str  # what this corpus represents in the claim matrix
    notes: str = ""

    @property
    def local_path(self) -> Path:
        return CORPORA_DIR / self.name


CORPORA: dict[str, Corpus] = {
    corpus.name: corpus
    for corpus in (
        Corpus(
            name="tf-aws-vpc",
            git_url="https://github.com/terraform-aws-modules/terraform-aws-vpc.git",
            commit="3ffbd46fb1c7733e1b34d8666893280454e27436",  # v6.6.1
            kind="Terraform module repository",
            notes="The most-used community Terraform module; heavy HCL, examples/, submodules.",
        ),
        Corpus(
            name="online-boutique",
            git_url="https://github.com/GoogleCloudPlatform/microservices-demo.git",
            commit="9a4616e77f0f9cbcbecaf27d711c38890dda1404",
            kind="Kubernetes microservices platform",
            notes="11 services in 5 languages, k8s + istio manifests, protos — a polyglot platform.",
        ),
        Corpus(
            name="fastapi-template",
            git_url="https://github.com/fastapi/full-stack-fastapi-template.git",
            commit="7d80b8534ecfff3d4c6cc631012298d6ef605ca0",
            kind="Python backend + React frontend",
            notes="FastAPI/SQLModel backend, React frontend, compose files, alembic migrations.",
        ),
        # The wiki corpus is generated, not cloned: a deterministic fake
        # knowledge-base (ADR/Capability pages, cross-links, a companion asset
        # folder) built by ``python -m eval.make_wiki_corpus``. Generated, so it
        # ships no third-party text and never drifts; deterministic, so its
        # content hash is pinned by a test rather than a commit.
        Corpus(
            name="wiki-export",
            git_url="",  # generated locally — see make_wiki_corpus.py
            commit="generated",
            kind="Exported wiki / knowledge base",
            notes="Deterministic synthetic export: 24 markdown pages, ADR/Capability naming, cross-links.",
        ),
    )
}


class CorpusNotReadyError(RuntimeError):
    pass


def ensure_corpus(name: str) -> Path:
    """Return the corpus checkout, cloning/generating it if missing.

    Network is used only for the initial clone of a pinned commit; a prepared
    corpus never touches the network again.
    """
    corpus = CORPORA[name]
    path = corpus.local_path
    if name == "wiki-export":
        marker = path / "MANIFEST.md"
        if not marker.is_file():
            from eval.make_wiki_corpus import generate

            generate(path)
        return path

    if (path / ".git").is_dir():
        head = _git(path, "rev-parse", "HEAD").strip()
        if head != corpus.commit:
            _git(path, "fetch", "--depth", "1", "origin", corpus.commit)
            _git(path, "checkout", corpus.commit)
        return path

    CORPORA_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--no-checkout", corpus.git_url, str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(path, "checkout", corpus.commit)
    return path


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args], check=True, capture_output=True, text=True
    )
    return result.stdout


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Prepare external benchmark corpora.")
    parser.add_argument(
        "--corpus",
        choices=sorted(CORPORA),
        action="append",
        help="corpus to prepare (repeatable); default: all",
    )
    args = parser.parse_args()
    names = args.corpus or sorted(CORPORA)
    for name in names:
        path = ensure_corpus(name)
        print(f"{name}: ready at {path}")


if __name__ == "__main__":
    main()
