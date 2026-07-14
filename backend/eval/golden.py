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
    python -m eval.golden --embedder nomic --with-generation --save-answers --repeats 3
    python -m eval.golden --embedder nomic --with-generation --gen-backend llamacpp

Retrieval metrics (hit@k, overblock, should-abstain) need only the embedder.
``--with-generation`` additionally generates answers with the local LLM (default
qwen3:4b on Ollama; ``--gen-backend llamacpp`` runs the same questions through a
running llama-server instead, so a reader on either engine can reproduce the table) and measures the grounding-warning
rate twice: on the raw first answer and again after the app's corrective
regeneration pass — so the report shows the corrective sieve as a working
mechanism, not decoration. ``--save-answers`` records each answer + its warning
codes so flagged cases can be read by hand; ``--repeats N`` generates each answer
N times and majority-votes the flags to gauge spread. Skip ``--with-generation``
for a pure, fast embedder comparison.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from time import perf_counter
from dataclasses import replace
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
from app.core.domain.relevance_calibration import (
    PROBE_QUERIES,
    calibrate_from_embeddings,
    probe_ceiling,
)
from app.core.domain.source_files import GENERATED_CHECKED_TYPES, is_generated_source
from app.core.use_cases.ask_workspace_question import (
    AskWorkspaceQuestionInput,
    AskWorkspaceQuestionUseCase,
    _hard_grounding_warnings,
)
from eval.corpora import CORPORA, ensure_corpus
from eval.golden_set import golden_set
from eval.golden_set_acme import ACME_REPO_RELATIVE, golden_set_acme
from eval.golden_set_external import (
    golden_set_boutique,
    golden_set_fastapi_tmpl,
    golden_set_tf_vpc,
)
from eval.golden_set_wiki import golden_set_wiki
from eval.harness import (
    QuestionOutcome,
    compute_report,
    render_markdown,
    report_to_dict,
)

# Selectable question sets. Each maps to its labelled set plus the repo it is
# written against, relative to the project root (``None`` = this repository). The
# app set exercises retrieval on the RAG desktop app's own code; the acme set
# exercises a different domain (an AWS/Terraform + FastAPI payments platform under
# ``build/demo-project``) so the floor and hit-rate aren't tuned to one codebase.
QUESTION_SETS = {
    "app": (golden_set, None),
    "acme": (golden_set_acme, ACME_REPO_RELATIVE),
}

# External corpora: public repositories pinned by commit (eval/corpora.py) plus
# the generated wiki export, each with its pre-registered question set. The
# corpus checkout is resolved (cloned/generated if missing) at run time; the
# question sets live in eval/golden_set_external.py and golden_set_wiki.py and
# are never edited to fit results.
EXTERNAL_SETS = {
    "tf-aws-vpc": golden_set_tf_vpc,
    "online-boutique": golden_set_boutique,
    "fastapi-template": golden_set_fastapi_tmpl,
    "wiki-export": golden_set_wiki,
}
assert set(EXTERNAL_SETS) <= set(CORPORA)

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
    # The kinds the app's indexer learned in #196/#200 — the external corpora
    # (C#, Java, Go, protos, SQL migrations, TOML configs) are made of them, so
    # the eval corpus must match what the product actually indexes.
    ".sql": "source_code",
    ".cs": "source_code",
    ".java": "source_code",
    ".go": "source_code",
    ".js": "source_code",
    ".ts": "source_code",
    ".tsx": "source_code",
    ".jsx": "source_code",
    ".proto": "source_code",
    ".toml": "config",
    ".ini": "config",
}
# Tabular data goes through the product's own extractor (row blocks with the
# header repeated), not through the plain text chunker — same as the app.
_EXTRACTOR_SUFFIXES = {".csv", ".tsv"}
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
    # IaC caches: vendored copies of every Terraform module per environment. On a
    # real Terragrunt monorepo these multiplied the corpus into tens of thousands
    # of duplicate chunks (observed 2026-07-07: a --repo run took hours and every
    # retrieval hit was a .terraform/.terragrunt-cache duplicate). The real app
    # never indexes them — it respects .gitignore; the runner must skip them too.
    ".terraform",
    ".terragrunt-cache",
    ".tox",
    "vendor",
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
        # Judge skip rules against the path RELATIVE to the scanned root, never the
        # absolute path: a directory name like "build" in the way TO the repo must
        # not disqualify its contents ("--set acme" targets build/demo-project, and
        # the absolute-parts check skipped the entire corpus — "No indexable files").
        rel = path.relative_to(root)
        if any(_is_skipped_dir(part) for part in rel.parts):
            continue
        posix = rel.as_posix()
        if any(fragment in posix for fragment in _SKIP_PATH_FRAGMENTS):
            continue
        if path.suffix.lower() in _EXTRACTOR_SUFFIXES:
            text = _extract_tabular(path)
            if text:
                yield path.relative_to(root).as_posix(), "tabular_data", "csv", text
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
        # The product refuses machine-written source (a generator's header, or one
        # absurdly long line) at index time. The harness must refuse it too, or the
        # benchmark measures a product nobody ships: protobuf stubs crowding out the
        # .proto file a person actually wrote. The shared type set matters: a bare
        # "source_code" check let demo_pb2_grpc.py (detected as "python") back into
        # the top-5 on the very question the filter was written for.
        if file_type in GENERATED_CHECKED_TYPES and is_generated_source(text):
            continue
        if text.strip():
            yield path.relative_to(root).as_posix(), file_type, path.suffix.lstrip("."), text


