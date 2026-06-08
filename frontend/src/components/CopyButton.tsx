import { useEffect, useState } from "react";

type CopyState = "idle" | "copied" | "failed";

interface CopyButtonProps {
  text: string;
}

export function CopyButton({ text }: CopyButtonProps) {
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

  const label =
    copyState === "copied"
      ? "Copied"
      : copyState === "failed"
        ? "Copy failed"
        : "Copy";

  return (
    <button
      className={`copy-button is-${copyState}`}
      type="button"
      title="Copy command text"
      onClick={() => void copyText()}
      aria-live="polite"
    >
      {label}
    </button>
  );
}
