# Bundling and running `llama-server` (llama.cpp)

The Ollama-free backend talks to a local `llama-server`. The binary is **bundled
with the app** (per architecture, covered by the app's signature); only GGUF
model files are downloaded at runtime. Do the steps in order — validate the
provider against a local `llama-server` first, then bundle.

## 1. Validate the provider locally (no bundling yet)

This proves `LlamaServerLLMProvider` works end-to-end before any packaging.

```bash
# a) Install llama.cpp just for testing (Homebrew ships llama-server).
brew install llama.cpp

# b) Get a small GGUF (the catalog default ~2 GB). Either let the app's
#    GGUF download job fetch it, or grab it directly:
mkdir -p ~/llm-test && cd ~/llm-test
curl -L -o llama3.2-3b.gguf \
  "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"

# c) Run the server (answers on :8080). --jinja applies the model's own chat
#    template so turns end cleanly and special tokens are not emitted as text.
llama-server -m ~/llm-test/llama3.2-3b.gguf --host 127.0.0.1 --port 8080 -c 4096 --jinja
```

In a second terminal, test the app's provider against it:

```bash
cd backend
python - <<'PY'
from app.adapters.llm.llama_server_llm_provider import LlamaServerLLMProvider
p = LlamaServerLLMProvider(base_url="http://127.0.0.1:8080", model="llama3.2")
print(p.generate("Say hello in one short sentence."))
print("STREAM:", "".join(p.generate_stream("Count to three.")))
PY
```

For embeddings, run a second server with `--embedding`:

```bash
llama-server -m ~/llm-test/nomic-embed.gguf --host 127.0.0.1 --port 8081 --embedding
```

If both answer, the code path is correct and only packaging remains.

## 2. Bundle the binary in the macOS build

1. Download the prebuilt macOS binaries from the llama.cpp GitHub releases
   (`ggml-org/llama.cpp`), for both arches:
   - `llama-bXXXX-bin-macos-arm64.tar.gz` (Apple Silicon)
   - `llama-bXXXX-bin-macos-x64.tar.gz` (Intel)
   Each archive contains `llama-server` **plus its `.dylib`s** — keep them together.
2. Place them under a build resource dir, e.g.
   `build/desktop/llama-runtime/<arch>/` (alongside the frozen backend runtime).
3. Add that dir to `frontend/src-tauri/tauri.conf.json` → `bundle.resources`
   (next to the existing `frozen-backend-runtime` resource), so it ships inside
   the `.app`.
4. Code-sign the nested binary/dylibs during the macOS build (the app is
   notarized; nested executables must be signed too, with the hardened runtime).
5. Point the backend at it: set `LLAMA_SERVER_BINARY_PATH` to the bundled path.
   `LlamaServerProcessManager` then launches `llama-server -m <gguf> --port …`,
   health-checks `/health`, and `LlamaServerLLMProvider` talks to it.

## 3. Wiring (backend, after the binary is in place)

- On choosing the llama.cpp backend: ensure the GGUF LLM (and embedding) models
  are downloaded (the `gguf-downloads` job), then `LlamaServerProcessManager`
  starts one server for the LLM (`:8080`) and one with `--embedding` (`:8081`).
- Set `LLM_PROVIDER=llamacpp` (and the embedding provider equivalent) so the
  factory builds `LlamaServerLLMProvider` against those ports.
- The desktop shell stops the servers on app quit (like it owns the backend).

Until step 2 is done, the setup-screen llama.cpp option would download models but
have nothing to serve them — which is why the UI toggle is wired only after the
binary is bundled and `LlamaServerProcessManager` can start it.
