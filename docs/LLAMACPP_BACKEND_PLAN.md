# Ollama-free local backend (llama.cpp)

Goal: the app must not depend on Ollama being installed. The user picks a local
runtime on the setup screen:

- **Ollama** — if it is installed, pull the LLM + embedding model through it
  (current behaviour).
- **llama.cpp** — a self-contained path that needs no third-party install: the
  app talks to a bundled `llama-server` (HTTP), and downloads small GGUF model
  files on first use.

## Why bundle the binary but download only the models

There are two very different kinds of artifact:

- The **`llama-server` binary** is executable code and is architecture-specific
  (arm64 vs x86_64, Metal). It should be **bundled inside the signed/notarized
  app**, not downloaded at runtime. Downloading and launching an unsigned
  executable at runtime hits macOS Gatekeeper (the same "app is damaged" block
  the app itself faces), is a real trust/security concern, and undercuts the
  project's safety story. The release workflow already builds for both macOS
  arches, so shipping the matching binary per build is cheap.
- The **model weights (GGUF)** are plain data, run on any architecture, and are
  safe to download at runtime — exactly like Ollama pulling a model. These are
  what we fetch on first use, with progress, into the app data dir.

So "download what's needed for this laptop" resolves to: the per-arch binary is
already in the app; only the (arch-agnostic) model files are downloaded.

## Model naming

Ollama uses registry tags (`llama3.2`). llama.cpp has no registry — it loads a
GGUF file identified by a Hugging Face `repo_id` + filename + quant, e.g.
`bartowski/Llama-3.2-3B-Instruct-GGUF` / `Llama-3.2-3B-Instruct-Q4_K_M.gguf`.
A curated catalog maps one friendly name ("Llama 3.2 3B") to **both** an Ollama
tag and a GGUF spec, so the UI stays "pick a model" regardless of backend.
Advanced users can still paste a custom Ollama tag, or a HF repo+file for GGUF.

## Architecture (fits the existing ports/adapters)

- `LLMProviderPort` already abstracts the model. **Done:**
  `LlamaServerLLMProvider` (HTTP to `llama-server` `/v1/chat/completions`,
  generate + SSE streaming) and factory registration under provider `llamacpp`.
- A **backend selector**: `ollama` if reachable and chosen, else `llamacpp`.
  Surfaced as a choice on the setup screen + a persisted preference.
- **GGUF catalog**: extend model catalog entries with `{repo_id, filename}`.
- **GGUF download**: download the file from Hugging Face into the app data dir
  with progress (mirrors the existing Ollama download-job UX). Data only.
- **Embeddings without Ollama**: `llama-server` can serve embeddings in
  `--embedding` mode. Because one server process loads one model, the LLM and
  the embedding model run as two `llama-server` processes on two ports.
- **Process management**: a runtime manager starts/stops `llama-server` with the
  selected GGUF (the desktop shell owns this, like it owns the backend process).

## Status

- [x] `LlamaServerLLMProvider` + factory wiring (`provider = "llamacpp"`).
- [x] GGUF catalog (`gguf_catalog.py`): curated models with HF repo/file, sizes,
      and matching Ollama tags; `GET /models/gguf-catalog`.
- [x] GGUF downloader (`GgufDownloaderPort` + `HuggingFaceGgufDownloader`):
      streams to a `.part` temp file, atomic rename on success, progress +
      cancellation. `DownloadGgufModelUseCase` resolves a catalog id or a custom
      repo/file, is idempotent, and reports installed state.
- [x] Background download **job** (threaded, pollable progress + cancel):
      `GgufDownloadJob` + `GgufDownloadJobRunner`; `POST /models/gguf-downloads`,
      `GET /models/gguf-downloads/{id}`, `POST .../cancel`. Frontend client +
      types added. Default first-run LLM is Llama 3.2 3B Q4 (~2 GB), not 8 GB.
- [ ] Settings/env for `llama-server` base URL + default model.
- [ ] Backend-selection preference + setup-screen choice (Ollama vs llama.cpp) —
      next: a toggle on the setup models step; the llama.cpp path drives the
      GGUF download job + progress via the endpoints above.
- [ ] Embedding provider via a second `llama-server --embedding` process.
- [ ] Bundle `llama-server` per arch in the macOS build; runtime process manager.

The last item (bundling + launching the native binary, Metal, packaging) cannot
be built or tested in the cloud sandbox — it is finished and verified on macOS.
