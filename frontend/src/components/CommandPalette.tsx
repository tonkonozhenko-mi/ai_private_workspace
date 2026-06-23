import { useEffect, useMemo, useRef, useState } from "react";

export interface PaletteItem {
  id: string;
  kind: "repo" | "group" | "tab" | "file";
  label: string;
  sub?: string;
  run: () => void;
}

const KIND_LABEL: Record<PaletteItem["kind"], string> = {
  repo: "Repositories",
  group: "Groups",
  tab: "Go to",
  file: "Files",
};

const KIND_ORDER: PaletteItem["kind"][] = ["tab", "repo", "group", "file"];

// A Cmd/Ctrl-K command palette: one fast entry point to jump to any repo, group,
// section, or file. Keyboard-first; nothing is changed by navigating.
export function CommandPalette({
  open,
  onClose,
  items,
}: {
  open: boolean;
  onClose: () => void;
  items: PaletteItem[];
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      // Focus after the overlay paints.
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matched = q
      ? items.filter(
          (it) => it.label.toLowerCase().includes(q) || (it.sub ?? "").toLowerCase().includes(q),
        )
      : items;
    // Files are noisy without a query — only show them once the user types.
    const visible = q ? matched : matched.filter((it) => it.kind !== "file");
    return KIND_ORDER.flatMap((kind) => visible.filter((it) => it.kind === kind)).slice(0, 50);
  }, [items, query]);

  useEffect(() => {
    setActive((a) => Math.min(a, Math.max(0, filtered.length - 1)));
  }, [filtered.length]);

  if (!open) return null;

  const runAt = (i: number) => {
    const item = filtered[i];
    if (item) {
      item.run();
      onClose();
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      runAt(active);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  // Build the rendered rows with category headers, tracking the flat index.
  let flatIndex = -1;
  let lastKind: PaletteItem["kind"] | null = null;

  return (
    <div className="cmdk-overlay" onMouseDown={onClose} role="presentation">
      <div className="cmdk" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-label="Command palette">
        <input
          ref={inputRef}
          className="cmdk-input"
          type="text"
          value={query}
          placeholder="Jump to a repo, group, section or file…"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          aria-label="Search"
        />
        <div className="cmdk-list" ref={listRef}>
          {filtered.length === 0 ? (
            <p className="cmdk-empty">No matches.</p>
          ) : (
            filtered.map((item) => {
              flatIndex += 1;
              const i = flatIndex;
              const header = item.kind !== lastKind ? KIND_LABEL[item.kind] : null;
              lastKind = item.kind;
              return (
                <div key={`${item.kind}-${item.id}`}>
                  {header ? <p className="cmdk-cat">{header}</p> : null}
                  <button
                    type="button"
                    className={`cmdk-item${i === active ? " is-active" : ""}`}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => runAt(i)}
                  >
                    <span className="cmdk-item-label">{item.label}</span>
                    {item.sub ? <span className="cmdk-item-sub">{item.sub}</span> : null}
                  </button>
                </div>
              );
            })
          )}
        </div>
        <div className="cmdk-foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
          <span><kbd>↵</kbd> open</span>
          <span><kbd>esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}
