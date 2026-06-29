export type WorkspaceTab =
  | "overview"
  | "intelligence"
  | "ask"
  | "models"
  | "reports"
  | "actions"
  | "activity"
  | "settings";

export const workspaceTabs: Array<{ id: WorkspaceTab; label: string }> = [
  { id: "overview", label: "Home" },
  { id: "intelligence", label: "Intelligence" },
  { id: "ask", label: "Ask" },
  { id: "models", label: "Models" },
  { id: "settings", label: "Settings" },
];
