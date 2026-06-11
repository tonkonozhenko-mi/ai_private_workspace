use serde::Serialize;

#[derive(Serialize)]
struct SupervisorStatus {
    state: &'static str,
    user_message: &'static str,
    health_url: &'static str,
    data_directory_hint: &'static str,
    logs_directory_hint: &'static str,
    execution_mode: &'static str,
}

#[derive(Serialize)]
struct SupervisorLogPaths {
    launcher_log: &'static str,
    backend_log: &'static str,
    model_download_log: &'static str,
}

#[tauri::command]
fn get_supervisor_status() -> SupervisorStatus {
    SupervisorStatus {
        state: "scaffold",
        user_message: "Desktop supervisor bridge is scaffolded. Backend startup is still owned by the safe development scripts until runtime bundling is finalized.",
        health_url: "http://127.0.0.1:8000/health",
        data_directory_hint: "~/Library/Application Support/AI Private Workspace",
        logs_directory_hint: "~/Library/Application Support/AI Private Workspace/logs",
        execution_mode: "read-only bridge scaffold",
    }
}

#[tauri::command]
fn get_supervisor_log_paths() -> SupervisorLogPaths {
    SupervisorLogPaths {
        launcher_log: "~/Library/Application Support/AI Private Workspace/logs/macos-app-launcher.log",
        backend_log: "~/Library/Application Support/AI Private Workspace/logs/backend.log",
        model_download_log: "~/Library/Application Support/AI Private Workspace/logs/model-downloads.log",
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_supervisor_status,
            get_supervisor_log_paths
        ])
        .run(tauri::generate_context!())
        .expect("error while running AI Private Workspace desktop shell");
}
