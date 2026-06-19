import { useCallback, useEffect, useState, type MutableRefObject } from "react";

import { listWorkspaceJobs } from "../api/client";
import type { WorkspaceJob } from "../api/types";
import { errorMessage } from "../lib/errorMessage";

interface UseWorkspaceJobsArgs {
  activeTab: string;
  selectedWorkspaceId: string | null;
  /** Ref to the currently-selected workspace id, used to ignore late responses
   *  after the user has switched workspaces. */
  selectedWorkspaceIdRef: MutableRefObject<string | null>;
}

export interface WorkspaceJobsState {
  activityJobs: WorkspaceJob[];
  activityJobsLoading: boolean;
  activityJobsError: string | null;
  loadActivityJobs: (workspaceId: string) => Promise<void>;
}

/**
 * Owns the "Activity" tab's job list: loads jobs for a workspace (ignoring stale
 * responses after a workspace switch) and auto-refreshes when the Activity tab
 * becomes active. Extracted from App.tsx to slim the root component.
 */
export function useWorkspaceJobs({
  activeTab,
  selectedWorkspaceId,
  selectedWorkspaceIdRef,
}: UseWorkspaceJobsArgs): WorkspaceJobsState {
  const [activityJobs, setActivityJobs] = useState<WorkspaceJob[]>([]);
  const [activityJobsLoading, setActivityJobsLoading] = useState(false);
  const [activityJobsError, setActivityJobsError] = useState<string | null>(null);

  const loadActivityJobs = useCallback(
    async (workspaceId: string) => {
      setActivityJobsLoading(true);
      setActivityJobsError(null);
      try {
        const jobs = await listWorkspaceJobs(workspaceId);
        if (selectedWorkspaceIdRef.current === workspaceId) {
          setActivityJobs(jobs);
        }
      } catch (error) {
        if (selectedWorkspaceIdRef.current === workspaceId) {
          setActivityJobsError(errorMessage(error));
        }
      } finally {
        if (selectedWorkspaceIdRef.current === workspaceId) {
          setActivityJobsLoading(false);
        }
      }
    },
    [selectedWorkspaceIdRef],
  );

  useEffect(() => {
    if (activeTab === "activity" && selectedWorkspaceId) {
      void loadActivityJobs(selectedWorkspaceId);
    }
  }, [activeTab, loadActivityJobs, selectedWorkspaceId]);

  return { activityJobs, activityJobsLoading, activityJobsError, loadActivityJobs };
}
