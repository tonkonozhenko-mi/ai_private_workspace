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

### Results

*To be published from the first full run (see the run plan in
`build/notes/`). The table will hold, per corpus: hit@5, wrongly-refused,
off-topic refusal, grounding-warning rate raw → corrected — for baseline and
full pipeline side by side, with the exact command that produced each row.*
