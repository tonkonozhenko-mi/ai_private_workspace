import { useMemo, useState } from "react";
import type { TimelineEvent } from "../api/types";
import { EmptyState } from "./EmptyState";
import { StatusBadge } from "./StatusBadge";
import type { StatusTone } from "./statusTone";

interface ActivityTimelineProps {
  events: TimelineEvent[];
}

type EventCategory =
  | "workspace"
  | "project"
  | "ask"
  | "command"
  | "experiment"
  | "general";

interface GroupedEvents {
  label: string;
  events: TimelineEvent[];
}

export function ActivityTimeline({ events }: ActivityTimelineProps) {
  const groupedEvents = useMemo(() => groupEventsByDay(events), [events]);
  const summary = useMemo(() => buildActivitySummary(events), [events]);

  return (
    <section className="panel activity-timeline-panel">
      <div className="panel-heading activity-panel-heading">
        <div>
          <p className="eyebrow">Activity</p>
          <h2>Workspace activity</h2>
          <p className="panel-intro activity-panel-intro">
            Recent local workspace events, grouped by day. Open details only when you need the raw metadata.
          </p>
        </div>
        <span className="panel-count">{events.length}</span>
      </div>

      {events.length > 0 ? (
        <>
          <div className="activity-summary-grid" aria-label="Activity summary">
            <ActivitySummaryItem label="Questions" value={summary.ask} tone="accent" />
            <ActivitySummaryItem label="Model events" value={summary.experiment + summary.workspace} tone="info" />
            <ActivitySummaryItem label="Project events" value={summary.project} tone="success" />
          </div>

          <div className="activity-day-list">
            {groupedEvents.map((group) => (
              <section className="activity-day-section" key={group.label}>
                <div className="activity-day-heading">
                  <h3>{group.label}</h3>
                  <span>{group.events.length} events</span>
                </div>
                <ol className="activity-timeline">
                  {group.events.map((event) => (
                    <TimelineItem event={event} key={event.id} />
                  ))}
                </ol>
              </section>
            ))}
          </div>
        </>
      ) : (
        <EmptyState
          title="Workspace events will appear here"
          message="Scans, indexing, questions, model selections, experiments, and command decisions appear after the user explicitly invokes them."
          compact
        />
      )}
    </section>
  );
}

function ActivitySummaryItem({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: StatusTone;
}) {
  return (
    <div className="activity-summary-item">
      <StatusBadge label={label} tone={tone} />
      <strong>{value}</strong>
    </div>
  );
}

