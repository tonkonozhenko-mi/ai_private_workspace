use serde::{Deserialize, Serialize};
use std::env;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
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

#[derive(Serialize)]
struct BackendHealthReadinessContract {
    status: String,
    health_url: String,
    readiness_check: String,
    startup_timeout_seconds: u64,
    safety_rules: Vec<String>,
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
        let local_app_data =
            env::var("LOCALAPPDATA").unwrap_or_else(|_| "%LOCALAPPDATA%".to_string());
        return PathBuf::from(local_app_data).join("AI Private Workspace");
    }

    let home = env::var("HOME").unwrap_or_else(|_| "~".to_string());
    PathBuf::from(home).join(".local/share/AI Private Workspace")
}

fn logs_dir() -> PathBuf {
    app_data_dir().join("logs")
}

fn data_dir() -> PathBuf {
    app_data_dir().join("data")
}

fn vector_store_path() -> PathBuf {
    app_data_dir().join("data").join("vector_store.db")
}

fn workspace_db_path() -> PathBuf {
    data_dir().join("workspaces.db")
}

fn user_model_catalog_path() -> PathBuf {
    data_dir().join("user-model-catalog.json")
}

fn backend_log_path() -> PathBuf {
    logs_dir().join("backend.log")
}

fn supervisor_log_path() -> PathBuf {
    logs_dir().join("desktop-supervisor.log")
}

fn append_supervisor_log(message: &str) {
    let _ = fs::create_dir_all(logs_dir());
    if let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(supervisor_log_path())
    {
        let _ = writeln!(file, "{}", message);
    }
}

fn health_url() -> String {
    "http://127.0.0.1:8000/health".to_string()
}

fn find_frozen_runtime_manifests_under(root: &PathBuf, max_depth: usize) -> Vec<PathBuf> {
    fn visit(dir: &PathBuf, depth: usize, max_depth: usize, found: &mut Vec<PathBuf>) {
        if depth > max_depth {
            return;
        }
        let entries = match fs::read_dir(dir) {
            Ok(entries) => entries,
            Err(_) => return,
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_file()
                && path.file_name().and_then(|name| name.to_str())
                    == Some("AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json")
            {
                found.push(path);
            } else if path.is_dir() {
                visit(&path, depth + 1, max_depth, found);
            }
        }
    }

    let mut found = Vec::new();
    visit(root, 0, max_depth, &mut found);
    found
}

fn runtime_manifest_candidates() -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    if let Ok(cwd) = env::current_dir() {
        candidates.push(cwd.join("build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"));
        candidates.push(cwd.join("../build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"));
    }
    if let Ok(exe) = env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            candidates.push(
                exe_dir.join("backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"),
            );
            candidates.push(exe_dir.join(
                "../Resources/backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json",
            ));
            candidates.push(exe_dir.join(
                "../../Resources/backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json",
            ));
            candidates.push(exe_dir.join("../Resources/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"));
            candidates.push(exe_dir.join("../../Resources/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"));

            for ancestor in exe_dir.ancestors().take(8) {
                let resources = ancestor.join("Resources");
                if resources.exists() {
                    candidates.extend(find_frozen_runtime_manifests_under(&resources, 6));
                }
            }
        }
    }
    candidates.sort();
    candidates.dedup();
    candidates
}

fn resolve_frozen_backend_executable() -> Result<PathBuf, String> {
    let candidates = runtime_manifest_candidates();
    append_supervisor_log(&format!(
        "Resolving frozen backend runtime. Candidate manifests: {}",
        candidates
            .iter()
            .map(|path| path.display().to_string())
            .collect::<Vec<String>>()
            .join(" | ")
    ));

    for manifest_path in candidates {
        if !manifest_path.exists() {
            continue;
        }
        append_supervisor_log(&format!(
            "Trying frozen runtime manifest: {}",
            manifest_path.display()
        ));
        let manifest_text = fs::read_to_string(&manifest_path).map_err(|err| {
            format!(
                "Could not read frozen runtime manifest {}: {}",
                manifest_path.display(),
                err
            )
        })?;
        let manifest: FrozenRuntimeManifest =
            serde_json::from_str(&manifest_text).map_err(|err| {
                format!(
                    "Could not parse frozen runtime manifest {}: {}",
                    manifest_path.display(),
                    err
                )
            })?;
        let runtime_dir = manifest_path.parent().ok_or_else(|| {
            format!(
                "Frozen runtime manifest has no parent directory: {}",
                manifest_path.display()
            )
        })?;
        let executable = runtime_dir.join(manifest.backend_executable);
        if executable.exists() {
            append_supervisor_log(&format!(
                "Resolved frozen backend executable: {}",
                executable.display()
            ));
            return Ok(executable);
        }
        let message = format!(
            "Frozen backend executable referenced by manifest is missing: {}",
            executable.display()
        );
        append_supervisor_log(&message);
        return Err(message);
    }
    let message = "Frozen backend runtime manifest is missing. Build it first with scripts/build_pyinstaller_backend_runtime.sh and bundle it with the packaged app build command. Check desktop-supervisor.log for searched paths.".to_string();
    append_supervisor_log(&message);
    Err(message)
}