def _extract_tabular(path: Path) -> str | None:
    """Read a CSV/TSV through the product's document extractor so the eval
    corpus carries the same row-block text (header repeated per block) the app
    indexes — not a raw comma dump the app would never produce."""
    try:
        from app.adapters.documents.local_document_extractor import LocalDocumentExtractor

        extracted = LocalDocumentExtractor().extract(str(path.parent), path.name, "tabular_data")
        if extracted.skipped_reason or extracted.is_empty:
            return None
        return "\n\n".join(f"[{section.locator}]\n{section.text}" for section in extracted.sections)
    except Exception:  # noqa: BLE001 - one odd file must not kill the corpus build
        return None


def _build_embedder(model_tag: str, backend: str, ollama_url: str, llama_embed_url: str):
    """The embedder for the chosen backend. Ollama selects the model by tag; the
    llama.cpp embed server serves whatever GGUF it was started with, so the tag is
    only a label there — start the app's llama engine on the matching model first."""
    if backend == "llamacpp":
        from app.adapters.embeddings.llama_server_embedding_provider import (
            LlamaServerEmbeddingProvider,
        )

        return LlamaServerEmbeddingProvider(
            base_url=llama_embed_url, model=model_tag, timeout_seconds=120
        )
    from app.adapters.embeddings.ollama_embedding_provider import OllamaEmbeddingProvider

    return OllamaEmbeddingProvider(base_url=ollama_url, model=model_tag, timeout_seconds=120)


# 360s, not the app's default: vpc-pp-endpoints timed out at 180s even on a WARM
# model (2026-07-14, post-warmup rerun) — dense Terraform context makes one
# generation legitimately slow. The eval is offline and would rather wait than
# report a coverage hole; the app's interactive timeout is a UX decision and stays
# where it is. Both engines get the same budget, or the comparison means nothing.
_GENERATION_TIMEOUT_SECONDS = 360


class LlamaServerNotRunning(RuntimeError):
    pass


