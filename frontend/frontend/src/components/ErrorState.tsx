interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void | Promise<void>;
  compact?: boolean;
}

export function ErrorState({
  title = "Could not load data",
  message,
  onRetry,
  compact = false,
}: ErrorStateProps) {
  return (
    <div
      className={`state-card state-card--error${
        compact ? " state-card--compact" : ""
      }`}
      role="alert"
    >
      <strong className="state-title">{title}</strong>
      <p className="state-message">{message}</p>
      {onRetry ? (
        <button
          className="state-action"
          type="button"
          onClick={() => void onRetry()}
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
