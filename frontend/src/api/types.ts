export interface WorkspaceOverviewItem {
  workspace_id: string;
  name: string;
  project_path: string;
  assistant_mode: string;
  privacy_mode: string;
  created_at: string;
  archived_at: string | null;
  is_archived: boolean;
  readiness_status: string;
  quick_start_status: string;
  next_action_id: string | null;
  next_action_title: string | null;
  has_scan: boolean;
  detected_skills_count: number;
  index_status: string;
  commands_pending_count: number;
  last_event_title: string | null;
  last_event_type: string | null;
  last_event_at: string | null;
}

export interface WorkspacesOverview {
  total_workspaces: number;
  items: WorkspaceOverviewItem[];
}

export interface TimelineEvent {
  id: string;
  workspace_id: string;
  event_type: string;
  title: string;
  summary: string;
  metadata: Record<string, string>;
  created_at: string;
}

export interface WorkspaceIndexStatus {
  workspace_id: string;
  status: string;
  indexed_files_count: number;
  chunks_count: number;
  skipped_files_count: number;
  last_indexed_at: string | null;
  last_error: string | null;
}

export interface WorkspaceSummary {
  workspace_id: string;
  name: string;
  project_path: string;
  assistant_mode: string;
  privacy_mode: string;
  created_at: string;
  has_scan: boolean;
  detected_skills_count: number;
  index_status: WorkspaceIndexStatus;
  recent_events: TimelineEvent[];
}

export interface WorkspaceModelsDashboardSummary {
  workspace_id: string;
  overall_status: string;
  primary_next_action_id: string | null;
  primary_next_action_title: string | null;
  selected_llm: string | null;
  selected_embedding: string | null;
  active_llm: string;
  active_embedding: string;
  can_ask_with_selected_llm: boolean;
  can_search_with_selected_embedding: boolean;
  top_recommended_model: string | null;
  top_recommended_model_score: number | null;
  performance_models_count: number;
  warnings_count: number;
  notes: string[];
}

export interface WorkspaceDashboard {
  workspace_id: string;
  workspace_name: string;
  assistant_mode: string;
  status: string;
  summary: WorkspaceSummary;
  quick_start: {
    workspace_id: string;
    status: string;
    next_action_id: string | null;
    next_action_title: string | null;
  };
  recent_events: TimelineEvent[];
  primary_next_action_id: string | null;
  primary_next_action_title: string | null;
  models_summary: WorkspaceModelsDashboardSummary | null;
}

export interface WorkspaceUIAction {
  id: string;
  title: string;
  description: string;
  method: string;
  endpoint: string;
  category: string;
  status: string;
  is_primary: boolean;
  mutates_data: boolean;
  reason: string;
}

export interface WorkspaceUIActionCatalog {
  workspace_id: string;
  primary_action_id: string | null;
  actions: WorkspaceUIAction[];
  notes: string[];
}

export interface WorkspaceDetailBundle {
  dashboard: WorkspaceDashboard;
  actions: WorkspaceUIActionCatalog;
  modelsSummary: WorkspaceModelsDashboardSummary;
}