def _build_llm(base_url: str, model: str, gen_backend: str, llama_gen_url: str):
    """The answer model for the chosen generation engine.

    The app ships two engines; until now the benchmark measured one, so a reader
    running llama.cpp could not reproduce the published table — and "run it
    yourself" is the whole claim. Ollama picks the model by tag; llama-server
    serves whatever GGUF it was started with, so the tag there is only a label.
    """
    if gen_backend == "llamacpp":
        import httpx

        from app.adapters.llm.llama_server_llm_provider import LlamaServerLLMProvider

        try:
            httpx.get(f"{llama_gen_url.rstrip('/')}/health", timeout=5)
        except httpx.HTTPError as error:
            raise LlamaServerNotRunning(
                f"No llama-server answering at {llama_gen_url} ({error}). Start the "
                "app's llama.cpp engine (or run llama-server on your answer model) "
                "and pass --llama-gen-url if it is not on the default port."
            ) from error
        return LlamaServerLLMProvider(
            base_url=llama_gen_url,
            model=model,
            timeout_seconds=_GENERATION_TIMEOUT_SECONDS,
        )

    from app.adapters.llm.ollama_llm_provider import OllamaLLMProvider

    return OllamaLLMProvider(
        base_url=base_url, model=model, timeout_seconds=_GENERATION_TIMEOUT_SECONDS
    )


def _warmup_llm(llm, attempts: int = 2) -> None:
    """Ping the answer model before the question loop so the FIRST real question
    never pays the cold-start bill. Observed twice on 2026-07-14 (vpc-pp-endpoints,
    shop-pp-single-manifest): Ollama's default keep_alive unloads the model during a
    long indexing phase, the first generate then times out and that question's
    generation is silently skipped. A failed warmup still helps — Ollama keeps
    loading in the background, so the retry (or the first question) hits a warm
    model. Never raises: the eval must not die on a warmup."""
    for attempt in range(1, attempts + 1):
        try:
            llm.generate("Reply with exactly: OK", temperature=0.0, think=False)
            print("  llm warmed up", flush=True)
            return
        except Exception as error:  # noqa: BLE001
            print(f"  (llm warmup attempt {attempt}/{attempts} failed: {error})", flush=True)
    print("  (llm warmup failed; first generation may be slow)", flush=True)


def _index_repo(workspace_id, repo, embedder, vector_store):
    """Chunk + embed every indexable file into the vector store. Returns
    (chunks_count, relevance_floor, relevance_probe_ceiling)."""
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
    # Mirror production's second calibration anchor: embed the fixed neutral probe
    # queries and take their highest similarity to the corpus (the empirical
    # chit-chat ceiling), so the eval threshold matches what the app computes.
    probe_embeddings = embedder.embed_texts(list(PROBE_QUERIES))
    ceiling = probe_ceiling(probe_embeddings, embeddings)
    return len(chunks), calibrate_from_embeddings(embeddings), ceiling


