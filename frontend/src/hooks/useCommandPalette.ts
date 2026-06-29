import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

import { getWorkspaceLatestScan } from "../api/client";

/**
 * Owns the command-palette state: whether it's open (Cmd/Ctrl-K toggles it from
 * anywhere) and the current project's file list, loaded lazily when the palette
 * opens so it can offer file search. Extracted from App.tsx to keep the root
 * component focused on composition.
 */
export function useCommandPalette(args: {
  selectedWorkspaceId: string | null;
  selectedGroupId: string | null;
}): {
  paletteOpen: boolean;
  setPaletteOpen: Dispatch<SetStateAction<boolean>>;
  paletteFiles: string[];
} {
  const { selectedWorkspaceId, selectedGroupId } = args;
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteFiles, setPaletteFiles] = useState<string[]>([]);

  // Cmd/Ctrl-K opens the command palette from anywhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Load the current project's file list (for palette file search) when the
  // palette opens. Cheap: it's the cached scan, fetched at most once per open.
  useEffect(() => {
    if (!paletteOpen || !selectedWorkspaceId || selectedGroupId) return;
    const controller = new AbortController();
    getWorkspaceLatestScan(selectedWorkspaceId, { signal: controller.signal })
      .then((scan) => {
        if (!controller.signal.aborted) setPaletteFiles(scan.files.map((f) => f.path));
      })
      .catch(() => {
        if (!controller.signal.aborted) setPaletteFiles([]);
      });
    return () => controller.abort();
  }, [paletteOpen, selectedWorkspaceId, selectedGroupId]);

  return { paletteOpen, setPaletteOpen, paletteFiles };
}
