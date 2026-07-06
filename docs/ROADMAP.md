# Roadmap

Directional, not a release commitment. Four constraints hold through every
phase: local-first (no cloud, no telemetry), explicit user actions (nothing
runs on its own), read-only analysis (the app never changes your project),
and clean ports-and-adapters boundaries.

The task-by-task history that used to live in this file is preserved in git
history and [`CHANGELOG.md`](../CHANGELOG.md); this document only looks forward
from the current release.

## Where the product is today (v0.4)

A packaged desktop app for macOS (Apple Silicon + Intel) and Windows x64,
built and released from CI with auto-update, SHA256 checksums, an SPDX SBOM,
and a published test report. Shipped and working day to day:

- Two local engines: built-in llama.cpp (bundled `llama-server`, GGUF catalog
  + downloads) and Ollama, switchable per project; answer and embedding models
  managed separately.
- Hybrid retrieval (dense + BM25 + synonym bridge → RRF → diversity → optional
  cross-encoder rerank → parent-document expansion) with a per-index calibrated
  abstention floor, small-talk routing, small-project full-context mode, and a
  one-shot corrective retrieval/regeneration pass.
- Deterministic anti-hallucination checks (groundedness, quote verification)
  with honest abstention, plus an experimental schema-constrained citations
  mode behind a flag.
- Project intelligence: evidence-backed map with role lenses, CI/CD and
  environment views, security review, git activity, project memory with
  guardrails, change journal, starter questions, and the Investigator — a
  bounded ReAct agent whose steps stream live.
- A reproducible 40-question golden-set benchmark (`backend/eval/`) measuring
  retrieval, abstention, and generation grounding end to end; its
  deterministic classifiers are pinned in CI. Current numbers are in the
  README ("Measured, not promised").
- 1,000+ deterministic backend tests on every push; SQLite (WAL) persistence
  throughout, including the vector index.

## Near term (v0.5)

Quality you can trust on projects that are not this repository:

1. **External golden-set** — a second labelled question set against the
   bundled demo project (and later a real third-party repo), so thresholds
   and retrieval are validated where self-eval can't be trusted; the
   config-key question class moves there.
2. **Benchmark cadence** — refresh the README numbers on each minor release;
   compare Ollama vs built-in llama.cpp embedding paths once
   (`--backend llamacpp`) to retire the proxy caveat.
3. **Background contextual enrichment** (flagged off by default) — LLM-written
   locator notes for markdown and orphan chunks, applied incrementally after
   indexing, so the index quietly improves without blocking first use.
4. **Structured-citations A/B** — decide from real answers whether the
   schema-constrained mode graduates from experiment to Deep-dive default.
5. Continued first-session polish: verify starter questions, project-type
   detection, and reset-to-recommended behavior on fresh machines.

## Road to 1.0

- Code signing and notarization for macOS; a signed Windows installer — the
  single biggest onboarding friction today.
- Windows parity QA at the same depth as macOS.
- Performance headroom on weak hardware (8 GB, no GPU): indexing throughput,
  model recommendations that respect RAM honestly.
- Persistent background jobs across restarts.
- Sandboxed agent/MCP execution as explicit, approval-based product flows.
- Broader QA sweep and the [v1 completion roadmap](V1_PRODUCT_COMPLETION_ROADMAP.md).

## Later and explorations

- Config-aware retrieval extended beyond json/yaml key names.
- More analyzers and user-defined skill/analyzer plugins.
- Team-facing exports: shareable project reports and summaries.
- Watched, not built (revisit when local runtimes make them cheap): late
  chunking, LLM-driven retrieval, full GraphRAG/RAPTOR hierarchies.
- Optional integrations (git providers, extra vector stores) behind explicit
  configuration and consent.
