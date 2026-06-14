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
        manualChunks: {
          react: ["react", "react-dom"],
        },
      },
    },
  },
});
