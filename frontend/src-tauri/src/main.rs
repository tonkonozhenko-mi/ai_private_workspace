#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // Safe shell scaffold only.
    // Backend supervision is intentionally not implemented here yet.
    // Future work: start the app-owned backend process, poll /health,
    // surface calm startup states, and stop only the PID owned by this app.
    tauri::Builder::default()
        .setup(|_app| {
            // No scans, indexes, shell commands, model downloads, MCP servers,
            // or agent execution are started from this scaffold.
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("failed to run AI Private Workspace desktop shell");
}
