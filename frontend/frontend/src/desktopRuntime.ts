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

interface TauriGlobal {
  core?: {
    invoke?: TauriInvoke;
  };
  tauri?: {
    invoke?: TauriInvoke;
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
