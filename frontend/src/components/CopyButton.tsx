import { useEffect, useState } from "react";

type CopyState = "idle" | "copied" | "failed";

interface CopyButtonProps {
  text: string;
  label?: string;
  iconOnly?: boolean;
}

export function CopyButton({ text, label = "command", iconOnly = false }: CopyButtonProps) {
  const [copyState, setCopyState] = useState<CopyState>("idle");

  useEffect(() => {
    if (copyState === "idle") {
      return;
    }

    const timeoutId = window.setTimeout(() => setCopyState("idle"), 1800);
    return () => window.clearTimeout(timeoutId);
  }, [copyState]);

  async function copyText() {
    try {
      await navigator.clipboard.writeText(text);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  const feedbackLabel =
    copyState === "copied"
      ? "Copied"
      : copyState === "failed"
        ? "Copy failed"
        : "Copy";

  if (iconOnly) {
    return (
      <button
        className={`answer-icon-button copy-button is-${copyState}`}
        type="button"
        title={feedbackLabel}
        aria-label={`Copy ${label}`}
        onClick={() => void copyText()}
      >
        {copyState === "copied" ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M20 6L9 17l-5-5" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="9" y="9" width="11" height="11" rx="2" />
            <path d="M5 15V5a2 2 0 0 1 2-2h10" />
          </svg>
        )}
      </button>
    );
  }

  return (
    <button
      className={`copy-button is-${copyState}`}
      type="button"
      title={`Copy ${label} text`}
      onClick={() => void copyText()}
      aria-live="polite"
    >
      {feedbackLabel}
    </button>
  );
}
