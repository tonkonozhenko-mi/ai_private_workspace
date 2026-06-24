import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tauriConf from "./src-tauri/tauri.conf.json";

// Inject the real app version (from tauri.conf.json) at build time so the UI can
// display it. This lets users confirm an auto-update actually changed the version.
export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(tauriConf.version),
  },
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Function form (rather than an object map) so it stays type-compatible
        // across Vite/Rollup major bumps: split React into its own chunk.
        manualChunks(id: string) {
          if (
            id.indexOf("/node_modules/react/") !== -1 ||
            id.indexOf("/node_modules/react-dom/") !== -1
          ) {
            return "react";
          }
        },
      },
    },
  },
});
