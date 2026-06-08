interface LoadingStateProps {
  title?: string;
  message?: string;
  compact?: boolean;
}

export function LoadingState({
  title = "Loading",
  message,
  compact = false,
}: LoadingStateProps) {
  return (
    <div
      className={`state-card state-card--loading${
        compact ? " state-card--compact" : ""
      }`}
      aria-live="polite"
    >
      <span className="loading-indicator" aria-hidden="true" />
      <strong className="state-title">{title}</strong>
      {message ? <p className="state-message">{message}</p> : null}
    </div>
  );
}
