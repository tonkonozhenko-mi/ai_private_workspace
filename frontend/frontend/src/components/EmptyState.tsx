interface EmptyStateProps {
  title: string;
  message?: string;
  compact?: boolean;
  actionLabel?: string;
  onAction?: () => void | Promise<void>;
}

export function EmptyState({
  title,
  message,
  compact = false,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div
      className={`state-card state-card--empty${
        compact ? " state-card--compact" : ""
      }`}
    >
      <strong className="state-title">{title}</strong>
      {message ? <p className="state-message">{message}</p> : null}
      {actionLabel && onAction ? (
        <button
          className="state-action"
          type="button"
          onClick={() => void onAction()}
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