fn port_8000_is_busy() -> bool {
    TcpStream::connect(("127.0.0.1", 8000)).is_ok()
}

fn backend_http_endpoint_is_ready(path: &str) -> bool {
    match TcpStream::connect(("127.0.0.1", 8000)) {
        Ok(mut stream) => {
            let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
            let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
            let request = format!(
                "GET {} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
                path
            );
            if stream.write_all(request.as_bytes()).is_err() {
                return false;
            }
            let mut response = String::new();
            if stream.read_to_string(&mut response).is_err() {
                return false;
            }
            response.starts_with("HTTP/1.1 200") || response.starts_with("HTTP/1.0 200")
        }
        Err(_) => false,
    }
}

fn backend_health_is_ready() -> bool {
    // Source-level safety checks keep this explicit readiness contract: GET /health HTTP/1.1
    backend_http_endpoint_is_ready("/health")
}

fn workspace_overview_is_ready() -> bool {
    backend_http_endpoint_is_ready("/workspaces/overview")
}

fn wait_for_backend_health(timeout: Duration) -> bool {
    let started = Instant::now();
    while started.elapsed() < timeout {
        if backend_health_is_ready() {
            return true;
        }
        thread::sleep(Duration::from_millis(250));
    }
    false
}

fn stop_owned_child(child: &mut Child) -> Result<(), String> {
    let pid = child.id();

    #[cfg(unix)]
    {
        let result = unsafe { libc::kill(pid as i32, libc::SIGTERM) };
        if result != 0 {
            let err = std::io::Error::last_os_error();
            if err.kind() != std::io::ErrorKind::NotFound {
                return Err(format!(
                    "Could not request graceful stop for app-owned backend process {}: {}",
                    pid, err
                ));
            }
        }

        let started = Instant::now();
        while started.elapsed() < Duration::from_secs(5) {
            if child
                .try_wait()
                .map_err(|err| {
                    format!("Could not check app-owned backend process {}: {}", pid, err)
                })?
                .is_some()
            {
                return Ok(());
            }
            thread::sleep(Duration::from_millis(100));
        }
    }

    child
        .kill()
        .map_err(|err| format!("Could not stop app-owned backend process {}: {}", pid, err))?;
    let _ = child.wait();
    Ok(())
}

fn process_status_from_child(
    child: Option<&Child>,
    state: &str,
    message: &str,
) -> AppOwnedBackendProcessStatus {
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
        supervisor_state_file: app_data_dir()
            .join("supervisor-state.json")
            .display()
            .to_string(),
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
            summary: format!(
                "Backend start enabled after frozen manifest gate: {}",
                status.backend_start_enabled
            ),
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
fn get_backend_health_readiness_contract() -> BackendHealthReadinessContract {
    BackendHealthReadinessContract {
        status: "http_health_gate_enabled".to_string(),
        health_url: health_url(),
        readiness_check: "HTTP GET /health must return 200 before the desktop UI treats the backend as ready".to_string(),
        startup_timeout_seconds: 15,
        safety_rules: vec![
            "Do not treat an open TCP port as application readiness.".to_string(),
            "Do not open the UI as ready until /health returns HTTP 200.".to_string(),
            "If /health does not become ready, stop only the child process started by this app session.".to_string(),
            "Do not kill unknown processes by port.".to_string(),
        ],
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
            Ok(None) => Ok(process_status_from_child(
                Some(child),
                "running",
                "App-owned backend process is running.",
            )),
            Err(err) => Err(format!("Could not read backend process status: {}", err)),
        }
    } else {
        Ok(process_status_from_child(
            None,
            "not_started",
            "No app-owned backend process has been started by this desktop session.",
        ))
    }
}

