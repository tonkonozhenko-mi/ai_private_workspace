import {
  formatStatusLabel,
  getStatusTone,
  type StatusTone,
} from "./statusTone";

interface StatusBadgeProps {
  label: string;
  tone?: StatusTone;
  size?: "sm" | "md";
  title?: string;
}

export function StatusBadge({
  label,
  tone = getStatusTone(label),
  size = "sm",
  title,
}: StatusBadgeProps) {
  return (
    <span
      className={`status-badge status-badge--${tone} status-badge--${size}`}
      title={title}
    >
      {formatStatusLabel(label)}
    </span>
  );
}