def _run_embedder(
    alias: str,
    repo: Path,
    k: int,
    base_url: str,
    llm_model: str | None,
    *,
    question_set=golden_set,
    set_name: str = "app",
    backend: str = "ollama",
    llama_embed_url: str = "http://127.0.0.1:8081",
    gen_backend: str = "ollama",
    llama_gen_url: str = "http://127.0.0.1:8080",
    save_answers: bool = False,
    repeats: int = 1,
    baseline: bool = False,
    role: str | None = None,
):
    cases_all = list(question_set())
    model_tag = EMBEDDERS[alias]
    # Distinct label per backend AND per question set so reports never overwrite each
    # other and the comparison (do the floors agree across backends and repos?) is
    # legible at a glance. The app set keeps its bare alias for backwards-compatible
    # report filenames; other sets are suffixed.
    label = alias if backend == "ollama" else f"{alias}-llamacpp"
    # The generation engine gets its own suffix so a llama.cpp run never overwrites
    # the published Ollama report — it is a second column, not a replacement.
    if gen_backend == "llamacpp" and llm_model:
        label = f"{label}-llamacpp-gen"
    if set_name != "app":
        label = f"{label}-{set_name}"
    if baseline:
        label = f"{label}-baseline"
    if role:
        label = f"{label}-{role}"
    print(f"[{label}] backend={backend} model={model_tag} repo={repo}", flush=True)
    embedder = _build_embedder(model_tag, backend, base_url, llama_embed_url)

    from app.adapters.vector_store.sqlite_vector_store import SQLiteVectorStore

    workspace_id = "eval"
    with tempfile.TemporaryDirectory() as tmp:
        store = SQLiteVectorStore(str(Path(tmp) / "eval.db"))
        chunks_count, floor, probe_ceiling_value = _index_repo(workspace_id, repo, embedder, store)

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
            relevance_probe_ceiling=probe_ceiling_value,
        )
        # ``assistant_mode`` mirrors the workspace role preference: --role runs the
        # same questions with the role's lens hint in the prompt. The invariant
        # under test: retrieval metrics must NOT move (the role lives in the
        # prose, never in the search).
        workspace = SimpleNamespace(id=workspace_id, project_path=str(repo), assistant_mode=role)
        uc = AskWorkspaceQuestionUseCase(
            workspace_repository=SimpleNamespace(get=lambda _wid: workspace),
            embedding_provider=embedder,
            vector_store=store,
            llm_provider_factory=None,
            index_status_repository=SimpleNamespace(get=lambda _wid: status),
        )
        # Baseline mode measures what a naive local RAG would do on the same
        # index: plain dense top-k, a fixed 0.30 threshold instead of the
        # calibrated floor, no small-talk router, and (under --with-generation)
        # no corrective pass. Same questions, same chunks, same embedder — the
        # difference between the two reports is the pipeline's measured value.
        BASELINE_THRESHOLD = 0.30
        threshold = BASELINE_THRESHOLD if baseline else uc._relevance_threshold(status, None)
        ceiling_str = f"{probe_ceiling_value:.3f}" if probe_ceiling_value is not None else "n/a"
        print(
            f"  calibrated floor={floor} probe_ceiling={ceiling_str} → threshold={threshold:.3f}",
            flush=True,
        )

        llm = (
            _build_llm(base_url, llm_model, gen_backend, llama_gen_url) if llm_model else None
        )
        if llm is not None:
            _warmup_llm(llm)
        outcomes: list[QuestionOutcome] = []
        routed_count = 0
        for case in cases_all:
            request = AskWorkspaceQuestionInput(
                workspace_id=workspace_id, question=case.question, limit=k
            )
            # Mirror the product decision: obvious chit-chat is routed straight to
            # general conversation BEFORE retrieval (feat/general-chat-router). The
            # eval still runs retrieval so best_score/source_paths stay available as
            # diagnostics for the threshold layer, but `abstained` reflects what the
            # app would actually do.
            if baseline:
                # Naive path: no router, no synonym bridge, no BM25/RRF, no MMR,
                # no parent-document expansion — the question embedding straight
                # into the vector store.
                routed = False
                query_embedding = embedder.embed_texts([case.question])[0]
                results = store.search(
                    workspace_id,
                    query_embedding,
                    limit=k,
                    embedding_provider=embedder.provider_name,
                    embedding_model=embedder.model_name,
                    embedding_dimension=len(query_embedding),
                )
            else:
                routed = looks_general_chat(case.question)
                results = uc._search_context(request, None)
            routed_count += routed
            best = max((r.score for r in results), default=0.0)
            abstained = routed or (not results) or best < threshold
            paths = tuple(dict.fromkeys(r.source_path for r in results))

            gen = None
            if llm is not None and not abstained:
                gen = _generate_outcome(
                    uc, request, results, best, llm, repeats, corrective=not baseline
                )

            outcomes.append(
                QuestionOutcome(
                    question_id=case.id,
                    abstained=abstained,
                    source_paths=paths,
                    best_score=best,
                    hallucinated=gen["hallucinated"] if gen else None,
                    raw_hallucinated=gen["raw_hallucinated"] if gen else None,
                    warning_codes=tuple(gen["warning_codes"]) if gen else (),
                    answer=(gen["answer"] if (gen and save_answers) else None),
                    generation_seconds=(gen["seconds"] if gen else None),
                )
            )

        cases = cases_all
        report = compute_report(label, k, cases, outcomes)
        print(f"  routed to general chat before retrieval: {routed_count}", flush=True)
        _write_reports(
            report,
            cases,
            outcomes,
            floor=floor,
            threshold=threshold,
            probe_ceiling=probe_ceiling_value,
        )
        _print_summary(report)


