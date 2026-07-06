# Golden-set retrieval eval

Measures how well an embedding model retrieves the right files for a labelled set
of questions, so the choice of default embedder (**P5**) and the abstention floor
rest on numbers, not vibes. Runs the **real** retrieval path (hybrid dense + BM25
→ RRF → per-file cap → MMR → parent-document expansion → calibrated floor), so the
numbers reflect what Ask actually does.

## Run it

From the `backend/` directory, with [Ollama](https://ollama.com) running and the
embedding models pulled:

```bash
ollama pull nomic-embed-text
ollama pull qwen3-embedding:0.6b
ollama pull bge-m3

python -m eval.golden --embedder nomic
python -m eval.golden --embedder qwen3
python -m eval.golden --embedder bge-m3
# or all three in one go:
python -m eval.golden --all
```

Each run indexes this repository with the chosen embedder into a throwaway SQLite
store, runs the question set, and writes a report to `build/notes/eval/`:

- `golden_<embedder>_<date>.json` — full per-question detail
- `golden_<embedder>_<date>.md` — summary table + the failures to eyeball

### Options

- `--repo /path/to/other/repo` — index a different repo. Note the shipped question
  set is written against *this* repo; point it elsewhere only with a matching set.
- `--k N` — top-k for retrieval-hit (default 5).
- `--with-generation [model]` — also generate answers with an Ollama LLM and
  measure `hallucination_rate` (hard grounding warnings). Slower; skip it for a
  pure embedder comparison. Default model `qwen2.5-coder`.
- `--ollama-url http://host:port` — non-default Ollama endpoint.

## What it measures

| Metric | Meaning | Good |
|---|---|---|
| `retrieval_hit@k` | for `project_precise` Qs, did a labelled file appear in top-k | high |
| `overblock_rate` | project Qs wrongly routed to "no context" (abstained) | low |
| `should_abstain_accuracy` | non-project Qs correctly returned 0 sources | high |
| `hallucination_rate` | (with `--with-generation`) answers with hard grounding warnings | low |

## Question classes (`eval/golden_set.py`)

- **project_precise** — a specific answer lives in specific file(s); `expected_paths`
  labels them (matched as path substrings).
- **project_broad** — "about the whole project"; any grounded answer counts (these
  lean on the handbook pseudo-document).
- **should_abstain** — NOT about the project (chit-chat, world facts, time). The
  right behaviour is to abstain with zero sources. Includes the live regression
  **"what time is it"**, which on nomic wrongly scored above the 0.38 cap and came
  back grounded with sources — this set is where we watch that.

## Interpreting for P5

Compare the three reports: the embedder with the best `retrieval_hit@k` **and** low
`overblock_rate` **and** high `should_abstain_accuracy` wins. If an embedder's
`should_abstain_accuracy` is low, its calibrated floor (printed at run start) may
need the cap revisited — that's the P5 + threshold decision.

The `harness.py` scoring is pure and unit-tested (`tests/test_eval_harness.py`);
only `golden.py` touches Ollama and the filesystem.
