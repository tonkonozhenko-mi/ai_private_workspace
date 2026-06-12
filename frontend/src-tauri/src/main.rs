use serde::{Deserialize, Serialize};
use std::env;
use std::fs::{self, File, OpenOptions};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Mutex, OnceLock};
use std::thread;
use std::time::{Duration, Instant};

static BACKEND_CHILD: OnceLock<Mutex<Option<Child>>> = OnceLock::new();

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

#[derive(Serialize)]
struct AppOwnedBackendProcessStatus {
    state: String,
    runtime_kind: String,
    pid: Option<u32>,
    health_url: String,
    backend_start_enabled: bool,
    data_directory: String,
    logs_directory: String,
    backend_log: String,
    message: String,
}

#[derive(Deserialize)]
struct FrozenRuntimeManifest {
    backend_executable: String,
}

fn backend_process_state() -> &'static Mutex<Option<Child>> {
    BACKEND_CHILD.get_or_init(|| Mutex::new(None))
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

fn backend_log_path() -> PathBuf {
    logs_dir().join("backend.log")
}

fn health_url() -> String {
    "http://127.0.0.1:8000/health".to_string()
}

fn runtime_manifest_candidates() -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    if let Ok(cwd) = env::current_dir() {
        candidates.push(cwd.join("build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"));
        candidates.push(cwd.join("../build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"));
    }
    if let Ok(exe) = env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            candidates.push(exe_dir.join("backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"));
            candidates.push(exe_dir.join("../Resources/backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"));
            candidates.push(exe_dir.join("../../Resources/backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"));
        }
    }
    candidates
}

fn resolve_frozen_backend_executable() -> Result<PathBuf, String> {
    for manifest_path in runtime_manifest_candidates() {
        if !manifest_path.exists() {
            continue;
        }
        let manifest_text = fs::read_to_string(&manifest_path)
            .map_err(|err| format!("Could not read frozen runtime manifest {}: {}", manifest_path.display(), err))?;
        let manifest: FrozenRuntimeManifest = serde_json::from_str(&manifest_text)
            .map_err(|err| format!("Could not parse frozen runtime manifest {}: {}", manifest_path.display(), err))?;
        let runtime_dir = manifest_path
            .parent()
            .ok_or_else(|| format!("Frozen runtime manifest has no parent directory: {}", manifest_path.display()))?;
        let executable = runtime_dir.join(manifest.backend_executable);
        if executable.exists() {
            return Ok(executable);
        }
        return Err(format!(
            "Frozen backend executable referenced by manifest is missing: {}",
            executable.display()
        ));
    }
    Err("Frozen backend runtime manifest is missing. Build it first with scripts/build_pyinstaller_backend_runtime.sh and smoke it with scripts/smoke_frozen_backend_runtime.sh.".to_string())
}

fn port_8000_is_busy() -> bool {
    TcpStream::connect(("127.0.0.1", 8000)).is_ok()
}

fn wait_for_backend_tcp(timeout: Duration) -> bool {
    let started = Instant::now();
    while started.elapsed() < timeout {
        if TcpStream::connect(("127.0.0.1", 8000)).is_ok() {
            return true;
        }
        thread::sleep(Duration::from_millis(250));
    }
    false
}

fn process_status_from_child(child: Option<&Child>, state: &str, message: &str) -> AppOwnedBackendProcessStatus {
    AppOwnedBackendProcessStatus {
        state: state.to_string(),
        runtime_kind: "frozen-pyinstaller-runtime".to_string(),
        pid: child.map(|current| current.id()),
        health_url: health_url(),
        backend_start_enabled: true,
        data_directory: app_data_dir().display().to_string(),
        logs_directory: logs_dir().display().to_string(),
        backend_log: backend_log_path().display().to_string(),
        message: message.to_string(),
    }
}

#[tauri::command]
fn get_supervisor_status() -> SupervisorStatus {
    SupervisorStatus {
        state: "app_owned_startup_available_after_manifest".to_string(),
        user_message: "Desktop supervisor bridge can start only the app-owned frozen backend runtime after the manifest exists. It never exposes arbitrary shell execution to React.".to_string(),
        health_url: health_url(),
        data_directory_hint: app_data_dir().display().to_string(),
        logs_directory_hint: logs_dir().display().to_string(),
        execution_mode: "narrow app-owned backend lifecycle; no generic shell execution".to_string(),
        backend_start_enabled: true,
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
            id: "backend-start-gated".to_string(),
            status: "ok".to_string(),
            summary: format!("Backend start enabled after frozen manifest gate: {}", status.backend_start_enabled),
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
        safety_note: "Tauri commands expose only app-owned backend lifecycle and path/status checks; they do not run arbitrary shell commands.".to_string(),
    }
}

#[tauri::command]
fn get_runtime_selection_status() -> RuntimeSelectionStatus {
    RuntimeSelectionStatus {
        status: "frozen_runtime_preferred".to_string(),
        backend_start_enabled: true,
        selected_runtime: "frozen-pyinstaller-runtime-after-manifest".to_string(),
        candidates: vec![
            RuntimeSelectionCandidate {
                id: "frozen-pyinstaller-runtime".to_string(),
                priority: 1,
                manifest_path: "build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json".to_string(),
                runtime_kind: "frozen_backend".to_string(),
                startup_enabled: true,
                fallback_rule: "If the frozen manifest or binary is missing/unhealthy, do not start unknown processes; return a clear blocked status.".to_string(),
            },
            RuntimeSelectionCandidate {
                id: "staged-source-runtime".to_string(),
                priority: 2,
                manifest_path: "build/desktop/backend-runtime/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json".to_string(),
                runtime_kind: "developer_staged_source".to_string(),
                startup_enabled: false,
                fallback_rule: "Do not use staged source runtime for packaged automatic startup; keep it as a developer fallback only.".to_string(),
            },
        ],
        safety_note: "Runtime selection can start only the app-owned frozen backend runtime. Missing manifest means blocked startup, not arbitrary fallback.".to_string(),
    }
}

