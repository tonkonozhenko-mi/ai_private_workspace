import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

const SIDEBAR_COLLAPSED_KEY = "apw.sidebarCollapsed";

/** Sidebar collapsed state, restored from and persisted to localStorage. */
export function useSidebarCollapsed(): [boolean, Dispatch<SetStateAction<boolean>>] {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? "1" : "0");
    } catch {
      // Ignore storage failures (private mode, etc.).
    }
  }, [collapsed]);

  return [collapsed, setCollapsed];
}
