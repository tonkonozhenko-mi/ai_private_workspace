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
6. **Adversarial cases, and what "abstain" means for them.** The wiki set
   carries pre-registered traps: a question with a false premise ("why did we
   choose Kafka?" — RabbitMQ was chosen), a premise from a superseded decision,
   a technology the corpus never mentions, and a chimera fusing entities from
   two unrelated pages. For the last two the correct outcome is *no
   fabrication* — and there are two honest ways to deliver it: refuse at the
   retrieval threshold, or answer with an explicit "the files do not contain
   this". Both count as should-abstain success; an answer counts only when it
   carries no fabrication signals (invented files or terms). It is not
   penalised for citing nothing — an honest negative has nothing to cite.
   *Honest ≠ correct*, and the class design keeps them apart structurally: an
   honest "not found" on a question whose answer IS in the corpus lands in the
   precise class and scores as a miss; honest-negative credit exists only in
   the abstain class, where absence is guaranteed by pre-registration.
7. **The scoring is guarded against itself.** A leakage audit checks that no
   pre-registered question appears in the product's runtime strings; it found
   (and this file records) one real coupling — three should-abstain questions
   were near-verbatim copies of the product's own calibration probes, i.e. the
   abstention threshold was being tested on its calibration input. All three
   were retired and replaced (2026-07-15) with questions from unrelated router
   categories; the coupling had been inert in the published numbers (every
   affected question was routed before the threshold), but inert is not the
   same as absent. And the fabrication detector is mutation-tested: grounded
   citations are programmatically corrupted (typos, plurals, wrong extensions,
   phantom versions, cross-corpus files) and the suite gates on **100%
   fabrication recall together with 0% false positives on the originals** — a
   change that buys one at the other's expense fails CI. Shared *phrasing*
   between the benchmark and the app's starter-question suggestions is
   deliberate and harmless: the benchmark asks what the product invites users
   to ask, and a UI suggestion string cannot raise a retrieval score.
8. **The harness is stricter than the product on broad questions.** The app
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

The app ships two engines, so the benchmark runs on both. The tables above were
generated on Ollama; to reproduce them on llama.cpp, start the app's engine (or
`llama-server` on your answer model) and add `--gen-backend llamacpp`:

```bash
python -m eval.golden --embedder nomic --set tf-aws-vpc --with-generation \
  --gen-backend llamacpp --llama-gen-url http://127.0.0.1:8080
# report: golden_nomic-llamacpp-gen-tf-aws-vpc_<date>.md — beside the Ollama one,
# never over it. Both runs record how long each answer took (median and worst),
# so "one question is slow" is a number rather than a shrug.
```

### Mixed-group protocol (manual for now)

The group union ("what did we decide, and where is it implemented?") spans two
indexes, which the CLI harness does not drive yet. Until it does: create a
group of `wiki-export` + `fastapi-template` in the app, ask the five
cross-source questions listed in
[`eval/golden_set_wiki.py`](../backend/eval/golden_set_wiki.py) footnotes, and
record whether each answer cites at least one source from *each* member. An
explicit, correct "the code has no such thing" counts for the code side —
absence cannot be cited.

**Run of 2026-07-14 (same config as the tables above): 4 of 5 pass.**

| Question | Verdict | Notes |
| --- | --- | --- |
| report storage | pass | ADR cited; honest "not configured in the backend". But the answer presented the *superseded* ADR-05 as current — the trap the corpus carries by design; the page's own "Superseded by ADR-08" status was in context and ignored (finding 1). |
| queue decision vs. code | pass | ADR-03 cited; honest "no queue code" — correct for this template. |
| tenant isolation | pass | Best of the five: RLS/`tenant_id` from the wiki, SQLAlchemy note from `backend/README` — both members in one answer. |
| onboarding starting point | pass | Wiki onboarding page cited; "start at `main.py`" for the code side. |
| retention rules in code | **half** | Wiki cited, but audit-event retention (seven years) was merged into the logs' 30 days — a compression error of exactly the kind the halluc metric counts — and the code side hedged ("needs investigating") instead of an honest negative (finding 2). |

Both findings are generation-layer, not retrieval (the right pages were on the
table): (1) a source marked superseded should be flagged as such and its
successor preferred; (2) a hedge is worse than an honest "not implemented
here". Queued as prompt-layer work; the answers above are reported as they
came.

**Follow-up (2026-07-15).** Both findings were fixed and re-verified live, and
the chain of fixes the trap set off is itself part of the record: marking a
superseded source in the prompt made the model invent its successor's content,
so the app now *fetches* the successor deterministically (the page names it) —
in single workspaces and per group member; the invented-file detector that
episode motivated then flagged honest wiki answers, because it truncated
bracketed filenames, treated the prompt's own `main.tf` example — which had
seeded the one real fabrication — as an invention, and judged the model's
inline draft instead of the answer the person reads. The citation example is
now an obvious placeholder, and every grounding check runs on the visible
answer only. Re-asking the trap question: the answer cites ADR-08 from
sources, names ADR-05 as superseded, and gives an honest negative for the
code side. wiki-export after these fixes: hit@5 100%, off-topic refusal 100%,
hallucination-warning rate 0%→0% at `--repeats 3`.

**Adversarial first run (2026-07-15, evening).** The four pre-registered traps
(protocol point 6) went in and the whole 18-question wiki set was re-run at
`--repeats 3`: **100% hit@5, 0% wrongly refused, 100% should-abstain, 0%→0%
hallucination warnings.** The false premise was corrected in words ("We did
not choose Kafka; we chose RabbitMQ…"), the stale premise was corrected
through the supersession pointer (the successor ADR is what got cited), and
both unanswerable questions received explicit honest negatives — which the
first scoring pass counted as failures, until reading the answers showed the
metric, not the model, was wrong; the honest-negative rule in point 6 is the
result. Traps that only ever catch the subject are decoration; these have now
caught the model, the prompt, the detector and the scoring — once each.

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
  harness deliberately does not build (protocol point 8). The strictness is
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

Follow-up with the timing instrumentation (2026-07-15, same machine, same
models): the timeout did not reproduce on either engine — the question
completed in ordinary time, so the tail was engine state, not the question.
Steady-state generation on this corpus: Ollama median 41.3 s, worst 126.2 s;
llama.cpp median 25.5 s, worst 43.2 s. Retrieval metrics were identical across
both engines, digit for digit. At `--repeats 1` the hallucination flag showed
run-to-run variance of ±1 question (a different single answer flagged per
engine) — the `--repeats N` majority vote exists for exactly this; the tables
above are single runs and say so.
