# Releasing and auto-updating (free, no paid certificates)

This describes the **free** distribution and auto-update setup for AI Private
Workspace, built on Tauri v2's updater + GitHub Releases. No paid code-signing
certificates are required. The only accepted trade-off is the first-launch
Gatekeeper/SmartScreen prompt (see "The free trade-off" at the bottom).

> Why a runbook and not committed code: the steps below change the desktop build
> and need your **private signing key** and a local `cargo build` / `npm install`
> to validate. Those can't be done safely from a sandbox, so apply them locally —
> each step is copy-paste. The release CI workflow (`.github/workflows/release.yml`)
> is already in the repo and stays inert until you push a tag and add the secrets.

## How an update works (the flow)

1. You bump the app version and push a git tag like `v0.2.0`.
2. GitHub Actions (`release.yml`) builds the macOS + Windows bundles, builds the
   frozen Python backend into each one, **signs the update with your private key**,
   and publishes the installers plus a `latest.json` manifest to a GitHub Release.
3. Each installed app, on launch, fetches `latest.json` from the release URL.
4. If the manifest version is newer, the app downloads the new bundle, **verifies
   the signature against the public key baked into the app** (rejects anything not
   signed by you), and installs it.
5. The update applies on the next launch. The downloaded AI model is **not**
   re-downloaded — only the app bundle (tens of MB) changes.

Security note: the updater signature is mandatory and cannot be disabled. Keep the
**private key secret**. If you lose it, you can't ship updates to already-installed
apps, so back it up.

## One-time setup

### 1. Generate the update signing keypair (free)

```bash
cd frontend
npm install   # if not already
npm run tauri signer generate -- -w ~/.tauri/ai-private-workspace.key
```

This prints (and saves) a **private key** and a **public key**. The private key is
protected by a password you choose.

- Keep the private key file + password safe and backed up.
- Copy the **public key** string for the next step.

### 2. Add the GitHub repository secrets

In your GitHub repo → Settings → Secrets and variables → Actions, add:

- `TAURI_SIGNING_PRIVATE_KEY` — the **contents** of the private key file.
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` — the password you chose.

### 3. Enable the updater in `frontend/src-tauri/tauri.conf.json`

Add the `plugins.updater` block and turn on updater artifacts. Replace
`<OWNER>/<REPO>` with your GitHub repo and `<PUBLIC_KEY>` with the public key from step 1:

```jsonc
{
  // ...existing config...
  "bundle": {
    "active": true,
    "createUpdaterArtifacts": true,   // <-- add this
    "targets": ["app", "dmg", "nsis"], // app+dmg for macOS, nsis installer for Windows
    // ...rest unchanged...
  },
  "plugins": {
    "updater": {
      "endpoints": [
        "https://github.com/<OWNER>/<REPO>/releases/latest/download/latest.json"
      ],
      "pubkey": "<PUBLIC_KEY>"
    }
  }
}
```

### 4. Add the updater plugin to the Rust shell

In `frontend/src-tauri/Cargo.toml` under `[dependencies]`:

```toml
tauri-plugin-updater = "2"
tauri-plugin-process = "2"   # used to relaunch after installing
```

In `frontend/src-tauri/src/lib.rs`, register the plugins on the builder
(right after `tauri::Builder::default()`):

```rust
let app = tauri::Builder::default()
    .plugin(tauri_plugin_updater::Builder::new().build())
    .plugin(tauri_plugin_process::init())
    .invoke_handler(tauri::generate_handler![
        // ...existing handlers...
    ])
    // ...rest unchanged...
```

Then verify the Rust side compiles:

```bash
cd frontend/src-tauri && cargo build
```

### 5. Check for updates on launch (frontend)

Install the JS bindings and add a check. From `frontend/`:

```bash
npm install @tauri-apps/plugin-updater @tauri-apps/plugin-process
```

Add a small helper and call it once on app start (e.g. in `App.tsx` inside a
`useEffect`):

```ts
import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";

export async function checkForUpdates() {
  try {
    const update = await check();
    if (update) {
      // Optionally show your own "Update available" UI here first.
      await update.downloadAndInstall();
      await relaunch();
    }
  } catch {
    // Offline or no update server reachable — ignore and keep running.
  }
}
```

If the JS `check()` is blocked by permissions, add a capability file
`frontend/src-tauri/capabilities/updater.json`:

```json
{
  "identifier": "updater",
  "windows": ["main"],
  "permissions": ["updater:default", "process:allow-restart"]
}
```

(Alternatively, run the check from Rust in a `.setup()` hook — see the Tauri
updater docs linked below — which needs no webview permission.)

## Per-release flow (every time you ship)

1. Bump the version in **both** `frontend/src-tauri/tauri.conf.json` and
   `frontend/package.json` (e.g. `0.1.0` → `0.2.0`). Keep them in sync.
2. Commit, then tag and push:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
3. GitHub Actions builds, signs, and publishes the release + `latest.json`.
4. Installed apps pick up the update automatically on their next launch.

That's the whole loop: **tag → CI → users auto-update.**

## The free trade-off (macOS / Windows without paid certificates)

- **Windows:** works fully. First launch shows a SmartScreen "unknown publisher"
  prompt → "More info" → "Run anyway". Auto-updates work after that.
- **macOS:** the app is unsigned, so the first open requires the user to
  right-click the app → **Open** (or System Settings → Privacy & Security →
  "Open Anyway"). Document this in your README. Note that unsigned macOS
  auto-updates can be unreliable; if macOS friction becomes a real barrier, a
  $99/yr Apple Developer ID is the single change that removes it.

## References

- Tauri v2 Updater plugin: https://v2.tauri.app/plugin/updater/
- Tauri GitHub Action: https://github.com/tauri-apps/tauri-action
