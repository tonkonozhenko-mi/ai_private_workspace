import { useEffect, useState } from "react";

import {
  cancelLocalModelDownloadJob,
  listLocalModelDownloadJobs,
} from "../api/client";
import type { LocalModelDownloadJob } from "../api/types";

/**
 * Always-visible (sidebar) indicator of in-flight local model downloads.
 *
 * Downloads run as backend jobs, so they continue even when you switch tabs.
 * This polls the backend for running jobs and shows progress + a Stop button,
 * so the status is visible everywhere and never lost on navigation.
 */
export function ActiveDownloads() {
  const [jobs, setJobs] = useState<LocalModelDownloadJob[]>([]);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const list = await listLocalModelDownloadJobs();
        if (cancelled) {
          return;
        }
        setJobs(
          (list.jobs ?? []).filter(
            (job) => job.status === "running" || job.status === "queued",
          ),
        );
      } catch {
        // Ignore transient polling errors.
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 2500);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (jobs.length === 0) {
    return null;
  }

  async function stop(jobId: string) {
    setCancellingId(jobId);
    try {
      await cancelLocalModelDownloadJob(jobId);
      setJobs((current) => current.filter((job) => job.id !== jobId));
    } catch {
      // Ignore; the next poll reflects the real state.
    } finally {
      setCancellingId(null);
    }
  }

  return (
    <div className="active-downloads" aria-label="Active model downloads">
      <span className="active-downloads-title">Downloading</span>
      {jobs.map((job) => {
        const percent = job.progress_percent ?? null;
        return (
          <div className="active-download" key={job.id}>
            <div className="active-download-head">
              <span className="active-download-name" title={job.display_name}>
                {job.display_name}
              </span>
              <button
                className="active-download-stop"
                type="button"
                disabled={cancellingId === job.id}
                onClick={() => void stop(job.id)}
              >
                {cancellingId === job.id ? "Stopping…" : "Stop"}
              </button>
            </div>
            <div
              className={`install-progress-bar${percent === null ? " is-indeterminate" : ""}`}
            >
              <span
                style={percent === null ? undefined : { width: `${percent}%` }}
              />
            </div>
            <span className="active-download-meta">
              {percent === null ? "Preparing…" : `${percent}%`}
            </span>
          </div>
        );
      })}
    </div>
  );
}