def _evaluate_answer(uc, request, context_results, answer):
    """Run the product's grounding evaluator over one generated answer; return its
    warnings list."""
    sources = [
        RagSource(
            chunk_id=r.chunk_id,
            source_path=r.source_path,
            score=r.score,
            preview=r.content[:200],
        )
        for r in context_results
    ]
    return evaluate_rag_answer(
        question=request.question,
        answer=answer,
        sources=sources,
        source_contents=[r.content for r in context_results],
    )


def _one_generation(uc, request, results, best_score, llm, corrective: bool = True) -> dict | None:
    """Generate one answer through the REAL product path — first the grounded
    answer, then the app's corrective regeneration pass (the same one that fires in
    production on hard grounding warnings). Returns raw vs. product warnings so the
    report can show the sieve working. None on any failure."""
    try:
        # temperature 0 for reproducibility (seed isn't plumbed through the provider;
        # greedy decoding is the reproducibility lever we have). think=False: the
        # default answer model (qwen3) is a thinking model — left to its default it
        # burns the whole token budget in Ollama's separate "thinking" field and
        # returns an EMPTY response ("did not include response text" on every
        # question, observed 2026-07-06). Grounded answers don't need chain-of-
        # thought, and the provider transparently retries without the flag on
        # models that can't think.
        request = replace(request, temperature=0.0, think=False)
        started = perf_counter()
        context_results, prompt, _m, _f, _u = uc._grounded_prompt(request, llm, results, [])
        answer, _usage = uc._generate_answer_with_usage(llm, prompt, [], 0.0, False, [])
        raw_warnings = _evaluate_answer(uc, request, context_results, answer)

        product_answer = answer
        product_warnings = raw_warnings
        # CRAG trigger (b): exactly what production runs when the answer carries hard
        # grounding warnings — one corrective retrieval + regeneration, kept only if
        # it strictly improves grounding. Measuring the product, not the raw model.
        regen = (
            uc._corrective_regeneration(request, llm, [], raw_warnings, best_score)
            if corrective
            else None
        )
        if regen is not None:
            product_answer = regen["answer"]
            product_warnings = regen["warnings"]
        # Everything the person waits for after the question is asked: the prompt
        # build, the model call, and the corrective pass when it fires.
        seconds = perf_counter() - started

        return {
            "raw_hallucinated": bool(_hard_grounding_warnings(raw_warnings)),
            "hallucinated": bool(_hard_grounding_warnings(product_warnings)),
            "warning_codes": [w.code for w in product_warnings],
            "answer": product_answer,
            "seconds": seconds,
        }
    except Exception as error:  # noqa: BLE001
        print(f"    (generation skipped for {request.question[:40]!r}: {error})", flush=True)
        return None


