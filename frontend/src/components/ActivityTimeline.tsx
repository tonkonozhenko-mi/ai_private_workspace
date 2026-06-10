import { useMemo, useState } from "react";
import type { TimelineEvent, WorkspaceJob } from "../api/types";
import { EmptyState } from "./EmptyState";
import { StatusBadge } from "./StatusBadge";
import type { StatusTone } from "./statusTone";

interface ActivityTimelineProps {
  events: TimelineEvent[];
  jobs: WorkspaceJob[];
  jobsLoading: boolean;
  jobsError: string | null;
  onRefreshJobs: () => Promise<void> | void;
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

export function ActivityTimeline({
  events,
  jobs,
  jobsLoading,
  jobsError,
  onRefreshJobs,
}: ActivityTimelineProps) {
  const groupedEvents = useMemo(() => groupEventsByDay(events), [events]);
  const visibleJobs = jobs.slice(0, 8);
  const summary = useMemo(() => buildActivitySummary(events), [events]);

  return (
    <section className="panel activity-timeline-panel">
      <div className="panel-heading activity-panel-heading">
        <div>
          <p className="eyebrow">Activity</p>
          <h2>Workspace activity</h2>
          <p className="panel-intro activity-panel-intro">
            Recent questions, model changes, context updates, and experiment feedback. Details stay hidden until you need them.
          </p>
        </div>
        <span className="panel-count">{events.length + visibleJobs.length}</span>
      </div>


      <JobActivitySection
        jobs={visibleJobs}
        loading={jobsLoading}
        error={jobsError}
        onRefresh={onRefreshJobs}
      />

      {events.length > 0 ? (
        <>
          <div className="activity-summary-grid" aria-label="Activity summary">
            <ActivitySummaryItem label="Questions" value={summary.ask} tone="accent" />
            <ActivitySummaryItem label="AI changes" value={summary.experiment + summary.workspace} tone="info" />
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
          message="Questions, scan/index jobs, context updates, AI model changes, experiment feedback, and command decisions appear after you explicitly invoke them."
          compact
        />
      )}
    </section>
  );
}


function JobActivitySection({
  jobs,
  loading,
  error,
  onRefresh,
}: {
  jobs: WorkspaceJob[];
  loading: boolean;
  error: string | null;
  onRefresh: () => Promise<void> | void;
}) {
  return (
    <section className="job-activity-section" aria-label="Background job history">
      <div className="job-activity-heading">
        <div>
          <p className="eyebrow">Background jobs</p>
          <h3>Scan and indexing runs</h3>
          <p>
            See what ran, how long it took, and which file rules were applied.
          </p>
        </div>
        <button className="text-button" type="button" onClick={() => void onRefresh()}>
          {loading ? "Refreshing..." : "Refresh jobs"}
        </button>
      </div>
      {error ? <p className="settings-message error">{error}</p> : null}
      {jobs.length === 0 ? (
        <p className="job-activity-empty">
          No scan or indexing jobs are available in this app session yet.
        </p>
      ) : (
        <div className="job-activity-list">
          {jobs.map((job) => (
            <JobActivityCard job={job} key={job.job_id} />
          ))}
        </div>
      )}
    </section>
  );
}

function JobActivityCard({ job }: { job: WorkspaceJob }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const requestEntries = Object.entries(job.request_summary);
  const resultEntries = Object.entries(job.result_summary);
  const hasDetails = requestEntries.length > 0 || resultEntries.length > 0 || Boolean(job.error);

  return (
    <article className="job-activity-card">
      <header>
        <div>
          <StatusBadge label={formatLabel(job.job_type)} tone={jobTone(job.status)} />
          <h4>{job.title}</h4>
        </div>
        <div className="job-activity-meta">
          <StatusBadge label={job.status} tone={jobTone(job.status)} />
          <span>{formatJobDuration(job)}</span>
        </div>
      </header>
      <p>{job.message ?? job.error ?? "No job message."}</p>
      <dl className="timeline-metadata timeline-metadata-preview">
        <div title={`Started: ${formatDateTime(job.started_at ?? job.created_at)}`}>
          <dt>Started</dt>
          <dd>{formatDateTime(job.started_at ?? job.created_at)}</dd>
        </div>
        <div title={`Completed: ${job.completed_at ? formatDateTime(job.completed_at) : "—"}`}>
          <dt>Completed</dt>
          <dd>{job.completed_at ? formatDateTime(job.completed_at) : "—"}</dd>
        </div>
        {job.request_summary.file_rules_profile ? (
          <div title={`File rules profile: ${job.request_summary.file_rules_profile}`}>
            <dt>File rules</dt>
            <dd>{job.request_summary.file_rules_profile}</dd>
          </div>
        ) : null}
        {job.result_summary.scanned_files ? (
          <div title={`Scanned files: ${job.result_summary.scanned_files}`}>
            <dt>Scanned</dt>
            <dd>{job.result_summary.scanned_files}</dd>
          </div>
        ) : null}
        {job.result_summary.chunks_count ? (
          <div title={`Context chunks: ${job.result_summary.chunks_count}`}>
            <dt>Chunks</dt>
            <dd>{job.result_summary.chunks_count}</dd>
          </div>
        ) : null}
      </dl>
      {hasDetails ? (
        <div className="timeline-details">
          <button
            className="secondary-button timeline-details-toggle"
            type="button"
            onClick={() => setIsExpanded((current) => !current)}
            aria-expanded={isExpanded}
          >
            {isExpanded ? "Hide job details" : "View job details"}
          </button>
          {isExpanded ? (
            <div className="job-activity-details-grid">
              <JobMetadataList title="Applied request" entries={requestEntries} />
              <JobMetadataList title="Result" entries={resultEntries} />
              {job.error ? (
                <div className="job-error-detail">
                  <strong>Error</strong>
                  <p>{job.error}</p>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function JobMetadataList({
  title,
  entries,
}: {
  title: string;
  entries: Array<[string, string]>;
}) {
  if (entries.length === 0) {
    return null;
  }

  return (
    <div>
      <strong>{title}</strong>
      <dl className="timeline-metadata timeline-metadata-details">
        {entries.map(([key, value]) => (
          <div key={key} title={`${formatLabel(key)}: ${value}`}>
            <dt>{formatLabel(key)}</dt>
            <dd>{formatMetadataValue(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
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
    return "Feedback saved";
  }
  if (type.includes("experiment")) {
    return "Model comparison";
  }
  if (type.includes("model") && type.includes("selected")) {
    return "AI model changed";
  }
  if (type.includes("scan")) {
    return "Project scanned";
  }
  if (type.includes("index")) {
    return "Context updated";
  }

  if (category === "project") {
    return "Project";
  }
  if (category === "ask") {
    return "Ask";
  }
  if (category === "command") {
    return "Command decision";
  }
  if (category === "workspace") {
    return "Workspace";
  }
  return eventType;
}

function getHumanTitle(event: TimelineEvent) {
  const type = event.event_type.toLowerCase();

  if (type.includes("question")) {
    return "Question asked";
  }
  if (type.includes("model") && type.includes("selected")) {
    return "AI model preference updated";
  }
  if (type.includes("experiment") && type.includes("rating")) {
    return "Model feedback saved";
  }
  if (type.includes("experiment")) {
    return "Model comparison completed";
  }
  if (type.includes("scan")) {
    return "Project scan completed";
  }
  if (type.includes("index")) {
    return "Search context rebuilt";
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
  const friendlyLabels: Record<string, string> = {
    llm_provider: "AI provider",
    llm_model: "AI model",
    quality_warnings_count: "Verification notes",
    sources_count: "Sources",
    experiment_type: "Comparison type",
    candidates_count: "Models compared",
    shared_context_sources_count: "Shared sources",
    detected_skills_count: "Technologies found",
    indexed_files_count: "Files indexed",
    chunks_count: "Context chunks",
    provider: "Provider",
    model: "Model",
    model_type: "Model type",
    selected_reason: "Reason",
    risk_level: "Risk level",
    policy_decision: "Policy decision",
  };

  return friendlyLabels[value] ?? titleCase(value.replaceAll("_", " "));
}

function titleCase(value: string) {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
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


function jobTone(status: string): StatusTone {
  const normalized = status.toLowerCase();
  if (normalized === "completed") {
    return "success";
  }
  if (normalized === "failed") {
    return "danger";
  }
  if (normalized === "cancelled") {
    return "warning";
  }
  if (normalized === "running" || normalized === "queued") {
    return "info";
  }
  return "neutral";
}

function formatJobDuration(job: WorkspaceJob) {
  if (job.duration_ms === null) {
    return job.status === "running" ? "Running" : "—";
  }
  if (job.duration_ms < 1000) {
    return `${job.duration_ms} ms`;
  }
  return `${(job.duration_ms / 1000).toFixed(1)}s`;
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
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
