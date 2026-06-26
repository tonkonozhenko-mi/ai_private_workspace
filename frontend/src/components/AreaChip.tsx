import type { ProjectWatchArea } from "../api/types";

/**
 * A "area · N" chip for changed areas. When the backend provides the actual file
 * paths, hovering or focusing the chip reveals which files changed. Falls back to
 * a plain chip (no tooltip) when paths aren't available.
 */
export function AreaChip({
  area,
  className = "",
}: {
  area: ProjectWatchArea;
  className?: string;
}) {
  const paths = area.paths ?? [];
  const hasFiles = paths.length > 0;
  const more = area.files - paths.length;
  return (
    <span
      className={`area-chip ${className}`.trim()}
      tabIndex={hasFiles ? 0 : undefined}
      aria-label={
        hasFiles ? `${area.area}: ${paths.join(", ")}` : `${area.area}, ${area.files} files`
      }
    >
      {area.area} · {area.files}
      {hasFiles ? (
        <span className="area-chip-tip" role="tooltip">
          <span className="area-chip-tip-head">{area.area}</span>
          {paths.map((p) => (
            <span key={p} className="area-chip-file">
              {p}
            </span>
          ))}
          {more > 0 ? <span className="area-chip-more">+{more} more</span> : null}
        </span>
      ) : null}
    </span>
  );
}
