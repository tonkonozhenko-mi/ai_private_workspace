"""Golden-set eval runner.

Indexes a target repo with a chosen embedding model, runs the labelled question
set through the REAL retrieval path (hybrid dense+BM25 → RRF → per-file cap → MMR
→ parent-doc expansion → calibrated abstention floor), and writes a JSON + markdown
report to ``build/notes/eval/``.

Usage (from the ``backend/`` directory, with Ollama running):

    python -m eval.golden --embedder nomic
    python -m eval.golden --embedder qwen3
    python -m eval.golden --embedder bge-m3
    python -m eval.golden --all                 # all three, one after another
    python -m eval.golden --embedder nomic --repo /path/to/other/repo --with-generation

Retrieval metrics (hit@k, overblock, should-abstain) need only the embedder.
``--with-generation`` additionally generates answers with the Ollama LLM and
measures hallucination_rate (hard grounding warnings); skip it for a pure,
fast embedder comparison.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.core.domain.chunking import (
    build_contextual_chunk,
    chunk_document,
    estimate_tokens,
    strip_contextual_header,
)
from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.domain.indexing import TextChunk
from app.core.domain.question_intent import looks_general_chat
from app.core.domain.rag import RagSource
from app.core.domain.rag_answer_evaluator import evaluate_rag_answer
from app.core.domain.relevance_calibration import calibrate_from_embeddings
from app.core.use_cases.ask_workspace_question import (
    AskWorkspaceQuestionInput,
    AskWorkspaceQuestionUseCase,
    _hard_grounding_warnings,
)
from eval.golden_set import golden_set
from eval.harness import (
    QuestionOutcome,
    compute_report,
    render_markdown,
    report_to_dict,
)

# --embedder alias -> (Ollama model tag, human label)
EMBEDDERS = {
    "nomic": "nomic-embed-text",
    "qwen3": "qwen3-embedding:0.6b",
    "bge-m3": "bge-m3",
}

# extension / filename -> the chunker's file_type (mirrors INDEXABLE_FILE_TYPES)
_EXT_TYPE = {
    ".py": "python",
    ".md": "markdown",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".tf": "terraform",
    ".tfvars": "terraform",
    ".hcl": "terragrunt",
    ".sh": "shell",
}
_SKIP_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "target",
    "__pycache__",
    "site-packages",
    ".mypy_cache",
    ".pytest_cache",
    "coverage",
    ".idea",
}
# Path fragments (posix) that mark generated/vendored trees — skipped wholesale so
# the corpus is only real project source. ``src-tauri/gen`` holds generated schemas.
# ``backend/eval/`` is the benchmark itself: golden_set.py contains the questions
# verbatim, so indexing it lets the eval retrieve its own answer sheet (observed:
# golden_set.py surfacing for pp-full-context and several should_abstain questions).
_SKIP_PATH_FRAGMENTS = ("src-tauri/gen/", "backend/eval/")


def _is_skipped_dir(part: str) -> bool:
    # Virtualenvs come in variants (.venv, .venv-x86_64, venv, env) — a prefix match
    # catches them all; a bare-name set catches the rest.
    return part in _SKIP_DIRS or part == "venv" or part.startswith(".venv")


_MAX_FILE_BYTES = 400_000
# Generated lock/manifest files add thousands of low-signal chunks and dominate the
# corpus without helping retrieval — skip them (the real app doesn't index most of
# these types anyway; this keeps the eval faithful and fast).
_SKIP_FILES = {"package-lock.json", "pnpm-lock.json"}
# How many chunk bodies to embed per Ollama request. The API takes an array, but a
# single request with tens of thousands of items overflows it (HTTP 400) — the app
# indexer batches for the same reason.
_EMBED_BATCH = 64


def _detect_type(path: Path) -> str | None:
    if path.name in _SKIP_FILES:
        return None
    if path.name.endswith("-lock.json"):
        return None
    if path.name == "Dockerfile":
        return "docker"
    if path.name == "tauri.conf.json":
        return "json"
    return _EXT_TYPE.get(path.suffix.lower())


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(_is_skipped_dir(part) for part in path.parts):
            continue
        posix = path.as_posix()
        if any(fragment in posix for fragment in _SKIP_PATH_FRAGMENTS):
            continue
        file_type = _detect_type(path)
        if file_type is None:
            continue
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if text.strip():
            yield path.relative_to(root).as_posix(), file_type, path.suffix.lstrip("."), text


def _build_embedder(model_tag: str, base_url: str):
    from app.adapters.embeddings.ollama_embedding_provider import OllamaEmbeddingProvider

    return OllamaEmbeddingProvider(base_url=base_url, model=model_tag, timeout_seconds=120)


def _build_llm(base_url: str, model: str):
    from app.adapters.llm.ollama_llm_provider import OllamaLLMProvider

    return OllamaLLMProvider(base_url=base_url, model=model, timeout_seconds=180)


def _index_repo(workspace_id, repo, embedder, vector_store):
    """Chunk + embed every indexable file into the vector store. Returns
    (chunks_count, relevance_floor)."""
    chunks: list[TextChunk] = []
    for rel_path, file_type, extension, text in _iter_files(repo):
        raw = chunk_document(text, file_type=file_type, extension=extension)
        total = len(raw)
        for i, body in enumerate(raw):
            content = build_contextual_chunk(
                body,
                source_path=rel_path,
                position=i + 1,
                total=total,
                file_type=file_type,
                extension=extension,
            )
            chunks.append(
                TextChunk(
                    id=f"{workspace_id}:{rel_path}:{i}",
                    workspace_id=workspace_id,
                    source_path=rel_path,
                    chunk_index=i,
                    content=content,
                    token_estimate=estimate_tokens(content),
                    metadata={"detected_type": file_type, "extension": extension},
                )
            )
    if not chunks:
        raise SystemExit(f"No indexable files found under {repo}")

    bodies = [strip_contextual_header(c.content) for c in chunks]
    print(f"  embedding {len(chunks)} chunks (batch {_EMBED_BATCH})…", flush=True)
    embeddings: list[list[float]] = []
    for start in range(0, len(bodies), _EMBED_BATCH):
        embeddings.extend(embedder.embed_texts(bodies[start : start + _EMBED_BATCH]))
        done = min(start + _EMBED_BATCH, len(bodies))
        if done % (_EMBED_BATCH * 20) == 0 or done == len(bodies):
            print(f"    {done}/{len(bodies)}", flush=True)
    dim = len(embeddings[0])
    vector_store.upsert_chunks(
        workspace_id=workspace_id,
        chunks=chunks,
        embeddings=embeddings,
        embedding_provider=embedder.provider_name,
        embedding_model=embedder.model_name,
        embedding_dimension=dim,
    )
    return len(chunks), calibrate_from_embeddings(embeddings)


def _run_embedder(alias: str, repo: Path, k: int, base_url: str, llm_model: str | None):
    model_tag = EMBEDDERS[alias]
    print(f"[{alias}] model={model_tag} repo={repo}", flush=True)
    embedder = _build_embedder(model_tag, base_url)

    from app.adapters.vector_store.sqlite_vector_store import SQLiteVectorStore

    workspace_id = "eval"
    with tempfile.TemporaryDirectory() as tmp:
        store = SQLiteVectorStore(str(Path(tmp) / "eval.db"))
        chunks_count, floor = _index_repo(workspace_id, repo, embedder, store)

        status = WorkspaceIndexStatus(
            workspace_id=workspace_id,
            status="indexed",
            indexed_files_count=0,
            chunks_count=chunks_count,
            skipped_files_count=0,
            last_indexed_at=datetime.now(timezone.utc).isoformat(),
            last_error=None,
            embedding_model=embedder.model_name,
            relevance_floor=floor,
        )
        workspace = SimpleNamespace(id=workspace_id, project_path=str(repo))
        uc = AskWorkspaceQuestionUseCase(
            workspace_repository=SimpleNamespace(get=lambda _wid: workspace),
            embedding_provider=embedder,
            vector_store=store,
            llm_provider_factory=None,
            index_status_repository=SimpleNamespace(get=lambda _wid: status),
        )
        threshold = uc._relevance_threshold(status, None)
        print(f"  calibrated floor={floor} → threshold={threshold:.3f}", flush=True)

        llm = _build_llm(base_url, llm_model) if llm_model else None
        outcomes: list[QuestionOutcome] = []
        routed_count = 0
        for case in golden_set():
            request = AskWorkspaceQuestionInput(
                workspace_id=workspace_id, question=case.question, limit=k
            )
            # Mirror the product decision: obvious chit-chat is routed straight to
            # general conversation BEFORE retrieval (feat/general-chat-router). The
            # eval still runs retrieval so best_score/source_paths stay available as
            # diagnostics for the threshold layer, but `abstained` reflects what the
            # app would actually do.
            routed = looks_general_chat(case.question)
            routed_count += routed
            results = uc._search_context(request, None)
            best = max((r.score for r in results), default=0.0)
            abstained = routed or (not results) or best < threshold
            paths = tuple(dict.fromkeys(r.source_path for r in results))

            hallucinated = None
            if llm is not None and not abstained:
                hallucinated = _generation_hallucinated(uc, request, results, llm)

            outcomes.append(
                QuestionOutcome(
                    question_id=case.id,
                    abstained=abstained,
                    source_paths=paths,
                    best_score=best,
                    hallucinated=hallucinated,
                )
            )

        cases = list(golden_set())
        report = compute_report(alias, k, cases, outcomes)
        print(f"  routed to general chat before retrieval: {routed_count}", flush=True)
        _write_reports(report, cases, outcomes, floor=floor, threshold=threshold)
        _print_summary(report)


def _generation_hallucinated(uc, request, results, llm) -> bool | None:
    """Best-effort: generate a grounded answer and report whether it carried a hard
    grounding warning. Returns None on any failure (generation is optional)."""
    try:
        context_results, prompt, _m, _f, _u = uc._grounded_prompt(request, llm, results, [])
        answer, _usage = uc._generate_answer_with_usage(llm, prompt, [], None, None, [])
        sources = [
            RagSource(
                chunk_id=r.chunk_id,
                source_path=r.source_path,
                score=r.score,
                preview=r.content[:200],
            )
            for r in context_results
        ]
        warnings = evaluate_rag_answer(
            question=request.question,
            answer=answer,
            sources=sources,
            source_contents=[r.content for r in context_results],
        )
        return bool(_hard_grounding_warnings(warnings))
    except Exception as error:  # noqa: BLE001
        print(f"    (generation skipped for {request.question[:40]!r}: {error})", flush=True)
        return None


def _out_dir() -> Path:
    # backend/eval/golden.py -> repo root -> build/notes/eval
    root = Path(__file__).resolve().parents[2]
    out = root / "build" / "notes" / "eval"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_reports(report, cases, outcomes, floor=None, threshold=None) -> None:
    """Write JSON + markdown. ``floor``/``threshold`` are recorded in both — the
    P5 verdict needs them next to the scores, not just in the console scrollback."""
    out = _out_dir()
    stamp = datetime.now().strftime("%Y-%m-%d")
    base = f"golden_{report.embedder}_{stamp}"
    data = report_to_dict(report, cases, outcomes)
    if floor is not None:
        data["relevance_floor"] = floor
    if threshold is not None:
        data["threshold"] = round(threshold, 4)
    (out / f"{base}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    md = render_markdown(report, cases, outcomes)
    if threshold is not None:
        md = md.replace(
            "\n\n",
            f"\n\n- Calibrated floor: **{floor}** → abstention threshold: **{threshold:.3f}**\n",
            1,
        )
    (out / f"{base}.md").write_text(md, encoding="utf-8")
    print(f"  wrote {out / base}.json / .md", flush=True)


def _print_summary(report) -> None:
    print(
        f"  hit@{report.k}={_p(report.overall_retrieval_hit_at_k)} "
        f"overblock={_p(report.overall_overblock_rate)} "
        f"should-abstain={_p(report.overall_should_abstain_accuracy)} "
        f"halluc={_p(report.overall_hallucination_rate)}",
        flush=True,
    )


def _p(v) -> str:
    return "—" if v is None else f"{v * 100:.1f}%"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Golden-set retrieval eval")
    parser.add_argument("--embedder", choices=sorted(EMBEDDERS), help="which embedder to run")
    parser.add_argument("--all", action="store_true", help="run all embedders in turn")
    parser.add_argument("--repo", default=None, help="target repo path (default: this repo)")
    parser.add_argument("--k", type=int, default=5, help="top-k for retrieval (default 5)")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument(
        "--with-generation",
        nargs="?",
        const="qwen2.5-coder",
        default=None,
        help="also generate answers with this Ollama LLM and measure hallucination "
        "(default model qwen2.5-coder if flag given without value)",
    )
    args = parser.parse_args(argv)

    if not args.all and not args.embedder:
        parser.error("pass --embedder <name> or --all")

    repo = Path(args.repo).resolve() if args.repo else Path(__file__).resolve().parents[2]
    aliases = sorted(EMBEDDERS) if args.all else [args.embedder]
    for alias in aliases:
        _run_embedder(alias, repo, args.k, args.ollama_url, args.with_generation)
    return 0


if __name__ == "__main__":
    sys.exit(main())