#[tauri::command]
fn get_app_owned_startup_gate() -> AppOwnedStartupGate {
    AppOwnedStartupGate {
        status: "real_startup_gated_by_manifest".to_string(),
        backend_start_enabled: true,
        startup_mode: "manifest_gated_app_owned_backend_process".to_string(),
        preferred_runtime: "frozen-pyinstaller-runtime".to_string(),
        health_url: health_url(),
        required_gates: vec![
            "Frozen runtime manifest exists and points to an app-owned backend executable.".to_string(),
            "Developer-only frozen backend smoke has passed locally.".to_string(),
            "Startup records a spawned PID and shuts down only that PID.".to_string(),
            "If the port is occupied by an unknown process, do not kill it.".to_string(),
            "Open UI only after /health is ready.".to_string(),
        ],
        safety_note: "This gate allows only app-owned frozen backend startup. It does not run shell commands, kill ports, download models, or trigger scan/index/rebuild/MCP/Agent workflows.".to_string(),
    }
}

#[tauri::command]
fn get_app_owned_backend_process_status() -> Result<AppOwnedBackendProcessStatus, String> {
    let mut guard = backend_process_state()
        .lock()
        .map_err(|_| "Could not lock backend process state".to_string())?;
    if let Some(child) = guard.as_mut() {
        match child.try_wait() {
            Ok(Some(status)) => {
                let message = format!("App-owned backend process exited with status: {}", status);
                *guard = None;
                Ok(process_status_from_child(None, "stopped", &message))
            }
            Ok(None) => Ok(process_status_from_child(Some(child), "running", "App-owned backend process is running.")),
            Err(err) => Err(format!("Could not read backend process status: {}", err)),
        }
    } else {
        Ok(process_status_from_child(None, "not_started", "No app-owned backend process has been started by this desktop session."))
    }
}

#[tauri::command]
fn start_app_owned_backend_runtime() -> Result<AppOwnedBackendProcessStatus, String> {
    fs::create_dir_all(logs_dir()).map_err(|err| format!("Could not create logs directory: {}", err))?;
    fs::create_dir_all(app_data_dir()).map_err(|err| format!("Could not create app data directory: {}", err))?;

    let mut guard = backend_process_state()
        .lock()
        .map_err(|_| "Could not lock backend process state".to_string())?;
    if let Some(child) = guard.as_mut() {
        if child.try_wait().map_err(|err| format!("Could not check existing backend process: {}", err))?.is_none() {
            return Ok(process_status_from_child(Some(child), "already_running", "App-owned backend process is already running."));
        }
        *guard = None;
    }

    if port_8000_is_busy() {
        return Err("Port 8000 is already in use. AI Private Workspace will not kill unknown processes; stop the other process manually or configure a different port in a future build.".to_string());
    }

    let executable = resolve_frozen_backend_executable()?;
    let stdout_log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(backend_log_path())
        .map_err(|err| format!("Could not open backend log file: {}", err))?;
    let stderr_log: File = stdout_log
        .try_clone()
        .map_err(|err| format!("Could not clone backend log file handle: {}", err))?;

    let mut child = Command::new(&executable)
        .env("APP_ENV", "desktop")
        .env("HOST", "127.0.0.1")
        .env("PORT", "8000")
        .env("AI_WORKSPACE_APP_DATA_DIR", app_data_dir())
        .env("AI_WORKBENCH_DB_PATH", app_data_dir().join("workspace.db"))
        .stdin(Stdio::null())
        .stdout(Stdio::from(stdout_log))
        .stderr(Stdio::from(stderr_log))
        .spawn()
        .map_err(|err| format!("Could not start frozen backend runtime {}: {}", executable.display(), err))?;

    if !wait_for_backend_tcp(Duration::from_secs(15)) {
        let _ = child.kill();
        let _ = child.wait();
        return Err("Started app-owned backend process but localhost health port did not become ready in time. Check the backend log for details.".to_string());
    }

    let status = process_status_from_child(Some(&child), "running", "App-owned frozen backend runtime started and localhost health port is reachable.");
    *guard = Some(child);
    Ok(status)
}

#[tauri::command]
fn stop_app_owned_backend_runtime() -> Result<AppOwnedBackendProcessStatus, String> {
    let mut guard = backend_process_state()
        .lock()
        .map_err(|_| "Could not lock backend process state".to_string())?;
    if let Some(mut child) = guard.take() {
        let pid = child.id();
        child.kill().map_err(|err| format!("Could not stop app-owned backend process {}: {}", pid, err))?;
        let _ = child.wait();
        return Ok(process_status_from_child(None, "stopped", &format!("Stopped app-owned backend process {}.", pid)));
    }
    Ok(process_status_from_child(None, "not_started", "No app-owned backend process was started by this desktop session."))
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_supervisor_status,
            get_supervisor_log_paths,
            get_supervisor_preflight,
            get_runtime_selection_status,
            get_app_owned_startup_gate,
            get_app_owned_backend_process_status,
            start_app_owned_backend_runtime,
            stop_app_owned_backend_runtime
        ])
        .run(tauri::generate_context!())
        .expect("error while running AI Private Workspace desktop shell");
}