function TimelineItem({ event }: { event: TimelineEvent }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const category = getEventCategory(event.event_type);
  const metadata = Object.entries(event.metadata);
  const previewMetadata = getPreviewMetadata(event, category);
  const hasDetails = metadata.length > 0;
  const humanTitle = getHumanTitle(event);

  return (
    <li className={`timeline-item timeline-${category}`}>
      <span className="timeline-rail" aria-hidden="true">
        <span>{getEventIcon(category)}</span>
      </span>
      <article>
        <header className="timeline-item-header">
          <div>
            <StatusBadge label={getEventLabel(event.event_type, category)} tone={getEventTone(category)} />
            <h3>{humanTitle}</h3>
          </div>
          <time dateTime={event.created_at}>{formatTime(event.created_at)}</time>
        </header>

        <p>{event.summary}</p>

        {previewMetadata.length > 0 ? (
          <dl className="timeline-metadata timeline-metadata-preview">
            {previewMetadata.map(([key, value]) => (
              <div key={key} title={`${formatLabel(key)}: ${value}`}>
                <dt>{formatLabel(key)}</dt>
                <dd>{formatMetadataValue(value)}</dd>
              </div>
            ))}
          </dl>
        ) : null}

        {hasDetails ? (
          <div className="timeline-details">
            <button
              className="secondary-button timeline-details-toggle"
              type="button"
              onClick={() => setIsExpanded((current) => !current)}
              aria-expanded={isExpanded}
            >
              {isExpanded ? "Hide details" : "Show details"}
            </button>

            {isExpanded ? (
              <dl className="timeline-metadata timeline-metadata-details">
                {metadata.map(([key, value]) => (
                  <div key={key} title={`${formatLabel(key)}: ${value}`}>
                    <dt>{formatLabel(key)}</dt>
                    <dd>{formatMetadataValue(value)}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </div>
        ) : null}
      </article>
    </li>
  );
}

function getEventCategory(eventType: string): EventCategory {
  const type = eventType.toLowerCase();

  if (type.includes("command")) {
    return "command";
  }
  if (
    type.includes("experiment") ||
    type.includes("rating") ||
    type.includes("rated")
  ) {
    return "experiment";
  }
  if (type.includes("question") || type.includes("ask")) {
    return "ask";
  }
  if (
    type.includes("scan") ||
    type.includes("index") ||
    type.includes("report")
  ) {
    return "project";
  }
  if (type.includes("workspace") || type.includes("model")) {
    return "workspace";
  }
  return "general";
}

function getEventTone(category: EventCategory): StatusTone {
  if (category === "project") {
    return "success";
  }
  if (category === "ask") {
    return "accent";
  }
  if (category === "command") {
    return "warning";
  }
  if (category === "experiment") {
    return "accent";
  }
  if (category === "workspace") {
    return "info";
  }
  return "neutral";
}

function getEventLabel(eventType: string, category: EventCategory) {
  const type = eventType.toLowerCase();

  if (type.includes("question")) {
    return "Question asked";
  }
  if (type.includes("experiment") && type.includes("rating")) {
    return "Experiment rated";
  }
  if (type.includes("experiment")) {
    return "Experiment";
  }
  if (type.includes("model") && type.includes("selected")) {
    return "Model selected";
  }
  if (type.includes("scan")) {
    return "Scan";
  }
  if (type.includes("index")) {
    return "Index";
  }

  if (category === "project") {
    return "Project";
  }
  if (category === "ask") {
    return "Ask";
  }
  if (category === "command") {
    return "Command";
  }
  if (category === "workspace") {
    return "Workspace";
  }
  return eventType;
}

function getHumanTitle(event: TimelineEvent) {
  const type = event.event_type.toLowerCase();

  if (type.includes("question")) {
    return "Workspace question asked";
  }
  if (type.includes("model") && type.includes("selected")) {
    return "Workspace model preference updated";
  }
  if (type.includes("experiment") && type.includes("rating")) {
    return "Model experiment rated";
  }
  if (type.includes("experiment")) {
    return "Model comparison completed";
  }
  if (type.includes("scan")) {
    return "Project scan completed";
  }
  if (type.includes("index")) {
    return "Workspace index updated";
  }
  return event.title;
}

function getEventIcon(category: EventCategory) {
  if (category === "ask") {
    return "?";
  }
  if (category === "experiment") {
    return "⇄";
  }
  if (category === "project") {
    return "✓";
  }
  if (category === "command") {
    return "!";
  }
  if (category === "workspace") {
    return "•";
  }
  return "•";
}

function getPreviewMetadata(event: TimelineEvent, category: EventCategory) {
  const preferredKeysByCategory: Record<EventCategory, string[]> = {
    ask: ["llm_provider", "llm_model", "quality_warnings_count", "sources_count"],
    experiment: ["experiment_type", "status", "candidates_count", "shared_context_sources_count"],
    project: ["detected_skills_count", "indexed_files_count", "chunks_count", "status"],
    workspace: ["provider", "model", "model_type", "selected_reason"],
    command: ["command", "status", "risk_level", "policy_decision"],
    general: [],
  };

  const preferredKeys = preferredKeysByCategory[category];
  const metadataEntries = Object.entries(event.metadata);
  const usedKeys = new Set<string>();
  const selected: Array<[string, string]> = [];

  for (const key of preferredKeys) {
    const match = metadataEntries.find(([metadataKey]) => metadataKey === key);
    if (match) {
      selected.push(match);
      usedKeys.add(match[0]);
    }
  }

  for (const entry of metadataEntries) {
    if (selected.length >= 4) {
      break;
    }
    if (!usedKeys.has(entry[0])) {
      selected.push(entry);
      usedKeys.add(entry[0]);
    }
  }

  return selected.slice(0, 4);
}

function buildActivitySummary(events: TimelineEvent[]) {
  const summary: Record<EventCategory, number> = {
    workspace: 0,
    project: 0,
    ask: 0,
    command: 0,
    experiment: 0,
    general: 0,
  };

  for (const event of events) {
    summary[getEventCategory(event.event_type)] += 1;
  }

  return summary;
}

function groupEventsByDay(events: TimelineEvent[]): GroupedEvents[] {
  const groups = new Map<string, TimelineEvent[]>();

  for (const event of events) {
    const label = getDayLabel(event.created_at);
    const group = groups.get(label) ?? [];
    group.push(event);
    groups.set(label, group);
  }

  return Array.from(groups.entries()).map(([label, grouped]) => ({
    label,
    events: grouped,
  }));
}

function getDayLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Earlier";
  }

  const now = new Date();
  const eventDay = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterday = today - 24 * 60 * 60 * 1000;

  if (eventDay === today) {
    return "Today";
  }
  if (eventDay === yesterday) {
    return "Yesterday";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(date);
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function formatMetadataValue(value: string) {
  if (value === "true") {
    return "Yes";
  }
  if (value === "false") {
    return "No";
  }
  return value;
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    timeStyle: "short",
  }).format(date);
}
