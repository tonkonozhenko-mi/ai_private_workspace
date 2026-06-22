import { useMemo, useState } from "react";

import type { ProjectGraphEdge, ProjectGraphNode, ProjectGraphPayload } from "../api/types";

// Left-to-right deployment flow. Config files have no edges and live in the
// Summary, so they are intentionally left off the map to keep it readable.
const COLUMN_ORDER = [
  "environment",
  "infra_component",
  "pipeline",
  "pipeline_job",
  "application",
  "module",
  "service",
  "container_image",
  "cloud_service",
  "dependency",
];

const TYPE_LABEL: Record<string, string> = {
  environment: "Environment",
  infra_component: "Infrastructure",
  pipeline: "Pipeline",
  pipeline_job: "Job",
  application: "Application",
  module: "Module",
  service: "Service",
  container_image: "Image",
  cloud_service: "Cloud service",
  dependency: "Dependency",
  config_file: "File",
};

const TYPE_COLOR: Record<string, string> = {
  environment: "#7dd3ae",
  infra_component: "#34c27e",
  pipeline: "#5eb0ef",
  pipeline_job: "#8ec7f2",
  application: "#5ad1c4",
  module: "#8fd19a",
  service: "#c4a6f0",
  container_image: "#e0b07a",
  cloud_service: "#f0a878",
  dependency: "#d6cf8a",
  config_file: "#9aa6a1",
};

const NODE_W = 158;
const NODE_H = 34;
const ROW_GAP = 16;
const COL_GAP = 64;
const PAD = 20;

interface Placed {
  node: ProjectGraphNode;
  x: number;
  y: number;
}

