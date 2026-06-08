import type { TimelineEvent } from "../api/types";

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

export function ActivityTimeline({ events }: ActivityTimelineProps) {
  return (
    <section className="panel activity-timeline-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Activity</p>
          <h2>Workspace timeline</h2>
        </div>
        <span className="panel-count">{events.length}</span>
      </div>

      <p className="panel-intro">
        Activity is persisted backend timeline data.
      </p>

      {events.length > 0 ? (
        <ol className="activity-timeline">
          {events.map((event) => (
            <TimelineItem event={event} key={event.id} />
          ))}
        </ol>
      ) : (
        <div className="activity-empty-state">
          <p className="eyebrow">No activity yet</p>
          <h2>Workspace events will appear here</h2>
          <p>
            Scans, indexing, questions, model selections, experiments, and
            command decisions appear after the user explicitly invokes them.
          </p>
        </div>
      )}
    </section>
  );
}

function TimelineItem({ event }: { event: TimelineEvent }) {
  const category = getEventCategory(event.event_type);
  const metadata = Object.entries(event.metadata).slice(0, 4);

  return (
    <li className={`timeline-item timeline-${category}`}>
      <span className="timeline-rail" aria-hidden="true">
        <span />
      </span>
      <article>
        <header className="timeline-item-header">
          <div>
            <span className="event-type-badge">{formatLabel(event.event_type)}</span>
            <h3>{event.title}</h3>
          </div>
          <time dateTime={event.created_at}>{formatDate(event.created_at)}</time>
        </header>

        <p>{event.summary}</p>

        {metadata.length > 0 ? (
          <dl className="timeline-metadata">
            {metadata.map(([key, value]) => (
              <div key={key} title={`${formatLabel(key)}: ${value}`}>
                <dt>{formatLabel(key)}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
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

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
