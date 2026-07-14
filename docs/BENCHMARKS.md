# Benchmarks

Two layers, one rule: **every number here is reproducible from this repository
with local models — run it yourself.**

## Layer 1 — the in-repo golden set (regression suite)

A 40+-question labelled set against this repository plus a second set against
the bundled demo project (`build/demo-project`). It runs the real retrieval
pipeline end to end and gates its deterministic parts in CI. Current numbers
live in the [README](../README.md#measured-not-promised). This layer answers
"did we break retrieval?" on every change; it cannot answer "does this work on
*your* project?" — that is what layer 2 is for.

## Layer 2 — external corpora (generality suite)

Five corpora, one per project kind the app claims to understand — none of them
written by us*, all pinned to exact commits:

| Corpus | Kind | Pinned at |
| --- | --- | --- |
| [`terraform-aws-vpc`](https://github.com/terraform-aws-modules/terraform-aws-vpc) | Terraform module repository | `3ffbd46` (v6.6.1) |
| [`microservices-demo`](https://github.com/GoogleCloudPlatform/microservices-demo) | Kubernetes platform, 11 services in 5 languages | `9a4616e` |
| [`full-stack-fastapi-template`](https://github.com/fastapi/full-stack-fastapi-template) | Python backend + React frontend | `7d80b85` |
| `wiki-export` | Exported knowledge base | generated* — see below |
| mixed group | code + wiki in one group | manual protocol below |

\* The wiki corpus is the exception: a real company wiki cannot be published,
so it is a **generated** fictional one (`python -m eval.make_wiki_corpus`) with
the shape real exports have — ADR/Capability naming, cross-links, a superseded
decision, a companion asset folder. Deterministic by construction; CI pins its
content hash so it can never drift under its questions.

### The protocol

1. **Pre-registered questions.** Question sets
   ([`eval/golden_set_external.py`](../backend/eval/golden_set_external.py),
   [`golden_set_wiki.py`](../backend/eval/golden_set_wiki.py)) were written
   from reading the pinned trees and committed before the first scored run.
   They are added to or retired with an explanatory commit — never reworded to
   fit results.
2. **Pinned corpora.** `python -m eval.corpora` clones each repository at its
   exact commit into `build/eval-corpora/` (gitignored). Upgrading a pin is a
   commit that re-registers the questions.
3. **Baseline vs. pipeline.** Every corpus runs twice with the same index and
   embedder: `--baseline` (plain dense top-k, fixed 0.30 threshold, no keyword
   search, no synonym bridge, no RRF/MMR/parent expansion, no small-talk
   router, no corrective pass) and the full pipeline. The delta is the
   pipeline's measured value — per corpus, not on average.
4. **Cross-language cases.** The `app`, `acme` and `wiki-export` sets each
   carry a Ukrainian question against an English corpus, guarding the
   cross-language retrieval path and the script-aware token budgeting.
5. **Role invariance.** `--role tester` (etc.) re-runs generation with that
   role's lens hint in the prompt. Retrieval metrics must not move; the flag
   exists to prove the invariant "the role lives in the prose, not the search".
6. **The harness is stricter than the product on broad questions.** The app
   builds a handbook pseudo-document at scan time and answers "what is this
   project about?" from it; the harness indexes only the repository's own
   files, so a broad question must clear the abstention bar on raw retrieval
   alone. A wrongly-refused broad question in these tables (e.g.
   online-boutique's) may be answered fine by the product — the error is
   reported anyway rather than special-cased, because a benchmark that
   inherits every helper loses the ability to catch regressions in the layer
   it actually measures.

### Running it

```bash
cd backend
python -m eval.corpora                       # one-time: fetch pinned corpora
python -m eval.golden --embedder nomic --set tf-aws-vpc --with-generation
python -m eval.golden --embedder nomic --set tf-aws-vpc --with-generation --baseline
# …repeat per corpus; reports land in build/notes/eval/ suffixed by set/mode
```

### Mixed-group protocol (manual for now)

The group union ("what did we decide, and where is it implemented?") spans two
indexes, which the CLI harness does not drive yet. Until it does: create a
group of `wiki-export` + `fastapi-template` in the app, ask the five
cross-source questions listed in
[`eval/golden_set_wiki.py`](../backend/eval/golden_set_wiki.py) footnotes, and
record whether each answer cites at least one source from *each* member.

### Results (v2, 2026-07-14)

Config: `nomic-embed-text` + `qwen3:4b` (temperature 0), k=5, Ollama, consumer
laptop. Every row: `python -m eval.golden --embedder nomic --set <corpus>
--with-generation [--baseline]`. **Baseline** = plain dense top-k on the same
index (fixed 0.30 threshold, no hybrid search, no router, no corrective pass) —
what a naive local RAG does with identical models and questions.

| Corpus | hit@5 | wrongly refused | off-topic refused | halluc raw→corrected |
| --- | --- | --- | --- | --- |
| terraform-aws-vpc | 66.7% → **88.9%** | 0% → 0% | 0% → **100%** | 10%→10% → **0%→0%** |
| microservices-demo | 55.6% → 55.6% | 0% → 9.1%¹ | 0% → **100%** | 9.1%→9.1% → **0%→0%** |
| fastapi-template | 60.0% → **100%** | 0% → 8.3%¹ | 0% → **100%** | 8.3%→8.3% → **0%→0%** |
| wiki-export | 100% → 100% | 0% → 0% | 0% → **100%** | 36.4%→36.4% → **18.2%→9.1%** |

Each cell is baseline → pipeline. Three readings the table supports:

- **The baseline never once refused an off-topic question** — 0 of 12 across
  four corpora; a borscht recipe gets "sources" from a Terraform module. The
  pipeline refused all 12.
- **Baseline hallucination warnings go uncorrected by construction** (there is
  no corrective pass to run); the pipeline's corrective regeneration takes the
  wiki corpus from 18.2% to 9.1% and every code corpus to 0%.
- ¹ The two wrongly-refused questions are both "what is this project about?" —
  the broad class the product answers from its scan-time handbook, which the
  harness deliberately does not build (protocol point 6). The strictness is
  reported, not special-cased.

**What the first run found (v1 → v2).** The v1 run of this benchmark found
three product bugs; they were fixed and the whole suite re-run — both columns
are kept because "found and fixed" is the claim, not first-try perfection:

| Bug found by v1 | v1 | v2 |
| --- | --- | --- |
| Abstention threshold could sit *below* the chit-chat ceiling | microservices-demo off-topic refusal 33.3% | 100% |
| Generated code indexed as if a person wrote it (protobuf stubs beat the real `.proto`; then Python stubs slipped a type check) | 1266 chunks, stubs in top-5 | 674 chunks, stubs gone |
| Small-talk router missed whole categories (creative requests, market prices, sign-offs) | 0 of 3 routed on microservices-demo | 3 of 3 routed before retrieval |

In-repo suites on the same day, same config: `app` (41 questions, 4 775
chunks) 95.2% hit@5, 100% off-topic refusal, hallucination 3.3%→0%; `acme`
94.4% / 100% / 9.5%→0%. Role invariance held on live runs: `--role tester`
and `--role manager` reproduce the no-role retrieval metrics digit for digit
(94.4 / 4.5 / 100) — the role lives in the prose, not the search.

Footnote on coverage: one terraform-aws-vpc answer (`vpc-pp-endpoints`)
exceeded the runner's 360 s generation timeout on the test machine in both v1
and v2; its retrieval metrics are counted, its generation is not. Reported
rather than retried until it fit.
