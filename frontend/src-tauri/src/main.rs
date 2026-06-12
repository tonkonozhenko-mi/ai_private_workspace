use serde::Serialize;
use std::env;
use std::path::PathBuf;

#[derive(Serialize)]
struct SupervisorStatus {
    state: String,
    user_message: String,
    health_url: String,
    data_directory_hint: String,
    logs_directory_hint: String,
    execution_mode: String,
    backend_start_enabled: bool,
    safe_launch_contract: Vec<String>,
}

#[derive(Serialize)]
struct SupervisorLogPaths {
    logs_directory: String,
    launcher_log: String,
    backend_log: String,
    model_download_log: String,
    supervisor_state_file: String,
}

#[derive(Serialize)]
struct SupervisorPreflightItem {
    id: String,
    status: String,
    summary: String,
}

#[derive(Serialize)]
struct SupervisorPreflight {
    status: String,
    items: Vec<SupervisorPreflightItem>,
    safety_note: String,
}

#[derive(Serialize)]
struct RuntimeSelectionCandidate {
    id: String,
    priority: u8,
    manifest_path: String,
    runtime_kind: String,
    startup_enabled: bool,
    fallback_rule: String,
}

#[derive(Serialize)]
struct RuntimeSelectionStatus {
    status: String,
    backend_start_enabled: bool,
    selected_runtime: String,
    candidates: Vec<RuntimeSelectionCandidate>,
    safety_note: String,
}

#[derive(Serialize)]
struct AppOwnedStartupGate {
    status: String,
    backend_start_enabled: bool,
    startup_mode: String,
    preferred_runtime: String,
    health_url: String,
    required_gates: Vec<String>,
    safety_note: String,
}

fn app_data_dir() -> PathBuf {
    if cfg!(target_os = "macos") {
        let home = env::var("HOME").unwrap_or_else(|_| "~".to_string());
        return PathBuf::from(home).join("Library/Application Support/AI Private Workspace");
    }

    if cfg!(target_os = "windows") {
        let local_app_data = env::var("LOCALAPPDATA").unwrap_or_else(|_| "%LOCALAPPDATA%".to_string());
        return PathBuf::from(local_app_data).join("AI Private Workspace");
    }

    let home = env::var("HOME").unwrap_or_else(|_| "~".to_string());
    PathBuf::from(home).join(".local/share/AI Private Workspace")
}

fn logs_dir() -> PathBuf {
    app_data_dir().join("logs")
}

#[tauri::command]
fn get_supervisor_status() -> SupervisorStatus {
    SupervisorStatus {
        state: "read_only_preflight".to_string(),
        user_message: "Desktop supervisor bridge is ready for read-only status/log path checks. Backend startup is still disabled until the runtime bundle is frozen.".to_string(),
        health_url: "http://127.0.0.1:8000/health".to_string(),
        data_directory_hint: app_data_dir().display().to_string(),
        logs_directory_hint: logs_dir().display().to_string(),
        execution_mode: "read-only supervisor bridge; no process startup".to_string(),
        backend_start_enabled: false,
        safe_launch_contract: vec![
            "Do not start scan, index, rebuild, MCP, Agent, or model downloads on desktop launch.".to_string(),
            "Do not expose arbitrary shell execution to React.".to_string(),
            "Do not kill unknown processes on localhost ports.".to_string(),
            "Keep runtime data and logs outside the app bundle.".to_string(),
        ],
    }
}

#[tauri::command]
fn get_supervisor_log_paths() -> SupervisorLogPaths {
    let logs = logs_dir();
    SupervisorLogPaths {
        logs_directory: logs.display().to_string(),
        launcher_log: logs.join("desktop-launcher.log").display().to_string(),
        backend_log: logs.join("backend.log").display().to_string(),
        model_download_log: logs.join("model-downloads.log").display().to_string(),
        supervisor_state_file: app_data_dir().join("supervisor-state.json").display().to_string(),
    }
}

#[tauri::command]
fn get_supervisor_preflight() -> SupervisorPreflight {
    let status = get_supervisor_status();
    let paths = get_supervisor_log_paths();
    let items = vec![
        SupervisorPreflightItem {
            id: "backend-start-disabled".to_string(),
            status: "ok".to_string(),
            summary: format!("Backend start enabled: {}", status.backend_start_enabled),
        },
        SupervisorPreflightItem {
            id: "localhost-health-url".to_string(),
            status: "ok".to_string(),
            summary: status.health_url,
        },
        SupervisorPreflightItem {
            id: "app-owned-data-dir".to_string(),
            status: "ok".to_string(),
            summary: status.data_directory_hint,
        },
        SupervisorPreflightItem {
            id: "app-owned-logs-dir".to_string(),
            status: "ok".to_string(),
            summary: paths.logs_directory,
        },
    ];

    SupervisorPreflight {
        status: "ok".to_string(),
        items,
        safety_note: "Read-only Tauri commands expose status and paths only; they do not start processes or execute shell commands.".to_string(),
    }
}

#[tauri::command]
fn get_runtime_selection_status() -> RuntimeSelectionStatus {
    RuntimeSelectionStatus {
        status: "read_only_selection_contract".to_string(),
        backend_start_enabled: false,
        selected_runtime: "none_yet".to_string(),
        candidates: vec![
            RuntimeSelectionCandidate {
                id: "frozen-pyinstaller-runtime".to_string(),
                priority: 1,
                manifest_path: "build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json".to_string(),
                runtime_kind: "frozen_backend".to_string(),
                startup_enabled: false,
                fallback_rule: "If the frozen manifest or binary is missing/unhealthy, do not start unknown processes; fall back to read-only or staged developer runtime.".to_string(),
            },
            RuntimeSelectionCandidate {
                id: "staged-source-runtime".to_string(),
                priority: 2,
                manifest_path: "build/desktop/backend-runtime/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json".to_string(),
                runtime_kind: "developer_staged_source".to_string(),
                startup_enabled: false,
                fallback_rule: "Use only as a developer fallback until frozen runtime smoke checks pass.".to_string(),
            },
        ],
        safety_note: "Runtime selection is metadata-only for now. Tauri does not start backend processes until the app-owned frozen runtime passes explicit checks.".to_string(),
    }
}


#[tauri::command]
fn get_app_owned_startup_gate() -> AppOwnedStartupGate {
    AppOwnedStartupGate {
        status: "gate_ready_metadata_only".to_string(),
        backend_start_enabled: false,
        startup_mode: "manifest_gated_future_startup_no_process_start_yet".to_string(),
        preferred_runtime: "frozen-pyinstaller-runtime".to_string(),
        health_url: "http://127.0.0.1:8000/health".to_string(),
        required_gates: vec![
            "Frozen runtime manifest exists and points to an app-owned backend executable.".to_string(),
            "Developer-only frozen backend smoke has passed locally.".to_string(),
            "Startup records a spawned PID and shuts down only that PID.".to_string(),
            "If the port is occupied by an unknown process, do not kill it.".to_string(),
            "Open UI only after /health is ready.".to_string(),
        ],
        safety_note: "This command is read-only gate metadata. It does not start backend processes, run shell commands, kill ports, download models, or trigger scan/index/rebuild/MCP/Agent workflows.".to_string(),
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_supervisor_status,
            get_supervisor_log_paths,
            get_supervisor_preflight,
            get_runtime_selection_status,
            get_app_owned_startup_gate
        ])
        .run(tauri::generate_context!())
        .expect("error while running AI Private Workspace desktop shell");
}