def _generate_outcome(
    uc, request, results, best_score, llm, repeats: int, corrective: bool = True
) -> dict | None:
    """Generate ``repeats`` times and fold into one outcome. The boolean flags are a
    majority vote across runs (ties count as flagged — conservative), which gives a
    stable label under generation non-determinism; the last run's answer/codes are
    kept for eyeballing. None if every run failed."""
    runs = [
        r
        for r in (
            _one_generation(uc, request, results, best_score, llm, corrective=corrective)
            for _ in range(max(1, repeats))
        )
        if r
    ]
    if not runs:
        return None
    n = len(runs)
    raw_votes = sum(1 for r in runs if r["raw_hallucinated"])
    prod_votes = sum(1 for r in runs if r["hallucinated"])
    last = runs[-1]
    seconds = sorted(r["seconds"] for r in runs)[n // 2]
    return {
        "raw_hallucinated": raw_votes * 2 >= n,
        "hallucinated": prod_votes * 2 >= n,
        "warning_codes": last["warning_codes"],
        "answer": last["answer"],
        "seconds": seconds,
    }


def _out_dir() -> Path:
    # backend/eval/golden.py -> repo root -> build/notes/eval
    root = Path(__file__).resolve().parents[2]
    out = root / "build" / "notes" / "eval"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_reports(report, cases, outcomes, floor=None, threshold=None, probe_ceiling=None) -> None:
    """Write JSON + markdown. ``floor``/``probe_ceiling``/``threshold`` are recorded
    in both — the P5/P8 verdict needs them next to the scores, not just in the
    console scrollback."""
    out = _out_dir()
    stamp = datetime.now().strftime("%Y-%m-%d")
    base = f"golden_{report.embedder}_{stamp}"
    data = report_to_dict(report, cases, outcomes)
    if floor is not None:
        data["relevance_floor"] = floor
    if probe_ceiling is not None:
        data["relevance_probe_ceiling"] = round(probe_ceiling, 4)
    if threshold is not None:
        data["threshold"] = round(threshold, 4)
    (out / f"{base}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    md = render_markdown(report, cases, outcomes)
    if threshold is not None:
        ceiling_note = (
            f" · probe ceiling: **{probe_ceiling:.3f}**" if probe_ceiling is not None else ""
        )
        md = md.replace(
            "\n\n",
            f"\n\n- Calibrated floor: **{floor}**{ceiling_note} → "
            f"abstention threshold: **{threshold:.3f}**\n",
            1,
        )
    (out / f"{base}.md").write_text(md, encoding="utf-8")
    print(f"  wrote {out / base}.json / .md", flush=True)


def _print_summary(report) -> None:
    if report.overall_raw_hallucination_rate is not None:
        halluc = f"halluc={_p(report.overall_raw_hallucination_rate)}→{_p(report.overall_hallucination_rate)}"
    else:
        halluc = f"halluc={_p(report.overall_hallucination_rate)}"
    print(
        f"  hit@{report.k}={_p(report.overall_retrieval_hit_at_k)} "
        f"overblock={_p(report.overall_overblock_rate)} "
        f"should-abstain={_p(report.overall_should_abstain_accuracy)} "
        f"{halluc}",
        flush=True,
    )


def _p(v) -> str:
    return "—" if v is None else f"{v * 100:.1f}%"


def main(argv=None) -> int:
    # The packaged backend raises its open-file limit during FastAPI lifespan
    # startup and the test suite mirrors it in conftest — but this runner is a
    # bare CLI, so it kept the macOS default of 256 fds. A multi-embedder run
    # exhausted them (observed 2026-07-07: sqlite 'unable to open database file'
    # on the second embedder, then Errno 24 in tempdir cleanup). Mirror production
    # here too.
    from app.config.fd_limit import raise_fd_limit

    raise_fd_limit()
    parser = argparse.ArgumentParser(description="Golden-set retrieval eval")
    parser.add_argument("--embedder", choices=sorted(EMBEDDERS), help="which embedder to run")
    parser.add_argument("--all", action="store_true", help="run all embedders in turn")
    parser.add_argument(
        "--set",
        dest="question_set",
        choices=sorted(QUESTION_SETS) + sorted(EXTERNAL_SETS),
        default="app",
        help="which labelled question set to run: 'app' (this repository, default), "
        "'acme' (the demo under build/demo-project), or an external corpus "
        f"({', '.join(sorted(EXTERNAL_SETS))}) — external corpora are cloned/generated "
        "on first use under build/eval-corpora at a pinned commit (see eval/corpora.py). "
        "The report is suffixed with the set name so runs sit side by side.",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="run the same questions as a NAIVE local RAG on the same index: plain "
        "dense top-k, fixed 0.30 threshold instead of the calibrated floor, no "
        "keyword search / synonym bridge / RRF / MMR / parent expansion, no small-talk "
        "router, and no corrective pass under --with-generation. The report is "
        "suffixed '-baseline'; the delta against the ordinary run is the pipeline's "
        "measured value on that corpus.",
    )
    parser.add_argument(
        "--role",
        choices=("developer", "devops", "tester", "business_analyst", "manager", "dba"),
        default=None,
        help="run with this workspace role's lens hint in the generation prompt. "
        "Retrieval metrics must not move (the role lives in the prose, not the "
        "search) — this flag exists to prove exactly that.",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="target repo path (default: the repo the chosen --set is written against)",
    )
    parser.add_argument("--k", type=int, default=5, help="top-k for retrieval (default 5)")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument(
        "--backend",
        choices=("ollama", "llamacpp"),
        default="ollama",
        help="embedding backend (default ollama). 'llamacpp' talks to a running "
        "llama-server embed endpoint — start the app's llama engine on the matching "
        "model first; the report is labelled '<embedder>-llamacpp' so the two backends "
        "can be compared side by side (do the floors agree?)",
    )
    parser.add_argument(
        "--llama-embed-url",
        default="http://127.0.0.1:8081",
        help="llama-server embedding endpoint (used only with --backend llamacpp)",
    )
    parser.add_argument(
        "--with-generation",
        nargs="?",
        const="qwen3:4b",
        default=None,
        help="also generate answers with this Ollama LLM and measure the grounding-"
        "warning rate raw vs. after the corrective pass (default model qwen3:4b — the "
        "app's recommended answer model — if the flag is given without a value)",
    )
    parser.add_argument(
        "--gen-backend",
        choices=("ollama", "llamacpp"),
        default="ollama",
        help="which engine GENERATES the answers (default ollama). The app ships two "
        "engines; a benchmark that measures only one cannot be reproduced by half our "
        "readers. 'llamacpp' talks to a running llama-server (see --llama-gen-url); the "
        "report is suffixed '-llamacpp-gen' so it sits beside the Ollama one rather "
        "than replacing it. Needs --with-generation.",
    )
    parser.add_argument(
        "--llama-gen-url",
        default="http://127.0.0.1:8080",
        help="llama-server answer endpoint (used only with --gen-backend llamacpp)",
    )
    parser.add_argument(
        "--save-answers",
        action="store_true",
        help="record each generated answer + its warning codes in the JSON report, so "
        "flagged cases can be read by hand (larger report; needs --with-generation)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="generate each answer N times and take a majority vote on the flags, to "
        "gauge spread under generation non-determinism (default 1; needs --with-generation)",
    )
    args = parser.parse_args(argv)

    if not args.all and not args.embedder:
        parser.error("pass --embedder <name> or --all")
    if (args.save_answers or args.repeats != 1) and not args.with_generation:
        parser.error("--save-answers and --repeats require --with-generation")
    if args.gen_backend == "llamacpp" and not args.with_generation:
        parser.error("--gen-backend only applies with --with-generation")

    project_root = Path(__file__).resolve().parents[2]
    # --repo wins; otherwise use the repo the chosen set is written against (the app
    # set → this repository; the acme set → build/demo-project; an external set →
    # its pinned checkout under build/eval-corpora, cloned/generated on demand).
    if args.question_set in EXTERNAL_SETS:
        question_set = EXTERNAL_SETS[args.question_set]
        repo = Path(args.repo).resolve() if args.repo else ensure_corpus(args.question_set)
    else:
        question_set, set_repo_relative = QUESTION_SETS[args.question_set]
        if args.repo:
            repo = Path(args.repo).resolve()
        elif set_repo_relative:
            repo = (project_root / set_repo_relative).resolve()
        else:
            repo = project_root
    if not repo.is_dir():
        parser.error(f"target repo not found: {repo}")

    aliases = sorted(EMBEDDERS) if args.all else [args.embedder]
    for alias in aliases:
        try:
            _run_embedder(
                alias,
                repo,
                args.k,
                args.ollama_url,
                args.with_generation,
                question_set=question_set,
                set_name=args.question_set,
                backend=args.backend,
                llama_embed_url=args.llama_embed_url,
                gen_backend=args.gen_backend,
                llama_gen_url=args.llama_gen_url,
                save_answers=args.save_answers,
                repeats=max(1, args.repeats),
                baseline=args.baseline,
                role=args.role,
            )
        except LlamaServerNotRunning as error:
            # A missing engine is a setup mistake, not a bug. Say what to start.
            print(f"error: {error}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