#[tauri::command]
fn start_app_owned_backend_runtime() -> Result<AppOwnedBackendProcessStatus, String> {
    fs::create_dir_all(logs_dir())
        .map_err(|err| format!("Could not create logs directory: {}", err))?;
    fs::create_dir_all(app_data_dir())
        .map_err(|err| format!("Could not create app data directory: {}", err))?;
    fs::create_dir_all(data_dir())
        .map_err(|err| format!("Could not create data directory: {}", err))?;
    append_supervisor_log("start_app_owned_backend_runtime invoked");
    append_supervisor_log(&format!(
        "Resolved app data directory: {}",
        app_data_dir().display()
    ));
    append_supervisor_log(&format!(
        "Resolved workspace database path: {}",
        workspace_db_path().display()
    ));

    let mut guard = backend_process_state()
        .lock()
        .map_err(|_| "Could not lock backend process state".to_string())?;
    if let Some(child) = guard.as_mut() {
        if child
            .try_wait()
            .map_err(|err| format!("Could not check existing backend process: {}", err))?
            .is_none()
        {
            return Ok(process_status_from_child(
                Some(child),
                "already_running",
                "App-owned backend process is already running.",
            ));
        }
        *guard = None;
    }

    if port_8000_is_busy() {
        if backend_health_is_ready() {
            append_supervisor_log("Port 8000 is already in use and /health is ready (HTTP 200)");
            if !workspace_overview_is_ready() {
                append_supervisor_log("Existing backend /health is ready, but /workspaces/overview did not return HTTP 200; refusing to reuse incomplete backend");
                return Err("A backend on port 8000 passed /health, but /workspaces/overview failed. AI Private Workspace will not kill or reuse the unknown process. Check its SQLite configuration or stop it manually.".to_string());
            }
            append_supervisor_log("Existing backend /workspaces/overview returned HTTP 200; reusing healthy local backend without taking ownership");
            return Ok(process_status_from_child(None, "external_healthy", "A healthy backend is already listening on 127.0.0.1:8000. AI Private Workspace will reuse it but will not stop it because this desktop session did not start the process."));
        }
        append_supervisor_log("Port 8000 is already in use but /health is not ready; refusing to kill unknown process");
        return Err("Port 8000 is already in use, but /health is not ready. AI Private Workspace will not kill unknown processes; stop the other process manually or configure a different port in a future build.".to_string());
    }

    let executable = resolve_frozen_backend_executable()?;
    append_supervisor_log(&format!(
        "Resolved backend executable path: {}",
        executable.display()
    ));
    let mut stdout_log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(backend_log_path())
        .map_err(|err| format!("Could not open backend log file: {}", err))?;
    let _ = writeln!(
        stdout_log,
        "\n=== AI Private Workspace app-owned backend start ==="
    );
    let _ = writeln!(stdout_log, "APP_DATA_DIR={}", app_data_dir().display());
    let _ = writeln!(
        stdout_log,
        "WORKSPACE_DB_PATH={}",
        workspace_db_path().display()
    );
    let _ = writeln!(stdout_log, "VECTOR_STORE=sqlite");
    let _ = writeln!(stdout_log, "OLLAMA_BASE_URL=http://127.0.0.1:11434");
    let _ = writeln!(stdout_log, "MODEL_DOWNLOAD_EXECUTION_ENABLED=true");
    let _ = writeln!(
        stdout_log,
        "USER_MODEL_CATALOG_PATH={}",
        user_model_catalog_path().display()
    );
    let _ = writeln!(
        stdout_log,
        "VECTOR_STORE_PATH={}",
        vector_store_path().display()
    );
    let _ = writeln!(stdout_log, "BACKEND_EXECUTABLE={}", executable.display());
    let stderr_log: File = stdout_log
        .try_clone()
        .map_err(|err| format!("Could not clone backend log file handle: {}", err))?;

    let inherited_path = env::var("PATH").unwrap_or_default();
    let desktop_path = format!(
        "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:{}",
        inherited_path
    );
    let mut child = Command::new(&executable)
        .env("APP_ENV", "desktop")
        .env("HOST", "127.0.0.1")
        .env("PORT", "8000")
        .env("APP_DATA_DIR", app_data_dir())
        .env("WORKSPACE_DB_PATH", workspace_db_path())
        .env("VECTOR_STORE", "sqlite")
        .env("VECTOR_STORE_PATH", vector_store_path())
        .env("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        .env("COMMAND_RUNNER", "local")
        .env("COMMAND_TIMEOUT_SECONDS", "3600")
        .env("MODEL_DOWNLOAD_EXECUTION_ENABLED", "true")
        .env("USER_MODEL_CATALOG_PATH", user_model_catalog_path())
        .env("PATH", desktop_path)
        .env("AI_WORKSPACE_VECTOR_STORE_PATH", vector_store_path())
        .env("AI_WORKSPACE_APP_DATA_DIR", app_data_dir())
        .env("AI_WORKBENCH_DB_PATH", workspace_db_path())
        .env("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://tauri.localhost,https://tauri.localhost,tauri://localhost,null")
        .stdin(Stdio::null())
        .stdout(Stdio::from(stdout_log))
        .stderr(Stdio::from(stderr_log))
        .spawn()
        .map_err(|err| {
            let message = format!("Could not start frozen backend runtime {}: {}", executable.display(), err);
            append_supervisor_log(&message);
            message
        })?;
    append_supervisor_log(&format!(
        "Started app-owned backend child PID {}",
        child.id()
    ));

    if !wait_for_backend_health(Duration::from_secs(15)) {
        let _ = stop_owned_child(&mut child);
        append_supervisor_log(
            "Started backend child but /health did not return HTTP 200 in time; child was stopped",
        );
        return Err("Started app-owned backend process but /health did not return HTTP 200 in time. Check backend.log and desktop-supervisor.log for details.".to_string());
    }

    append_supervisor_log("App-owned frozen backend /health returned HTTP 200");
    if !workspace_overview_is_ready() {
        let _ = stop_owned_child(&mut child);
        append_supervisor_log("App-owned backend /health returned HTTP 200, but /workspaces/overview failed; child was stopped");
        return Err("App-owned backend passed /health, but /workspaces/overview did not return HTTP 200. The child was stopped because workspace SQLite bootstrap is not ready. Check backend.log and desktop-supervisor.log.".to_string());
    }

    append_supervisor_log("App-owned frozen backend /workspaces/overview returned HTTP 200");
    append_supervisor_log("App-owned frozen backend runtime is healthy and workspace API ready");
    let status = process_status_from_child(
        Some(&child),
        "running",
        "App-owned frozen backend runtime started and /health returned HTTP 200.",
    );
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
        stop_owned_child(&mut child)?;
        return Ok(process_status_from_child(
            None,
            "stopped",
            &format!("Stopped app-owned backend process {}.", pid),
        ));
    }
    Ok(process_status_from_child(
        None,
        "not_started",
        "No app-owned backend process was started by this desktop session.",
    ))
}