function truncate(text: string, max = 22): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export function ProjectMap({ graph }: { graph: ProjectGraphPayload }) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  // Jobs are the biggest source of clutter (many same-named nodes), so the map
  // opens with that layer hidden; the legend toggles any layer on or off.
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(
    () => new Set(["pipeline_job"]),
  );

  // Every node type present in the graph (for the legend), with counts — shown
  // even when hidden so a layer can be toggled back on.
  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const n of graph.nodes) {
      if (COLUMN_ORDER.includes(n.type)) counts.set(n.type, (counts.get(n.type) ?? 0) + 1);
    }
    return counts;
  }, [graph.nodes]);

  const shown = useMemo(
    () =>
      graph.nodes.filter(
        (n) => COLUMN_ORDER.includes(n.type) && !hiddenTypes.has(n.type),
      ),
    [graph.nodes, hiddenTypes],
  );

  const toggleType = (type: string) =>
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  const shownIds = useMemo(() => new Set(shown.map((n) => n.id)), [shown]);
  const edges = useMemo(
    () => graph.edges.filter((e) => shownIds.has(e.source) && shownIds.has(e.target)),
    [graph.edges, shownIds],
  );

  const { placed, width, height } = useMemo(() => {
    const columns = COLUMN_ORDER.map((type) =>
      shown
        .filter((n) => n.type === type)
        .sort((a, b) => a.name.localeCompare(b.name)),
    );
    const usedColumns = columns.filter((c) => c.length > 0);
    const maxRows = Math.max(1, ...usedColumns.map((c) => c.length));
    const colHeight = maxRows * NODE_H + (maxRows - 1) * ROW_GAP;

    const placements = new Map<string, Placed>();
    usedColumns.forEach((col, ci) => {
      const x = PAD + ci * (NODE_W + COL_GAP);
      const thisHeight = col.length * NODE_H + (col.length - 1) * ROW_GAP;
      const startY = PAD + (colHeight - thisHeight) / 2;
      col.forEach((node, ri) => {
        placements.set(node.id, { node, x, y: startY + ri * (NODE_H + ROW_GAP) });
      });
    });

    const w = PAD * 2 + Math.max(1, usedColumns.length) * (NODE_W + COL_GAP) - COL_GAP;
    const h = PAD * 2 + colHeight;
    return { placed: placements, width: w, height: h };
  }, [shown]);

  const neighbors = useMemo(() => {
    if (!hovered) return null;
    const set = new Set<string>([hovered]);
    for (const e of edges) {
      if (e.source === hovered) set.add(e.target);
      if (e.target === hovered) set.add(e.source);
    }
    return set;
  }, [hovered, edges]);

  if (shown.length === 0) {
    return (
      <p className="pi-muted pi-empty-note">
        Nothing to map yet — no infrastructure, pipelines or services were detected.
      </p>
    );
  }

  const selectedNode = selected ? placed.get(selected)?.node ?? null : null;
  const selectedEdges = selected
    ? edges.filter((e) => e.source === selected || e.target === selected)
    : [];

  function edgePath(e: ProjectGraphEdge): string {
    const s = placed.get(e.source);
    const t = placed.get(e.target);
    if (!s || !t) return "";
    const x1 = s.x + NODE_W;
    const y1 = s.y + NODE_H / 2;
    const x2 = t.x;
    const y2 = t.y + NODE_H / 2;
    const mx = (x1 + x2) / 2;
    return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
  }

  function nodeOpacity(id: string): number {
    if (!neighbors) return 1;
    return neighbors.has(id) ? 1 : 0.25;
  }

  function edgeActive(e: ProjectGraphEdge): boolean {
    return !hovered || e.source === hovered || e.target === hovered;
  }

  return (
    <div className="pi-map">
      <div className="pi-map-legend">
        {COLUMN_ORDER.filter((t) => typeCounts.has(t)).map((t) => {
          const hidden = hiddenTypes.has(t);
          return (
            <button
              key={t}
              type="button"
              className={`pi-map-legend-item${hidden ? " is-hidden" : ""}`}
              onClick={() => toggleType(t)}
              aria-pressed={!hidden}
              title={hidden ? `Show ${TYPE_LABEL[t]}` : `Hide ${TYPE_LABEL[t]}`}
            >
              <span className="pi-map-swatch" style={{ background: TYPE_COLOR[t] }} />
              {TYPE_LABEL[t]}
              <span className="pi-map-legend-count">{typeCounts.get(t)}</span>
            </button>
          );
        })}
      </div>

      <div className="pi-map-canvas">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          width={width}
          height={height}
          role="img"
          aria-label="Project map"
        >
          <g>
            {edges.map((e) => (
              <path
                key={e.id}
                d={edgePath(e)}
                className={`pi-map-edge${edgeActive(e) ? " pi-map-edge-active" : ""}`}
                fill="none"
              />
            ))}
          </g>
          <g>
            {shown.map((n) => {
              const p = placed.get(n.id);
              if (!p) return null;
              const color = TYPE_COLOR[n.type] ?? "#9aa6a1";
              const isSelected = selected === n.id;
              return (
                <g
                  key={n.id}
                  transform={`translate(${p.x}, ${p.y})`}
                  opacity={nodeOpacity(n.id)}
                  className="pi-map-node"
                  onMouseEnter={() => setHovered(n.id)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => setSelected(isSelected ? null : n.id)}
                >
                  <rect
                    width={NODE_W}
                    height={NODE_H}
                    rx={8}
                    className={`pi-map-rect${isSelected ? " pi-map-rect-selected" : ""}`}
                    style={{ stroke: color }}
                  />
                  <rect width={4} height={NODE_H} rx={2} fill={color} />
                  <text x={14} y={NODE_H / 2 + 4} className="pi-map-label">
                    {truncate(n.name)}
                  </text>
                  {n.status === "inferred" ? (
                    <text x={NODE_W - 10} y={NODE_H / 2 + 4} className="pi-map-inferred">
                      ?
                    </text>
                  ) : null}
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {selectedNode ? (
        <div className="pi-map-detail">
          <div className="pi-map-detail-head">
            <span
              className="pi-map-swatch"
              style={{ background: TYPE_COLOR[selectedNode.type] ?? "#9aa6a1" }}
            />
            <span className="pi-map-detail-name">{selectedNode.name}</span>
            <span className="pi-map-detail-type">{TYPE_LABEL[selectedNode.type]}</span>
          </div>
          <p className="pi-map-detail-meta">
            Detected by {selectedNode.analyzer}
            {selectedNode.status === "inferred" ? " · inferred from naming" : ""}
            {selectedNode.source_file ? (
              <>
                {" · "}
                <code>{selectedNode.source_file}</code>
              </>
            ) : null}
          </p>
          {selectedEdges.length > 0 ? (
            <ul className="pi-map-detail-edges">
              {selectedEdges.map((e) => {
                const other = e.source === selected ? e.target : e.source;
                const dir = e.source === selected ? "→" : "←";
                return (
                  <li key={e.id}>
                    {dir} {e.type.replace(/_/g, " ")}: {placed.get(other)?.node.name ?? other}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="pi-muted">No connections recorded for this node.</p>
          )}
        </div>
      ) : (
        <p className="pi-map-hint">
          Click a colour to show or hide that layer · hover a node to trace its connections ·
          click it for details.
        </p>
      )}
    </div>
  );
}
