import { useCallback, useState } from "react";
import { createPortal } from "react-dom";

// A drop-in replacement for window.prompt() that works inside the Tauri desktop
// webview, where native window.prompt/confirm/alert are silently blocked (they
// return immediately without showing anything). Usage mirrors prompt():
//
//   const { prompt, dialog } = usePromptDialog();
//   const value = await prompt("Rename this", currentTitle);   // string | null
//   ...
//   return (<>{dialog}{/* rest of the component */}</>);
//
// The overlay is portaled to <body> so an ancestor with a CSS transform/filter
// can't trap its position:fixed (the same containing-block gotcha the answer
// trace panel hit). Enter saves, Escape / backdrop / Cancel returns null.

interface PendingPrompt {
  message: string;
  multiline: boolean;
  resolve: (value: string | null) => void;
}

interface PromptOptions {
  multiline?: boolean;
  placeholder?: string;
}

export function usePromptDialog() {
  const [pending, setPending] = useState<PendingPrompt | null>(null);
  const [value, setValue] = useState("");
  const [placeholder, setPlaceholder] = useState("");

  const prompt = useCallback(
    (message: string, defaultValue = "", options?: PromptOptions) =>
      new Promise<string | null>((resolve) => {
        setValue(defaultValue);
        setPlaceholder(options?.placeholder ?? "");
        setPending({ message, multiline: options?.multiline ?? false, resolve });
      }),
    [],
  );

  const close = useCallback(
    (result: string | null) => {
      setPending((current) => {
        current?.resolve(result);
        return null;
      });
    },
    [],
  );

  const dialog = pending
    ? createPortal(
        <div
          className="prompt-dialog-backdrop"
          role="dialog"
          aria-modal="true"
          onClick={() => close(null)}
        >
          <div className="prompt-dialog" onClick={(event) => event.stopPropagation()}>
            <p className="prompt-dialog-message">{pending.message}</p>
            {pending.multiline ? (
              <textarea
                className="prompt-dialog-input"
                autoFocus
                rows={5}
                value={value}
                placeholder={placeholder}
                onChange={(event) => setValue(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") close(null);
                }}
              />
            ) : (
              <input
                className="prompt-dialog-input"
                type="text"
                autoFocus
                value={value}
                placeholder={placeholder}
                onChange={(event) => setValue(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") close(value);
                  if (event.key === "Escape") close(null);
                }}
              />
            )}
            <div className="prompt-dialog-actions">
              <button type="button" className="text-button" onClick={() => close(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="workspace-card-action"
                onClick={() => close(value)}
              >
                Save
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )
    : null;

  return { prompt, dialog };
}
