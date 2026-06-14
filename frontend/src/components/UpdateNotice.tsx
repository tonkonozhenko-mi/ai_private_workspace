import { useEffect, useState } from "react";

// Minimal bridge to the global Tauri event API. We avoid importing the npm
// plugin packages so the web build stays dependency-free; the desktop shell
// exposes `window.__TAURI__` because `withGlobalTauri` is enabled.
type TauriEvent<T> = { payload: T };
type UnlistenFn = () => void;
type TauriGlobal = {
  event?: {
    listen: <T>(
      event: string,
      handler: (event: TauriEvent<T>) => void,
    ) => Promise<UnlistenFn>;
  };
};

type UpdateState =
  | { kind: "idle" }
  | { kind: "available"; version: string }
  | { kind: "ready"; version: string; at: string }
  | { kind: "error"; message: string };

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function UpdateNotice() {
  const [state, setState] = useState<UpdateState>({ kind: "idle" });

  useEffect(() => {
    const tauri = (window as unknown as { __TAURI__?: TauriGlobal }).__TAURI__;
    const listen = tauri?.event?.listen;
    if (!listen) {
      return;
    }

    const unlisteners: UnlistenFn[] = [];
    let cancelled = false;
    const register = (fn: Promise<UnlistenFn>) => {
      fn.then((un) => {
        if (cancelled) un();
        else unlisteners.push(un);
      }).catch(() => undefined);
    };

    register(
      listen<string>("update://available", (event) =>
        setState({ kind: "available", version: event.payload }),
      ),
    );
    register(
      listen<string>("update://ready", (event) =>
        setState({ kind: "ready", version: event.payload, at: formatTime(new Date()) }),
      ),
    );
    register(
      listen<string>("update://error", (event) =>
        setState({ kind: "error", message: event.payload }),
      ),
    );

    return () => {
      cancelled = true;
      unlisteners.forEach((un) => un());
    };
  }, []);

  if (state.kind === "idle") {
    return null;
  }

  return (
    <div className={`update-notice update-notice-${state.kind}`} role="status">
      {state.kind === "available" && (
        <>
          <span className="update-notice-spinner" aria-hidden="true" />
          <span className="update-notice-text">
            Downloading update {state.version}…
          </span>
        </>
      )}
      {state.kind === "ready" && (
        <>
          <span className="update-notice-dot" aria-hidden="true" />
          <span className="update-notice-text">
            Update {state.version} downloaded at {state.at}. Quit and reopen the
            app to apply it.
          </span>
          <button
            type="button"
            className="update-notice-dismiss"
            onClick={() => setState({ kind: "idle" })}
            aria-label="Dismiss"
          >
            ✕
          </button>
        </>
      )}
      {state.kind === "error" && (
        <>
          <span className="update-notice-text">
            Update check failed: {state.message}
          </span>
          <button
            type="button"
            className="update-notice-dismiss"
            onClick={() => setState({ kind: "idle" })}
            aria-label="Dismiss"
          >
            ✕
          </button>
        </>
      )}
    </div>
  );
}
