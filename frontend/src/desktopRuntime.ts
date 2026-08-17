export interface DesktopBackendStartupResult {
  state: string;
  runtime_kind: string;
  pid?: number | null;
  health_url: string;
  backend_start_enabled: boolean;
  data_directory: string;
  logs_directory: string;
  backend_log: string;
  message: string;
}

type TauriInvoke = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

type CloseRequestedHandler = (event: { preventDefault: () => void }) => void;

interface TauriWindowHandle {
  onCloseRequested?: (
    handler: (event: { preventDefault: () => void }) => void | Promise<void>,
  ) => Promise<() => void>;
  destroy?: () => Promise<void>;
  close?: () => Promise<void>;
}

interface TauriGlobal {
  core?: {
    invoke?: TauriInvoke;
  };
  tauri?: {
    invoke?: TauriInvoke;
  };
  window?: {
    getCurrentWindow?: () => TauriWindowHandle;
  };
}

interface TauriInternalsGlobal {
  invoke?: TauriInvoke;
}

function tauriInvoke(): TauriInvoke | null {
  const maybeWindow = window as typeof window & {
    __TAURI__?: TauriGlobal;
    __TAURI_INTERNALS__?: TauriInternalsGlobal;
  };
  return (
    maybeWindow.__TAURI__?.core?.invoke
    ?? maybeWindow.__TAURI__?.tauri?.invoke
    ?? maybeWindow.__TAURI_INTERNALS__?.invoke
    ?? null
  );
}

export function tauriBridgeDiagnostic(): string {
  const maybeWindow = window as typeof window & {
    __TAURI__?: TauriGlobal;
    __TAURI_INTERNALS__?: TauriInternalsGlobal;
  };
  if (maybeWindow.__TAURI__?.core?.invoke) {
    return "window.__TAURI__.core.invoke";
  }
  if (maybeWindow.__TAURI__?.tauri?.invoke) {
    return "window.__TAURI__.tauri.invoke";
  }
  if (maybeWindow.__TAURI_INTERNALS__?.invoke) {
    return "window.__TAURI_INTERNALS__.invoke";
  }
  return "no-tauri-invoke-bridge";
}

export function isRunningInsideTauri(): boolean {
  return tauriInvoke() !== null;
}

export async function chooseProjectDirectory(): Promise<string | null> {
  const invoke = tauriInvoke();
  if (!invoke) {
    return null;
  }

  return invoke<string | null>("choose_project_directory");
}

/**
 * Open the native file picker filtered to .gguf model files. Returns the chosen
 * absolute path, or null when cancelled or when not running inside the desktop
 * shell (the web dev server has no native picker — the caller falls back to a
 * pasted path).
 */
export async function chooseGgufFile(): Promise<string | null> {
  const invoke = tauriInvoke();
  if (!invoke) {
    return null;
  }

  return invoke<string | null>("choose_gguf_file");
}

function currentTauriWindow(): TauriWindowHandle | null {
  const maybeWindow = window as typeof window & { __TAURI__?: TauriGlobal };
  const getCurrentWindow = maybeWindow.__TAURI__?.window?.getCurrentWindow;
  if (!getCurrentWindow) {
    return null;
  }
  try {
    return getCurrentWindow();
  } catch {
    return null;
  }
}

/**
 * Register a guard that runs when the user tries to close the desktop window.
 * The handler may call event.preventDefault() to keep the window open (e.g. to
 * show a confirmation). Returns an unlisten function, or null when not running
 * inside the desktop shell (web dev server has no window lifecycle).
 */
export async function registerDesktopCloseGuard(
  handler: CloseRequestedHandler,
): Promise<(() => void) | null> {
  const handle = currentTauriWindow();
  if (!handle?.onCloseRequested) {
    return null;
  }
  try {
    return await handle.onCloseRequested(handler);
  } catch {
    return null;
  }
}

/** Force the desktop window to close, bypassing the close guard. */
export async function closeDesktopWindow(): Promise<void> {
  const handle = currentTauriWindow();
  if (handle?.destroy) {
    await handle.destroy();
    return;
  }
  if (handle?.close) {
    await handle.close();
  }
}

export async function ensureAppOwnedBackendRuntime(): Promise<DesktopBackendStartupResult | null> {
  const invoke = tauriInvoke();
  if (!invoke) {
    return null;
  }

  const current = await invoke<DesktopBackendStartupResult>("get_app_owned_backend_process_status");
  if (current.state === "running" || current.state === "already_running") {
    return current;
  }

  return invoke<DesktopBackendStartupResult>("start_app_owned_backend_runtime");
}

/**
 * The token this launch of the desktop app shares with the backend it started.
 *
 * Null outside the desktop shell — a browser pointed at a hand-run backend has
 * no bridge to ask, and that backend has no token either, so both sides agree.
 */
export async function desktopApiAuthToken(): Promise<string | null> {
  const invoke = tauriInvoke();
  if (!invoke) {
    return null;
  }
  try {
    const token = await invoke<string>("get_api_auth_token");
    return typeof token === "string" && token ? token : null;
  } catch {
    // An older shell without the command. The backend it started has no token
    // either, so unauthenticated requests are what it expects.
    return null;
  }
}

/**
 * Open a link in the person's own browser, not in this window.
 *
 * Tauri's webview ignores `target="_blank"`, so an ordinary anchor either does
 * nothing or — worse — navigates the app window away from the app. The Rust
 * side has an `open_external_url` command that hands the URL to the operating
 * system after checking it is http(s); this is the one route to it.
 *
 * Falls back to window.open in a plain browser, which is where `npm run dev`
 * lives.
 */
export function openExternalUrl(url: string): void {
  const invoke = tauriInvoke();
  if (invoke) {
    void invoke("open_external_url", { url });
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}