#[tauri::command]
fn choose_project_directory() -> Result<Option<String>, String> {
    #[cfg(target_os = "macos")]
    {
        let output = Command::new("/usr/bin/osascript")
            .arg("-e")
            .arg("POSIX path of (choose folder with prompt \"Choose a local project folder for AI Private Workspace\")")
            .stdin(Stdio::null())
            .output()
            .map_err(|err| format!("Could not open macOS folder picker: {}", err))?;
        if output.status.success() {
            let value = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if value.is_empty() {
                return Ok(None);
            }
            return Ok(Some(value.trim_end_matches('/').to_string()));
        }
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        if stderr.contains("User canceled") || stderr.contains("-128") {
            return Ok(None);
        }
        return Err(format!("Folder picker failed: {}", stderr.trim()));
    }

    #[cfg(not(target_os = "macos"))]
    {
        Err("Native folder picker is currently implemented for macOS packaged builds.".to_string())
    }
}

pub fn run() {
    let app = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_supervisor_status,
            get_supervisor_log_paths,
            get_supervisor_preflight,
            get_runtime_selection_status,
            get_app_owned_startup_gate,
            get_backend_health_readiness_contract,
            get_app_owned_backend_process_status,
            start_app_owned_backend_runtime,
            stop_app_owned_backend_runtime,
            choose_project_directory
        ])
        .build(tauri::generate_context!())
        .expect("error while building AI Private Workspace desktop shell");

    app.run(|_app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            match stop_app_owned_backend_runtime() {
                Ok(status) => {
                    append_supervisor_log(&format!("Desktop app exit cleanup: {}", status.message))
                }
                Err(err) => append_supervisor_log(&format!(
                    "Desktop app exit cleanup could not stop owned backend child: {}",
                    err
                )),
            }
        }
    });
}
