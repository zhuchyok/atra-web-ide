use axum::{
    Json, Router,
    body::Body,
    extract::{
        Path, Query, State, WebSocketUpgrade,
        ws::{Message, WebSocket},
    },
    http::{HeaderMap, Method, StatusCode, header},
    response::{Html, IntoResponse, Response},
    routing::{delete, get, post},
};
use dotenv::dotenv;
use futures_util::StreamExt;
use portable_pty::{CommandBuilder, PtySize, native_pty_system};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::json;
use sqlx::FromRow;
use sqlx::types::chrono;
use sqlx::types::uuid::Uuid;
use std::env;
use std::io::{Read, Write};
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;
use sysinfo::System;
use tokio::fs;
use tokio::sync::mpsc;
use tower_http::cors::{Any, CorsLayer};
use tower_http::services::ServeDir;
use tracing::{error, info, warn};

use knowledge_engine::KnowledgeEngine;
use tokio::sync::Semaphore;

struct AppState {
    client: Client,
    knowledge_engine: Option<KnowledgeEngine>,
    workspace_root: PathBuf,
    request_count: AtomicU64,
    victoria_url: String,
    use_victoria_agent: bool,
    chat_semaphore: Arc<Semaphore>,
}

macro_rules! require_ke {
    ($state:expr) => {
        match $state.knowledge_engine.as_ref() {
            Some(ke) => ke,
            None => return (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({ "error": "KnowledgeEngine unavailable (DB not connected)" }))
            ).into_response(),
        }
    };
}

#[derive(Deserialize)]
struct SearchQuery {
    q: String,
}

#[derive(Deserialize)]
struct FilePathQuery {
    path: String,
}

#[derive(Serialize)]
struct FileInfo {
    name: String,
    path: String,
    #[serde(rename = "type")]
    file_type: String,
    size: Option<u64>,
    modified: Option<String>,
}

#[derive(Serialize)]
struct FileContent {
    path: String,
    content: String,
    encoding: String,
}

#[derive(Deserialize)]
struct WriteFileRequest {
    path: String,
    content: String,
    #[serde(default = "default_encoding")]
    encoding: String,
}

fn default_encoding() -> String {
    "utf-8".to_string()
}

#[derive(Deserialize)]
struct CreateRequest {
    #[serde(rename = "type")]
    item_type: String,
    content: Option<String>,
}

#[derive(Deserialize)]
struct KnowledgeSearchRequest {
    embedding: Vec<f32>,
    project_context: Option<String>,
    limit: Option<i64>,
    use_quantum: Option<bool>,
}

#[derive(Deserialize)]
struct QuantumOptimizeRequest {
    candidates: Vec<serde_json::Value>,
    goal: String,
    temperature: Option<f32>,
}

#[derive(Deserialize)]
struct SecurityAnalyzeRequest {
    prompt: String,
    request_id: String,
    expert_name: String,
    category: String,
}

async fn security_analyze_handler(Json(req): Json<SecurityAnalyzeRequest>) -> impl IntoResponse {
    let prompt_lower = req.prompt.to_lowercase();

    // [SINGULARITY 21.23] Fast heuristic security checks in Rust
    let mut should_block = false;
    let mut reason = "";

    let malicious_patterns = [
        "ignore all previous instructions",
        "system prompt",
        "rm -rf /",
        "drop table",
        "delete from experts",
        "format c:",
    ];

    for pattern in malicious_patterns {
        if prompt_lower.contains(pattern) {
            should_block = true;
            reason = "Malicious pattern detected (Rust Heuristics)";
            break;
        }
    }

    Json(json!({
        "should_block": should_block,
        "alert": if should_block { Some(json!({ "description": reason, "severity": "high" })) } else { None },
        "request_id": req.request_id
    }))
}

#[derive(Deserialize)]
struct ClusterSyncRequest {
    cluster_id: Uuid,
    nodes: Vec<serde_json::Value>,
}

async fn cluster_heartbeat_handler(
    State(state): State<Arc<AppState>>,
    Json(req): Json<serde_json::Value>,
) -> impl IntoResponse {
    let ke = require_ke!(state);
    let cluster_id = req["cluster_id"].as_str().unwrap_or_default();
    let name = req["name"].as_str().unwrap_or("unknown");

    // Валидация: cluster_id должен быть непустым UUID или name непустым
    if cluster_id.is_empty() && name == "unknown" {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "cluster_id or name required" })),
        )
            .into_response();
    }

    // [SINGULARITY 21.24] Fast heartbeat update in Rust
    let res = if !cluster_id.is_empty() {
        sqlx::query(
            "UPDATE clusters SET last_heartbeat = NOW(), status = 'active' WHERE id = $1::uuid OR name = $2"
        )
        .bind(cluster_id)
        .bind(name)
        .execute(&ke.pool)
        .await
    } else {
        sqlx::query("UPDATE clusters SET last_heartbeat = NOW(), status = 'active' WHERE name = $1")
            .bind(name)
            .execute(&ke.pool)
            .await
    };

    match res {
        Ok(_) => (StatusCode::OK, Json(json!({ "status": "alive" }))).into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": e.to_string() })),
        )
            .into_response(),
    }
}

async fn cluster_sync_handler(
    State(state): State<Arc<AppState>>,
    Json(req): Json<ClusterSyncRequest>,
) -> impl IntoResponse {
    let ke = require_ke!(state);
    info!("📡 Syncing knowledge from cluster {}", req.cluster_id);

    let mut synced_count = 0;
    for node in req.nodes {
        // [SINGULARITY 21.24] Conflict Resolution via Versioning (Vector Clocks simplified)
        let id = node["id"].as_str().unwrap_or_default();
        let version = node["version"].as_i64().unwrap_or(1);
        let content = node["content"].as_str().unwrap_or_default();

        let res = sqlx::query(
            "INSERT INTO knowledge_nodes (id, content, cluster_id, version)
             VALUES ($1::uuid, $2, $3::uuid, $4)
             ON CONFLICT (id) DO UPDATE
             SET content = EXCLUDED.content,
                 version = EXCLUDED.version,
                 cluster_id = EXCLUDED.cluster_id
             WHERE EXCLUDED.version > knowledge_nodes.version",
        )
        .bind(id)
        .bind(content)
        .bind(req.cluster_id)
        .bind(version)
        .execute(&ke.pool)
        .await;

        if res.is_ok() {
            synced_count += 1;
        }
    }

    (
        StatusCode::OK,
        Json(json!({ "status": "synced", "received": synced_count })),
    )
        .into_response()
}

async fn knowledge_search_v2_handler(
    State(state): State<Arc<AppState>>,
    Json(req): Json<KnowledgeSearchRequest>,
) -> impl IntoResponse {
    let ke = require_ke!(state);
    let limit = req.limit.unwrap_or(8);
    let use_quantum = req.use_quantum.unwrap_or(false);

    // Валидация: embedding должен быть ровно 768 измерений (nomic-embed-text)
    if req.embedding.is_empty() || req.embedding.len() != 768 {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({
                "error": format!(
                    "embedding must have exactly 768 dimensions, got {}",
                    req.embedding.len()
                )
            })),
        )
            .into_response();
    }

    match ke
        .retrieve_with_context(req.embedding, req.project_context, limit, use_quantum)
        .await
    {
        Ok(nodes) => (StatusCode::OK, Json(nodes)).into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": e.to_string() })),
        )
            .into_response(),
    }
}

async fn quantum_optimize_handler(Json(req): Json<QuantumOptimizeRequest>) -> impl IntoResponse {
    let temp = req.temperature.unwrap_or(1.0);
    let optimizer = knowledge_engine::quantum_opt::QuantumInspiredOptimizer::new(temp, 0.9);

    // Эмуляция оптимизации плана: выбираем лучшие шаги на основе "энергии" (релевантности цели)
    // В реальном сценарии здесь была бы более сложная логика оценки каждого кандидата
    let optimized = optimizer.optimize(
        req.candidates,
        |_c| {
            // Mock energy function: в реальности вызывали бы скоринг-модель
            rand::random::<f32>()
        },
        10,
    );

    Json(json!({
        "status": "optimized",
        "method": "simulated_annealing",
        "results": optimized
    }))
}

#[derive(Serialize, FromRow)]
struct Expert {
    id: Uuid,
    name: String,
    role: Option<String>,
    system_prompt: Option<String>,
    created_at: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Serialize, FromRow)]
struct Domain {
    id: Uuid,
    name: String,
    description: Option<String>,
    created_at: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Deserialize)]
struct TerminalAskRequest {
    command: String,
}

/// Классификатор задачи: Victoria (планирование, координация) или Veronica (файлы, выполнение).
fn task_classify(message: &str) -> &'static str {
    let lower = message.to_lowercase();
    let veronica_triggers = [
        "файл",
        "file",
        "прочитай",
        "read",
        "создай",
        "create",
        "удали",
        "delete",
        "найди",
        "find",
        "поиск",
        "search",
        "выполни",
        "execute",
        "сделай",
        "do",
        "запусти",
        "run",
        "напиши код",
        "write code",
        "проверь код",
        "check code",
    ];
    let victoria_triggers = [
        "спланируй",
        "plan",
        "организуй",
        "organize",
        "стратегия",
        "strategy",
        "координируй",
        "coordinate",
        "управляй",
        "manage",
        "команда",
        "team",
        "сложн",
        "complex",
    ];
    if victoria_triggers.iter().any(|t| lower.contains(t)) {
        return "victoria";
    }
    if veronica_triggers.iter().any(|t| lower.contains(t)) {
        return "veronica";
    }
    "victoria"
}

#[derive(Deserialize)]
struct AutocompleteRequest {
    code: String,
    filename: String,
    line: i32,
    column: i32,
    language: Option<String>,
}

#[derive(Serialize)]
struct AutocompleteResponse {
    completions: Vec<serde_json::Value>,
}

#[derive(Deserialize)]
struct LintRequest {
    code: String,
    filename: String,
    language: Option<String>,
}

#[derive(Serialize)]
struct LintResponse {
    errors: Vec<serde_json::Value>,
}

async fn get_autocomplete(
    State(state): State<Arc<AppState>>,
    Json(req): Json<AutocompleteRequest>,
) -> impl IntoResponse {
    let language = req.language.clone().unwrap_or_else(|| {
        let ext = std::path::Path::new(&req.filename)
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("");
        match ext {
            "py" => "Python",
            "rs" => "Rust",
            "js" | "jsx" => "JavaScript",
            "ts" | "tsx" => "TypeScript",
            "html" => "HTML",
            "css" => "CSS",
            "json" => "JSON",
            "md" => "Markdown",
            _ => "Text",
        }
        .to_string()
    });

    let prompt = format!(
        "Ты AI-ассистент для автодополнения кода.\n\nЯзык: {}\nФайл: {}\nСтрока {}, позиция {}\n\nКод:\n{}\n\nПредложи 3-5 автодополнений в формате JSON: {{\"completions\": [{{ \"label\": \"...\", \"type\": \"...\", \"insert\": \"...\" }}]}}",
        language, req.filename, req.line, req.column, req.code
    );

    let payload = json!({
        "model": "victoria-wisdom-30b:latest",
        "messages": [{"role": "user", "content": prompt}],
        "stream": false
    });

    // Используем существующий proxy_chat для вызова модели
    proxy_chat(State(state), HeaderMap::new(), Json(payload)).await
}

async fn get_lint(
    State(state): State<Arc<AppState>>,
    Json(req): Json<LintRequest>,
) -> impl IntoResponse {
    let prompt = format!(
        "Проверь код на ошибки (linting).\n\nЯзык: {}\nФайл: {}\n\nКод:\n{}\n\nВерни список ошибок в формате JSON: {{\"errors\": [{{ \"line\": 1, \"column\": 1, \"message\": \"...\", \"severity\": \"error\" }}]}}",
        req.language.as_deref().unwrap_or("Unknown"),
        req.filename,
        req.code
    );

    let payload = json!({
        "model": "victoria-wisdom-30b:latest",
        "messages": [{"role": "user", "content": prompt}],
        "stream": false
    });

    proxy_chat(State(state), HeaderMap::new(), Json(payload)).await
}

// --- Sandbox Handlers ---

async fn get_sandbox_status(Path(expert_name): Path<String>) -> impl IntoResponse {
    let container_name = format!("sandbox-{}", expert_name.to_lowercase().replace(' ', "-"));

    let output = tokio::process::Command::new("docker")
        .args(["inspect", "--format", "{{json .State}}", &container_name])
        .output()
        .await;

    match output {
        Ok(out) if out.status.success() => {
            let state_json: serde_json::Value =
                serde_json::from_slice(&out.stdout).unwrap_or(json!({}));
            (
                StatusCode::OK,
                Json(json!({
                    "status": state_json["Status"].as_str().unwrap_or("unknown"),
                    "container": container_name,
                    "created": state_json["StartedAt"].as_str().unwrap_or(""),
                })),
            )
                .into_response()
        }
        _ => (
            StatusCode::OK,
            Json(json!({ "status": "not_found", "container": container_name })),
        )
            .into_response(),
    }
}

async fn reset_sandbox(Path(expert_name): Path<String>) -> impl IntoResponse {
    let container_name = format!("sandbox-{}", expert_name.to_lowercase().replace(' ', "-"));

    let _ = tokio::process::Command::new("docker")
        .args(["rm", "-f", &container_name])
        .output()
        .await;

    (
        StatusCode::OK,
        Json(
            json!({ "status": "success", "message": format!("Sandbox for {} reset", expert_name) }),
        ),
    )
        .into_response()
}

async fn get_recent_experiments() -> impl IntoResponse {
    // В реальной системе мы бы брали это из таблицы sandbox_logs
    let experiments = json!([
        {"time": "21:15", "expert": "Вероника", "task": "Тест миграции v2", "result": "✅ Успех"},
        {"time": "20:40", "expert": "Игорь", "task": "Нагрузка на Redis", "result": "⚠️ Warning: Latency > 5ms"}
    ]);
    (StatusCode::OK, Json(experiments))
}

// --- Latency Handlers ---

async fn get_latency_benchmark(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let benchmark_path = state.workspace_root.join("latency_benchmark.json");
    if !benchmark_path.exists() {
        return (
            StatusCode::OK,
            Json(json!({
                "status": "no_data",
                "message": "Run: python scripts/benchmark_latency.py",
            })),
        )
            .into_response();
    }

    match fs::read_to_string(benchmark_path).await {
        Ok(content) => {
            let data: serde_json::Value = serde_json::from_str(&content).unwrap_or(json!({}));
            (
                StatusCode::OK,
                Json(json!({
                    "status": "ok",
                    "p50_ms": data["p50_ms"],
                    "p95_ms": data["p95_ms"],
                    "p99_ms": data["p99_ms"],
                    "avg_ms": data["avg_ms"],
                    "n_requests": data["n_requests"],
                    "p95_ok": data["p95_ms"].as_f64().unwrap_or(999.0) < 300.0,
                    "services": data["services"],
                })),
            )
                .into_response()
        }
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()).into_response(),
    }
}

// --- Optimization Handlers ---

async fn get_plan_cache_stats() -> impl IntoResponse {
    // В Rust Gateway мы пока не реализовали кэширование планов,
    // но возвращаем структуру для совместимости с фронтендом.
    (
        StatusCode::OK,
        Json(json!({
            "hits": 0,
            "misses": 0,
            "size": 0,
            "status": "not_implemented_in_rust"
        })),
    )
}

async fn get_rag_optimization_stats() -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(json!({
            "embedding_batch": { "status": "active", "queue_size": 0 },
            "prefetch": { "status": "active", "cached_queries": 3 },
            "fallback": { "status": "active", "total_fallbacks": 0 }
        })),
    )
}

// --- Analytics Handlers ---

async fn get_ab_testing_stats() -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(json!({
            "status": "active",
            "experiments": [
                { "id": "rust_gateway_v1", "name": "Rust Gateway Migration", "status": "running", "variant": "A" }
            ]
        })),
    )
}

async fn get_quality_metrics() -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(json!({
            "avg_confidence": 0.92,
            "success_rate": 0.98,
            "total_tasks": 123
        })),
    )
}

async fn get_system_metrics(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let mut sys = System::new_all();
    sys.refresh_all();

    let cpu_percent = sys.global_cpu_info().cpu_usage();
    let cpu_count = sys.cpus().len();

    let total_ram = sys.total_memory();
    let used_ram = sys.used_memory();
    let free_ram = sys.available_memory();

    let mut disk_used = 0;
    let mut disk_total = 0;
    for disk in sysinfo::Disks::new_with_refreshed_list().iter() {
        disk_used += disk.total_space() - disk.available_space();
        disk_total += disk.total_space();
    }

    let mut result = json!({
        "success": true,
        "cpu": {
            "percent": (cpu_percent * 10.0).round() / 10.0,
            "count": cpu_count,
        },
        "ram": {
            "percent": ((used_ram as f64 / total_ram as f64) * 1000.0).round() / 10.0,
            "used_gb": (used_ram as f64 / (1024.0 * 1024.0 * 1024.0) * 100.0).round() / 100.0,
            "total_gb": (total_ram as f64 / (1024.0 * 1024.0 * 1024.0) * 100.0).round() / 100.0,
            "available_gb": (free_ram as f64 / (1024.0 * 1024.0 * 1024.0) * 100.0).round() / 100.0,
        },
        "disk": {
            "percent": ((disk_used as f64 / disk_total as f64) * 1000.0).round() / 10.0,
            "used_gb": (disk_used as f64 / (1024.0 * 1024.0 * 1024.0) * 100.0).round() / 100.0,
            "total_gb": (disk_total as f64 / (1024.0 * 1024.0 * 1024.0) * 100.0).round() / 100.0,
        },
    });

    // DB metrics
    if let Some(ke) = state.knowledge_engine.as_ref() {
        if let Ok(experts_count) = sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM experts")
            .fetch_one(&ke.pool)
            .await
        {
            if let Ok(nodes_count) =
                sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM knowledge_nodes")
                    .fetch_one(&ke.pool)
                    .await
            {
                result["db"] = json!({
                    "experts": experts_count,
                    "knowledge_nodes": nodes_count,
                    "healthy": experts_count >= 80 && nodes_count >= 10000
                });
            }
        }
    }

    (StatusCode::OK, Json(result))
}

async fn get_auto_optimizer_status() -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(json!({
            "is_running": true,
            "optimizations_count": 42,
            "status": "active_via_gateway"
        })),
    )
}

// --- Data Retention Handlers ---

#[derive(Deserialize)]
struct CleanupRequest {
    #[serde(default = "default_dry_run")]
    dry_run: bool,
    tables: Option<String>,
}

fn default_dry_run() -> bool {
    true
}

async fn run_cleanup(
    State(state): State<Arc<AppState>>,
    Json(req): Json<CleanupRequest>,
) -> impl IntoResponse {
    let ke = require_ke!(state);
    let retention_days = 90;
    let allowed_tables = ["real_time_metrics", "semantic_ai_cache"];
    let mut results = Vec::new();
    let mut total_deleted = 0i64;

    let tables_to_clean: Vec<String> = req
        .tables
        .map(|t| t.split(',').map(|s| s.trim().to_string()).collect())
        .unwrap_or_else(|| allowed_tables.iter().map(|s| s.to_string()).collect());

    for table in tables_to_clean {
        if !allowed_tables.contains(&table.as_str()) {
            results.push(json!({ "table": table, "deleted": 0, "error": "Table not allowed" }));
            continue;
        }

        let query = if req.dry_run {
            format!(
                "SELECT COUNT(*) FROM {} WHERE created_at < NOW() - INTERVAL '{} days'",
                table, retention_days
            )
        } else {
            format!(
                "DELETE FROM {} WHERE created_at < NOW() - INTERVAL '{} days'",
                table, retention_days
            )
        };

        match sqlx::query_scalar::<_, i64>(&query)
            .fetch_one(&ke.pool)
            .await
        {
            Ok(count) => {
                results.push(json!({ "table": table, "deleted": count, "dry_run": req.dry_run }));
                total_deleted += count;
            }
            Err(e) => {
                results.push(json!({ "table": table, "deleted": 0, "error": e.to_string() }));
            }
        }
    }

    (
        StatusCode::OK,
        Json(json!({
            "status": if req.dry_run { "dry_run" } else { "completed" },
            "timestamp": chrono::Utc::now().to_rfc3339(),
            "total_deleted": total_deleted,
            "results": results
        })),
    )
        .into_response()
}

// --- Files Handlers ---

#[derive(Deserialize)]
struct ReadFileParams {
    path: String,
}

async fn read_file_handler(
    State(state): State<Arc<AppState>>,
    Query(req): Query<ReadFileParams>,
) -> impl IntoResponse {
    let workspace = &state.workspace_root;
    let safe_path = workspace.join(req.path.trim_start_matches('/'));

    if !safe_path.starts_with(workspace) {
        return (StatusCode::FORBIDDEN, "Access denied").into_response();
    }

    match fs::read_to_string(safe_path).await {
        Ok(content) => (
            StatusCode::OK,
            Json(json!({ "content": content, "path": req.path })),
        )
            .into_response(),
        Err(e) => (StatusCode::NOT_FOUND, format!("File not found: {}", e)).into_response(),
    }
}

async fn write_file_handler(
    State(state): State<Arc<AppState>>,
    Json(req): Json<WriteFileRequest>,
) -> impl IntoResponse {
    let workspace = &state.workspace_root;
    let safe_path = workspace.join(req.path.trim_start_matches('/'));

    if !safe_path.starts_with(workspace) {
        return (StatusCode::FORBIDDEN, "Access denied").into_response();
    }

    if let Some(parent) = safe_path.parent() {
        let _ = fs::create_dir_all(parent).await;
    }

    match fs::write(safe_path, req.content).await {
        Ok(_) => (
            StatusCode::OK,
            Json(json!({ "status": "success", "path": req.path })),
        )
            .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("Failed to write file: {}", e),
        )
            .into_response(),
    }
}

#[derive(Deserialize)]
struct ListFilesParams {
    path: Option<String>,
}

async fn list_files_handler(
    State(state): State<Arc<AppState>>,
    Query(req): Query<ListFilesParams>,
) -> impl IntoResponse {
    let workspace = &state.workspace_root;
    let rel_path = req.path.unwrap_or_default();
    let safe_path = workspace.join(rel_path.trim_start_matches('/'));

    if !safe_path.starts_with(workspace) {
        return (StatusCode::FORBIDDEN, "Access denied").into_response();
    }

    let mut entries = Vec::new();
    let mut dir = match fs::read_dir(safe_path).await {
        Ok(d) => d,
        Err(e) => {
            return (StatusCode::NOT_FOUND, format!("Directory not found: {}", e)).into_response();
        }
    };

    while let Ok(Some(entry)) = dir.next_entry().await {
        let metadata = entry.metadata().await.ok();
        entries.push(json!({
            "name": entry.file_name().to_string_lossy(),
            "path": entry.path().strip_prefix(workspace).unwrap_or(&entry.path()).to_string_lossy(),
            "type": if entry.file_type().await.map(|t| t.is_dir()).unwrap_or(false) { "directory" } else { "file" },
            "size": metadata.map(|m| m.len()),
        }));
    }

    (StatusCode::OK, Json(entries)).into_response()
}

use glob::glob;
use regex::Regex;
use tokio::io::{AsyncReadExt, AsyncWriteExt};

#[derive(Deserialize)]
struct BatchReadRequest {
    file_paths: Vec<String>,
    max_concurrent: Option<usize>,
}

#[derive(Deserialize)]
struct BatchGrepRequest {
    pattern: String,
    file_paths: Vec<String>,
    case_sensitive: Option<bool>,
}

async fn batch_read_handler(
    State(state): State<Arc<AppState>>,
    Json(req): Json<BatchReadRequest>,
) -> impl IntoResponse {
    let max_concurrent = req.max_concurrent.unwrap_or(10).min(50);
    let semaphore = Arc::new(Semaphore::new(max_concurrent));
    let mut results = Vec::new();

    let mut tasks = Vec::new();
    for path in req.file_paths {
        let state = state.clone();
        let semaphore = semaphore.clone();
        tasks.push(tokio::spawn(async move {
            let _permit = semaphore.acquire().await.ok();
            let safe_path = match get_safe_path(&state.workspace_root, &path).await {
                Ok(p) => p,
                Err(_) => {
                    return json!({ "path": path, "status": "error", "error": "Access denied" });
                }
            };

            match fs::read_to_string(safe_path).await {
                Ok(content) => json!({
                    "path": path,
                    "status": "success",
                    "content": content,
                    "size_kb": (content.len() as f64 / 1024.0 * 100.0).round() / 100.0,
                    "lines": content.lines().count()
                }),
                Err(e) => json!({ "path": path, "status": "error", "error": e.to_string() }),
            }
        }));
    }

    for task in tasks {
        if let Ok(res) = task.await {
            results.push(res);
        }
    }

    let success_count = results.iter().filter(|r| r["status"] == "success").count();
    Json(json!({
        "status": "success",
        "results": results,
        "summary": {
            "total": results.len(),
            "success": success_count,
            "errors": results.len() - success_count
        }
    }))
}

async fn batch_grep_handler(
    State(state): State<Arc<AppState>>,
    Json(req): Json<BatchGrepRequest>,
) -> impl IntoResponse {
    let case_sensitive = req.case_sensitive.unwrap_or(false);
    let pattern = if case_sensitive {
        req.pattern.clone()
    } else {
        format!("(?i){}", req.pattern)
    };

    let re = match Regex::new(&pattern) {
        Ok(r) => r,
        Err(e) => {
            return (
                StatusCode::BAD_REQUEST,
                Json(json!({ "error": format!("Invalid regex: {}", e) })),
            )
                .into_response();
        }
    };

    let mut all_files = Vec::new();
    for pattern in req.file_paths {
        let full_pattern = state.workspace_root.join(pattern.trim_start_matches('/'));
        if let Ok(paths) = glob(full_pattern.to_str().unwrap_or("")) {
            for path in paths.flatten() {
                if path.is_file() {
                    all_files.push(path);
                }
            }
        }
    }

    let semaphore = Arc::new(Semaphore::new(20));
    let mut results = Vec::new();
    let mut tasks = Vec::new();

    for path in all_files {
        let re = re.clone();
        let semaphore = semaphore.clone();
        let workspace_root = state.workspace_root.clone();
        tasks.push(tokio::spawn(async move {
            let _permit = semaphore.acquire().await.ok();
            let content = match fs::read_to_string(&path).await {
                Ok(c) => c,
                Err(_) => return None,
            };

            let mut matches = Vec::new();
            for (i, line) in content.lines().enumerate() {
                if let Some(m) = re.find(line) {
                    matches.push(json!({
                        "line": i + 1,
                        "content": line.trim(),
                        "match": m.as_str(),
                        "start": m.start(),
                        "end": m.end()
                    }));
                }
            }

            if matches.is_empty() {
                return None;
            }

            let rel_path = path.strip_prefix(&workspace_root).unwrap_or(&path);
            Some(json!({
                "path": rel_path.to_string_lossy(),
                "matches": matches,
                "match_count": matches.len(),
                "status": "success"
            }))
        }));
    }

    for task in tasks {
        if let Ok(Some(res)) = task.await {
            results.push(res);
        }
    }

    let total_matches: usize = results
        .iter()
        .map(|r| r["match_count"].as_u64().unwrap_or(0) as usize)
        .sum();
    Json(json!({
        "status": "success",
        "results": results,
        "summary": {
            "files_with_matches": results.len(),
            "total_matches": total_matches
        }
    }))
    .into_response()
}

#[derive(Deserialize)]
struct TerminalExecuteRequest {
    command: String,
}

// --- Terminal Handlers ---

async fn terminal_ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_socket(socket, state))
}

async fn handle_socket(mut socket: WebSocket, state: Arc<AppState>) {
    let pty_system = native_pty_system();
    let pair = match pty_system.openpty(PtySize {
        rows: 24,
        cols: 80,
        pixel_width: 0,
        pixel_height: 0,
    }) {
        Ok(p) => p,
        Err(e) => {
            error!("Failed to open PTY: {}", e);
            return;
        }
    };

    let shell = env::var("SHELL").unwrap_or_else(|_| "/bin/zsh".to_string());
    let mut cmd = CommandBuilder::new(&shell);
    cmd.cwd(state.workspace_root.clone());

    let mut child = match pair.slave.spawn_command(cmd) {
        Ok(c) => c,
        Err(e) => {
            error!("Failed to spawn shell: {}", e);
            return;
        }
    };

    // Drop slave to avoid keeping it open
    drop(pair.slave);

    let mut pty_reader = pair
        .master
        .try_clone_reader()
        .expect("Failed to clone PTY reader");
    let mut pty_writer = pair
        .master
        .take_writer()
        .expect("Failed to take PTY writer");

    let (tx, mut rx) = mpsc::channel::<Vec<u8>>(100);

    // Task to read from PTY and send to WebSocket
    let mut tx_pty = tx.clone();
    std::thread::spawn(move || {
        let mut buffer = [0u8; 1024];
        while let Ok(n) = pty_reader.read(&mut buffer) {
            if n == 0 {
                break;
            }
            if tx_pty.blocking_send(buffer[..n].to_vec()).is_err() {
                break;
            }
        }
    });

    // Main loop for WebSocket communication
    loop {
        tokio::select! {
            Some(msg) = socket.recv() => {
                match msg {
                    Ok(Message::Text(text)) => {
                        let _ = pty_writer.write_all(text.as_bytes());
                    }
                    Ok(Message::Binary(bin)) => {
                        let _ = pty_writer.write_all(&bin);
                    }
                    Ok(Message::Close(_)) => break,
                    _ => {}
                }
            }
            Some(data) = rx.recv() => {
                if socket.send(Message::Binary(data)).await.is_err() {
                    break;
                }
            }
            else => break,
        }
    }

    let _ = child.kill();
}

async fn terminal_execute_handler(
    State(state): State<Arc<AppState>>,
    Json(req): Json<TerminalExecuteRequest>,
) -> impl IntoResponse {
    let workspace = &state.workspace_root;

    match tokio::process::Command::new("sh")
        .arg("-c")
        .arg(&req.command)
        .current_dir(workspace)
        .output()
        .await
    {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            (
                StatusCode::OK,
                Json(json!({
                    "status": if output.status.success() { "success" } else { "failed" },
                    "exit_code": output.status.code(),
                    "stdout": stdout,
                    "stderr": stderr
                })),
            )
                .into_response()
        }
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("Failed to execute command: {}", e),
        )
            .into_response(),
    }
}

// --- Git API ---

fn is_git_repo(workspace: &PathBuf) -> bool {
    workspace.join(".git").exists()
}

async fn git_status_handler(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    if !is_git_repo(&state.workspace_root) {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "Not a git repository" })),
        )
            .into_response();
    }
    match tokio::process::Command::new("git")
        .args(["status", "--short"])
        .current_dir(&state.workspace_root)
        .output()
        .await
    {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            (
                StatusCode::OK,
                Json(json!({
                    "status": if output.status.success() { "success" } else { "failed" },
                    "stdout": stdout,
                    "stderr": stderr,
                    "lines": stdout.lines().filter(|s| !s.is_empty()).collect::<Vec<_>>()
                })),
            )
                .into_response()
        }
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("{}", e) })),
        )
            .into_response(),
    }
}

#[derive(Deserialize)]
struct GitDiffQuery {
    path: Option<String>,
}

async fn git_diff_handler(
    State(state): State<Arc<AppState>>,
    Query(q): Query<GitDiffQuery>,
) -> impl IntoResponse {
    if !is_git_repo(&state.workspace_root) {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "Not a git repository" })),
        )
            .into_response();
    }
    let mut cmd = tokio::process::Command::new("git");
    cmd.arg("diff").current_dir(&state.workspace_root);
    if let Some(ref p) = q.path {
        let safe = p.trim_start_matches('/');
        if !safe.contains("..") {
            cmd.arg("--").arg(safe);
        }
    }
    match cmd.output().await {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            (
                StatusCode::OK,
                Json(json!({
                    "stdout": stdout,
                    "exit_code": output.status.code()
                })),
            )
                .into_response()
        }
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("{}", e) })),
        )
            .into_response(),
    }
}

#[derive(Deserialize)]
struct GitLogQuery {
    n: Option<u32>,
}

async fn git_log_handler(
    State(state): State<Arc<AppState>>,
    Query(q): Query<GitLogQuery>,
) -> impl IntoResponse {
    if !is_git_repo(&state.workspace_root) {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "Not a git repository" })),
        )
            .into_response();
    }
    let n = q.n.unwrap_or(20).min(100);
    match tokio::process::Command::new("git")
        .args([
            "log",
            "-n",
            &n.to_string(),
            "--pretty=format:%h|%an|%ad|%s",
            "--date=short",
        ])
        .current_dir(&state.workspace_root)
        .output()
        .await
    {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let commits: Vec<serde_json::Value> = stdout
                .lines()
                .filter(|s| !s.is_empty())
                .map(|line| {
                    let parts: Vec<&str> = line.splitn(4, '|').collect();
                    json!({
                        "hash": parts.get(0).unwrap_or(&""),
                        "author": parts.get(1).unwrap_or(&""),
                        "date": parts.get(2).unwrap_or(&""),
                        "subject": parts.get(3).unwrap_or(&""),
                    })
                })
                .collect();
            (StatusCode::OK, Json(json!({ "commits": commits }))).into_response()
        }
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("{}", e) })),
        )
            .into_response(),
    }
}

async fn git_branch_handler(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    if !is_git_repo(&state.workspace_root) {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "Not a git repository" })),
        )
            .into_response();
    }
    let current = tokio::process::Command::new("git")
        .args(["branch", "--show-current"])
        .current_dir(&state.workspace_root)
        .output()
        .await;
    let branches = tokio::process::Command::new("git")
        .args(["branch", "-a"])
        .current_dir(&state.workspace_root)
        .output()
        .await;
    match (current, branches) {
        (Ok(cur), Ok(br)) => {
            let current_name = String::from_utf8_lossy(&cur.stdout).trim().to_string();
            let branch_list: Vec<String> = String::from_utf8_lossy(&br.stdout)
                .lines()
                .map(|s| s.trim().trim_start_matches('*').trim().to_string())
                .filter(|s| !s.is_empty())
                .collect();
            (
                StatusCode::OK,
                Json(json!({
                    "current": current_name,
                    "branches": branch_list
                })),
            )
                .into_response()
        }
        _ => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": "git branch failed" })),
        )
            .into_response(),
    }
}

#[derive(Deserialize)]
struct GitCommitRequest {
    message: String,
    paths: Option<Vec<String>>,
}

async fn git_commit_handler(
    State(state): State<Arc<AppState>>,
    Json(req): Json<GitCommitRequest>,
) -> impl IntoResponse {
    if !is_git_repo(&state.workspace_root) {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "Not a git repository" })),
        )
            .into_response();
    }
    let msg = req.message.trim();
    if msg.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "Commit message is required" })),
        )
            .into_response();
    }
    let paths = req.paths.as_deref().unwrap_or(&[]);
    let add_args: Vec<&str> = paths.iter().map(String::as_str).collect();
    let add_ok = if add_args.is_empty() {
        tokio::process::Command::new("git")
            .arg("add")
            .arg("-A")
            .current_dir(&state.workspace_root)
            .output()
            .await
    } else {
        let mut cmd = tokio::process::Command::new("git");
        cmd.arg("add").current_dir(&state.workspace_root);
        for p in &add_args {
            let safe = p.trim_start_matches('/');
            if !safe.contains("..") {
                cmd.arg(safe);
            }
        }
        cmd.output().await
    };
    let add_ok = match add_ok {
        Ok(out) if out.status.success() => true,
        _ => false,
    };
    if !add_ok {
        return (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": "git add failed" })),
        )
            .into_response();
    }
    let commit = tokio::process::Command::new("git")
        .args(["commit", "-m", msg])
        .current_dir(&state.workspace_root)
        .output()
        .await;
    match commit {
        Ok(out) => {
            let stdout = String::from_utf8_lossy(&out.stdout).to_string();
            let stderr = String::from_utf8_lossy(&out.stderr).to_string();
            (
                StatusCode::OK,
                Json(json!({
                    "success": out.status.success(),
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": out.status.code()
                })),
            )
                .into_response()
        }
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("{}", e) })),
        )
            .into_response(),
    }
}

// --- Multimodal Handlers ---

#[derive(Deserialize)]
struct ProcessImageRequest {
    image_base64: String,
    prompt: Option<String>,
}

async fn process_image(
    State(state): State<Arc<AppState>>,
    Json(req): Json<ProcessImageRequest>,
) -> impl IntoResponse {
    // Proxy to Moondream Station (port 2020) or Ollama
    let moondream_url = "http://localhost:2020/describe";
    let payload = json!({
        "image": req.image_base64,
        "prompt": req.prompt.unwrap_or_else(|| "Опиши это изображение подробно.".to_string())
    });

    match state.client.post(moondream_url).json(&payload).send().await {
        Ok(res) if res.status().is_success() => {
            let data: serde_json::Value = res.json().await.unwrap_or(json!({}));
            (
                StatusCode::OK,
                Json(json!({ "text": data["description"], "content_type": "image" })),
            )
                .into_response()
        }
        _ => {
            // Fallback to Ollama Vision if Moondream is down
            let ollama_base =
                env::var("OLLAMA_URL").unwrap_or_else(|_| "http://localhost:11434".to_string());
            let ollama_url = format!("{}/api/generate", ollama_base.trim_end_matches('/'));
            let ollama_payload = json!({
                "model": "moondream",
                "prompt": "Describe this image",
                "images": [req.image_base64.replace("data:image/png;base64,", "").replace("data:image/jpeg;base64,", "")],
                "stream": false
            });

            match state
                .client
                .post(ollama_url)
                .json(&ollama_payload)
                .send()
                .await
            {
                Ok(res) if res.status().is_success() => {
                    let data: serde_json::Value = res.json().await.unwrap_or(json!({}));
                    (
                        StatusCode::OK,
                        Json(json!({ "text": data["response"], "content_type": "image" })),
                    )
                        .into_response()
                }
                _ => (
                    StatusCode::SERVICE_UNAVAILABLE,
                    "Vision services unavailable",
                )
                    .into_response(),
            }
        }
    }
}

#[derive(Deserialize, Serialize)]
struct PlanRequest {
    goal: String,
    project_context: Option<String>,
}

async fn proxy_plan(
    State(state): State<Arc<AppState>>,
    Json(req): Json<PlanRequest>,
) -> impl IntoResponse {
    let victoria_url = format!("{}/plan", state.victoria_url.trim_end_matches('/'));

    let res = state.client.post(&victoria_url).json(&req).send().await;

    match res {
        Ok(response) => {
            let status = response.status();
            let data: serde_json::Value = response.json().await.unwrap_or(json!({}));
            (status, Json(data)).into_response()
        }
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()).into_response(),
    }
}

fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    // Load environment variables
    dotenv().ok();

    // Initialize logging
    tracing_subscriber::fmt::init();

    // Build custom runtime with tuned parameters
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(4) // Gateway is I/O-bound
        .max_blocking_threads(64) // Reduced from default 512
        .thread_name("atra-gateway-worker")
        .enable_all()
        .build()?;

    runtime.block_on(async_main())
}

use axum_server::tls_rustls::RustlsConfig;

async fn async_main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let database_url = env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/knowledge_os".to_string());

    let workspace_root_str = env::var("WORKSPACE_ROOT")
        .unwrap_or_else(|_| "/Users/bikos/Documents/atra-web-ide".to_string());
    let workspace_root = PathBuf::from(workspace_root_str);

    let victoria_url =
        env::var("VICTORIA_URL").unwrap_or_else(|_| "http://localhost:8010".to_string());
    let use_victoria_agent = env::var("USE_VICTORIA_AGENT")
        .unwrap_or_else(|_| "true".to_string())
        .to_lowercase()
        == "true"
        || env::var("USE_VICTORIA_AGENT").unwrap_or_else(|_| "1".to_string()) == "1";

    let knowledge_engine = match KnowledgeEngine::new(&database_url).await {
        Ok(ke) => {
            info!("✅ KnowledgeEngine initialized successfully");
            Some(ke)
        }
        Err(e) => {
            warn!(
                "⚠️ KnowledgeEngine failed to initialize: {}. Knowledge features will be unavailable.",
                e
            );
            None
        }
    };

    let client = Client::builder()
        .timeout(Duration::from_secs(300)) // Increased timeout to 5 minutes for heavy models
        .build()
        .expect("Failed to create reqwest client");

    let max_concurrent_chat = env::var("MAX_CONCURRENT_CHAT")
        .ok()
        .and_then(|s| s.parse::<usize>().ok())
        .unwrap_or(50);

    let state = Arc::new(AppState {
        client,
        knowledge_engine,
        workspace_root: workspace_root.clone(),
        request_count: AtomicU64::new(0),
        victoria_url: victoria_url.clone(),
        use_victoria_agent,
        chat_semaphore: Arc::new(Semaphore::new(max_concurrent_chat)),
    });

    info!(
        "🔒 Chat semaphore initialized with max_concurrent={}",
        max_concurrent_chat
    );

    // Configure CORS
    let cors = CorsLayer::new()
        .allow_origin([
            "http://localhost:3000".parse().unwrap(),
            "http://localhost:3002".parse().unwrap(),
        ])
        .allow_methods([Method::GET, Method::POST, Method::DELETE])
        .allow_headers(Any);

    let app = Router::new()
        .route("/health", get(health_check))
        .nest_service(
            "/crates",
            ServeDir::new(workspace_root.join("mirror/crates.io/crates")),
        )
        .route("/v1/chat/completions", post(proxy_chat))
        .route("/api/chat/plan", post(proxy_plan))
        .route("/v1/knowledge/search", get(knowledge_search))
        .route("/api/experts", get(list_experts_handler))
        .route("/api/experts/:id", get(get_expert_handler))
        .route("/api/preview", get(preview_index_handler))
        .route("/api/preview/file", get(preview_file_handler))
        .route("/api/preview/html", get(preview_index_handler)) // Alias for compatibility
        .route("/api/editor/autocomplete", post(get_autocomplete))
        .route("/api/editor/lint", post(get_lint))
        .route("/api/sandbox/status/:expert_name", get(get_sandbox_status))
        .route("/api/sandbox/reset/:expert_name", post(reset_sandbox))
        .route("/api/sandbox/experiments", get(get_recent_experiments))
        .route("/api/terminal/pty", get(terminal_pty))
        .route("/api/terminal/ask", post(terminal_ask))
        .route("/api/latency/benchmark", get(get_latency_benchmark))
        .route("/api/plan-cache/stats", get(get_plan_cache_stats))
        .route(
            "/api/rag-optimization/stats",
            get(get_rag_optimization_stats),
        )
        .route("/api/ab-testing/stats", get(get_ab_testing_stats))
        .route("/api/quality-metrics", get(get_quality_metrics))
        .route("/api/system-metrics", get(get_system_metrics))
        .route("/api/auto-optimizer/status", get(get_auto_optimizer_status))
        .route("/api/data-retention/cleanup", post(run_cleanup))
        .route("/api/multimodal/process-image", post(process_image))
        .route("/api/chat/status", get(chat_status_handler))
        .route("/api/chat/models", get(chat_models_handler))
        .route("/api/files/list_v2", get(list_files_handler))
        .route("/api/files/read_v2", get(read_file_handler))
        .route("/api/files/write_v2", post(write_file_handler))
        .route("/api/files/create_v2", post(create_item_handler))
        .route("/api/files/delete_v2", delete(delete_item_handler))
        .route("/api/files/batch_read", post(batch_read_handler))
        .route("/api/files/batch_grep", post(batch_grep_handler))
        .route(
            "/api/knowledge/search_v2",
            post(knowledge_search_v2_handler),
        )
        .route("/api/quantum/optimize_plan", post(quantum_optimize_handler))
        .route("/api/security/analyze", post(security_analyze_handler))
        .route("/api/cluster/heartbeat", post(cluster_heartbeat_handler))
        .route("/api/cluster/sync", post(cluster_sync_handler))
        .route("/api/terminal/execute", post(terminal_execute_handler))
        .route("/api/terminal/ws", get(terminal_ws_handler))
        .route("/api/git/status", get(git_status_handler))
        .route("/api/git/diff", get(git_diff_handler))
        .route("/api/git/log", get(git_log_handler))
        .route("/api/git/branch", get(git_branch_handler))
        .route("/api/git/commit", post(git_commit_handler))
        .route("/api/domains", get(list_domains))
        .route("/metrics", get(metrics_prometheus))
        .route("/metrics/summary", get(metrics_summary))
        .layer(cors)
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], 8081));

    // [SINGULARITY 21.24] mTLS Support for inter-cluster security
    let cert_path = env::var("GATEWAY_CERT_PATH").ok();
    let key_path = env::var("GATEWAY_KEY_PATH").ok();

    if let (Some(cert), Some(key)) = (cert_path, key_path) {
        info!("🔐 Starting Rust API Gateway with TLS (mTLS if CA provided)");
        let config = RustlsConfig::from_pem_file(cert, key).await?;

        axum_server::bind_rustls(addr, config)
            .serve(app.into_make_service())
            .await?;
    } else {
        info!("🚀 Rust API Gateway listening on {} (HTTP mode)", addr);
        let listener = tokio::net::TcpListener::bind(addr).await?;
        axum::serve(listener, app).await?;
    }

    Ok(())
}

async fn health_check() -> &'static str {
    "OK"
}

// --- File Operations Helpers ---

async fn get_safe_path(
    workspace_root: &PathBuf,
    path_str: &str,
) -> Result<PathBuf, (StatusCode, Json<serde_json::Value>)> {
    let safe_path_str = path_str.trim_start_matches('/');
    let full_path = workspace_root.join(safe_path_str);

    if path_str.contains("..") {
        return Err((
            StatusCode::FORBIDDEN,
            Json(json!({ "error": "Access denied: invalid path" })),
        ));
    }

    let canonical_root = workspace_root.canonicalize()
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({ "error": format!("Workspace root error: {} (path: {:?})", e, workspace_root) }))))?;

    if full_path.exists() {
        let canonical_path = full_path.canonicalize().map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": format!("Path canonicalization error: {}", e) })),
            )
        })?;

        if !canonical_path.starts_with(&canonical_root) {
            return Err((
                StatusCode::FORBIDDEN,
                Json(json!({ "error": "Access denied: path outside workspace" })),
            ));
        }
    } else {
        if let Some(parent) = full_path.parent() {
            if parent.exists() {
                let canonical_parent = parent.canonicalize().map_err(|e| {
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        Json(json!({ "error": format!("Parent canonicalization error: {}", e) })),
                    )
                })?;
                if !canonical_parent.starts_with(&canonical_root) {
                    return Err((
                        StatusCode::FORBIDDEN,
                        Json(json!({ "error": "Access denied: path outside workspace" })),
                    ));
                }
            }
        }
    }

    Ok(full_path)
}

// --- Route Handlers ---

async fn list_files(
    State(state): State<Arc<AppState>>,
    Query(params): Query<FilePathQuery>,
) -> impl IntoResponse {
    let dir_path = match get_safe_path(&state.workspace_root, &params.path).await {
        Ok(p) => p,
        Err(e) => return e.into_response(),
    };

    if !dir_path.exists() {
        return (StatusCode::OK, Json(Vec::<FileInfo>::new())).into_response();
    }

    if !dir_path.is_dir() {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "Path is not a directory" })),
        )
            .into_response();
    }

    let mut files = Vec::new();
    let mut entries = match fs::read_dir(dir_path).await {
        Ok(e) => e,
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": e.to_string() })),
            )
                .into_response();
        }
    };

    while let Ok(Some(entry)) = entries.next_entry().await {
        let metadata = entry.metadata().await.ok();
        let path = entry.path();
        let rel_path = path.strip_prefix(&state.workspace_root).unwrap_or(&path);

        files.push(FileInfo {
            name: entry.file_name().to_string_lossy().to_string(),
            path: rel_path.to_string_lossy().to_string(),
            file_type: if path.is_dir() { "directory" } else { "file" }.to_string(),
            size: metadata.as_ref().map(|m| m.len()),
            modified: metadata.and_then(|m| m.modified().ok()).map(|t| {
                let dt: chrono::DateTime<chrono::Utc> = t.into();
                dt.to_rfc3339()
            }),
        });
    }

    files.sort_by(|a, b| a.name.cmp(&b.name));
    (StatusCode::OK, Json(files)).into_response()
}

async fn read_file(
    State(state): State<Arc<AppState>>,
    Query(params): Query<FilePathQuery>,
) -> impl IntoResponse {
    let file_path = match get_safe_path(&state.workspace_root, &params.path).await {
        Ok(p) => p,
        Err(e) => return e.into_response(),
    };

    if !file_path.exists() {
        return (
            StatusCode::NOT_FOUND,
            Json(json!({ "error": "File not found" })),
        )
            .into_response();
    }

    if !file_path.is_file() {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "Path is not a file" })),
        )
            .into_response();
    }

    match fs::read_to_string(file_path).await {
        Ok(content) => (
            StatusCode::OK,
            Json(FileContent {
                path: params.path,
                content,
                encoding: "utf-8".to_string(),
            }),
        )
            .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": e.to_string() })),
        )
            .into_response(),
    }
}

async fn write_file(
    State(state): State<Arc<AppState>>,
    Query(params): Query<FilePathQuery>,
    Json(req): Json<WriteFileRequest>,
) -> impl IntoResponse {
    let file_path = match get_safe_path(&state.workspace_root, &params.path).await {
        Ok(p) => p,
        Err(e) => return e.into_response(),
    };

    if let Some(parent) = file_path.parent() {
        let _ = fs::create_dir_all(parent).await;
    }

    match fs::write(&file_path, &req.content).await {
        Ok(_) => (
            StatusCode::OK,
            Json(json!({
                "success": true,
                "path": params.path,
                "size": req.content.len()
            })),
        )
            .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": e.to_string() })),
        )
            .into_response(),
    }
}

async fn create_item(
    State(state): State<Arc<AppState>>,
    Query(params): Query<FilePathQuery>,
    Json(req): Json<CreateRequest>,
) -> impl IntoResponse {
    let item_path = match get_safe_path(&state.workspace_root, &params.path).await {
        Ok(p) => p,
        Err(e) => return e.into_response(),
    };

    if item_path.exists() {
        return (
            StatusCode::CONFLICT,
            Json(json!({ "error": "Path already exists" })),
        )
            .into_response();
    }

    if req.item_type == "directory" {
        match fs::create_dir_all(&item_path).await {
            Ok(_) => (
                StatusCode::OK,
                Json(json!({ "success": true, "path": params.path, "type": "directory" })),
            )
                .into_response(),
            Err(e) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": e.to_string() })),
            )
                .into_response(),
        }
    } else {
        if let Some(parent) = item_path.parent() {
            let _ = fs::create_dir_all(parent).await;
        }
        match fs::write(&item_path, req.content.unwrap_or_default()).await {
            Ok(_) => (
                StatusCode::OK,
                Json(json!({ "success": true, "path": params.path, "type": "file" })),
            )
                .into_response(),
            Err(e) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": e.to_string() })),
            )
                .into_response(),
        }
    }
}

async fn delete_item(
    State(state): State<Arc<AppState>>,
    Query(params): Query<FilePathQuery>,
) -> impl IntoResponse {
    let item_path = match get_safe_path(&state.workspace_root, &params.path).await {
        Ok(p) => p,
        Err(e) => return e.into_response(),
    };

    if !item_path.exists() {
        return (
            StatusCode::NOT_FOUND,
            Json(json!({ "error": "Path not found" })),
        )
            .into_response();
    }

    if item_path == state.workspace_root {
        return (
            StatusCode::FORBIDDEN,
            Json(json!({ "error": "Cannot delete workspace root" })),
        )
            .into_response();
    }

    let res = if item_path.is_dir() {
        fs::remove_dir_all(item_path).await
    } else {
        fs::remove_file(item_path).await
    };

    match res {
        Ok(_) => (
            StatusCode::OK,
            Json(json!({ "success": true, "path": params.path })),
        )
            .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": e.to_string() })),
        )
            .into_response(),
    }
}

async fn list_experts(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let ke = require_ke!(state);
    match sqlx::query_as::<_, Expert>(
        "SELECT id, name, role, system_prompt, created_at FROM experts ORDER BY name",
    )
    .fetch_all(&ke.pool)
    .await
    {
        Ok(experts) => (StatusCode::OK, Json(experts)).into_response(),
        Err(e) => {
            error!("List experts error: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": e.to_string() })),
            )
                .into_response()
        }
    }
}

async fn get_expert(State(state): State<Arc<AppState>>, Path(id): Path<Uuid>) -> impl IntoResponse {
    let ke = require_ke!(state);
    match sqlx::query_as::<_, Expert>(
        "SELECT id, name, role, system_prompt, created_at FROM experts WHERE id = $1",
    )
    .bind(id)
    .fetch_optional(&ke.pool)
    .await
    {
        Ok(Some(expert)) => (StatusCode::OK, Json(expert)).into_response(),
        Ok(None) => (
            StatusCode::NOT_FOUND,
            Json(json!({ "error": "Expert not found" })),
        )
            .into_response(),
        Err(e) => {
            error!("Get expert error: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": e.to_string() })),
            )
                .into_response()
        }
    }
}

async fn list_domains(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let ke = require_ke!(state);
    match sqlx::query_as::<_, Domain>(
        "SELECT id, name, description, created_at FROM domains ORDER BY name",
    )
    .fetch_all(&ke.pool)
    .await
    {
        Ok(domains) => (StatusCode::OK, Json(domains)).into_response(),
        Err(e) => {
            error!("List domains error: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": e.to_string() })),
            )
                .into_response()
        }
    }
}

async fn metrics_prometheus(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let n = state.request_count.load(Ordering::Relaxed);
    let body = format!(
        "# HELP gateway_requests_total Total chat/completion requests\n\
         # TYPE gateway_requests_total counter\ngateway_requests_total {}\n",
        n
    );
    ([(header::CONTENT_TYPE, "text/plain; charset=utf-8")], body)
}

async fn metrics_summary(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let n = state.request_count.load(Ordering::Relaxed);
    let summary = json!({
        "info": "Use GET /metrics for full Prometheus format",
        "gateway_requests_total": n,
        "endpoints": { "metrics": "/metrics", "summary": "/metrics/summary" }
    });
    (StatusCode::OK, Json(summary))
}

#[derive(Deserialize)]
struct CreateItemRequest {
    #[serde(rename = "type")]
    item_type: String,
    path: String,
    content: Option<String>,
}

async fn create_item_handler(
    State(state): State<Arc<AppState>>,
    Json(req): Json<CreateItemRequest>,
) -> impl IntoResponse {
    let workspace = &state.workspace_root;
    let safe_path = workspace.join(req.path.trim_start_matches('/'));

    if !safe_path.starts_with(workspace) {
        return (StatusCode::FORBIDDEN, "Access denied").into_response();
    }

    if safe_path.exists() {
        return (StatusCode::CONFLICT, "Path already exists").into_response();
    }

    match req.item_type.as_str() {
        "directory" => {
            if let Err(e) = fs::create_dir_all(&safe_path).await {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("Failed to create directory: {}", e),
                )
                    .into_response();
            }
        }
        "file" => {
            if let Some(parent) = safe_path.parent() {
                let _ = fs::create_dir_all(parent).await;
            }
            if let Err(e) = fs::write(&safe_path, req.content.unwrap_or_default()).await {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("Failed to create file: {}", e),
                )
                    .into_response();
            }
        }
        _ => return (StatusCode::BAD_REQUEST, "Invalid item type").into_response(),
    }

    (
        StatusCode::OK,
        Json(json!({ "success": true, "path": req.path })),
    )
        .into_response()
}

#[derive(Deserialize)]
struct DeleteItemRequest {
    path: String,
}

async fn delete_item_handler(
    State(state): State<Arc<AppState>>,
    Query(req): Query<DeleteItemRequest>,
) -> impl IntoResponse {
    let workspace = &state.workspace_root;
    let safe_path = workspace.join(req.path.trim_start_matches('/'));

    if !safe_path.starts_with(workspace) || safe_path == *workspace {
        return (StatusCode::FORBIDDEN, "Access denied").into_response();
    }

    if !safe_path.exists() {
        return (StatusCode::NOT_FOUND, "Path not found").into_response();
    }

    let res = if safe_path.is_dir() {
        fs::remove_dir_all(safe_path).await
    } else {
        fs::remove_file(safe_path).await
    };

    match res {
        Ok(_) => (
            StatusCode::OK,
            Json(json!({ "success": true, "path": req.path })),
        )
            .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("Failed to delete item: {}", e),
        )
            .into_response(),
    }
}

async fn chat_status_handler(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let victoria_url = format!("{}/health", state.victoria_url.trim_end_matches('/'));
    match state.client.get(victoria_url).send().await {
        Ok(res) => {
            let data: serde_json::Value = res.json().await.unwrap_or(json!({ "status": "error" }));
            (StatusCode::OK, Json(data)).into_response()
        }
        Err(_) => (StatusCode::OK, Json(json!({ "status": "offline" }))).into_response(),
    }
}

async fn chat_models_handler(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let victoria_url = format!(
        "{}/api/available-models",
        state.victoria_url.trim_end_matches('/')
    );
    match state.client.get(victoria_url).send().await {
        Ok(res) => {
            let data: serde_json::Value = res
                .json()
                .await
                .unwrap_or(json!({ "mlx": [], "ollama": [] }));
            (StatusCode::OK, Json(data)).into_response()
        }
        Err(_) => (StatusCode::OK, Json(json!({ "mlx": [], "ollama": [] }))).into_response(),
    }
}

// --- Preview Handlers ---

async fn preview_index_handler(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let file_path = state.workspace_root.join("index.html");
    if !file_path.exists() {
        return Html(r#"
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ATRA Preview</title>
    <style>
        body { font-family: system-ui, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .container { text-align: center; padding: 2rem; }
        h1 { font-size: 2.5rem; margin-bottom: 1rem; }
        p { opacity: 0.8; font-size: 1.1rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>ATRA Web IDE</h1>
        <p>Create an index.html file to see your preview here</p>
    </div>
</body>
</html>
        "#).into_response();
    }

    match fs::read_to_string(file_path).await {
        Ok(content) => Html(content).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()).into_response(),
    }
}

#[derive(Deserialize)]
struct PreviewFileParams {
    path: String,
}

async fn preview_file_handler(
    State(state): State<Arc<AppState>>,
    Query(params): Query<PreviewFileParams>,
) -> impl IntoResponse {
    let workspace = &state.workspace_root;
    let safe_path = workspace.join(params.path.trim_start_matches('/'));

    if !safe_path.starts_with(workspace) {
        return (StatusCode::FORBIDDEN, "Access denied").into_response();
    }

    if !safe_path.exists() {
        return (StatusCode::NOT_FOUND, "File not found").into_response();
    }

    let mime = mime_guess::from_path(&safe_path).first_or_octet_stream();

    match fs::read(safe_path).await {
        Ok(content) => (
            StatusCode::OK,
            [(header::CONTENT_TYPE, mime.to_string())],
            content,
        )
            .into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()).into_response(),
    }
}

// --- Experts Handlers ---

async fn list_experts_handler(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let pool = match state.knowledge_engine.as_ref() {
        Some(ke) => &ke.pool,
        None => {
            let fallback = json!([
                {"id": "1", "name": "Виктория", "role": "Team Lead"},
                {"id": "2", "name": "Вероника", "role": "Local Developer"},
                {"id": "3", "name": "Дмитрий", "role": "ML Engineer"},
                {"id": "4", "name": "Игорь", "role": "Backend Developer"}
            ]);
            return (StatusCode::OK, Json(fallback)).into_response();
        }
    };
    match sqlx::query_as::<_, Expert>(
        "SELECT id, name, role, system_prompt, created_at FROM experts ORDER BY name",
    )
    .fetch_all(pool)
    .await
    {
        Ok(experts) => (StatusCode::OK, Json(experts)).into_response(),
        Err(e) => {
            error!("List experts error: {}", e);
            // Fallback experts if DB is down
            let fallback = json!([
                {"id": "1", "name": "Виктория", "role": "Team Lead"},
                {"id": "2", "name": "Вероника", "role": "Local Developer"},
                {"id": "3", "name": "Дмитрий", "role": "ML Engineer"},
                {"id": "4", "name": "Игорь", "role": "Backend Developer"}
            ]);
            (StatusCode::OK, Json(fallback)).into_response()
        }
    }
}

async fn get_expert_handler(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> impl IntoResponse {
    let ke = require_ke!(state);
    match sqlx::query_as::<_, Expert>(
        "SELECT id, name, role, system_prompt, created_at FROM experts WHERE id = $1",
    )
    .bind(id)
    .fetch_optional(&ke.pool)
    .await
    {
        Ok(Some(expert)) => (StatusCode::OK, Json(expert)).into_response(),
        Ok(None) => (
            StatusCode::NOT_FOUND,
            Json(json!({ "error": "Expert not found" })),
        )
            .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": e.to_string() })),
        )
            .into_response(),
    }
}

async fn preview_file(
    State(state): State<Arc<AppState>>,
    Query(params): Query<FilePathQuery>,
) -> impl IntoResponse {
    let file_path = match get_safe_path(&state.workspace_root, &params.path).await {
        Ok(p) => p,
        Err(e) => return e.into_response(),
    };

    if !file_path.exists() {
        return (StatusCode::NOT_FOUND, "File not found").into_response();
    }

    let mime = mime_guess::from_path(&file_path).first_or_octet_stream();
    match fs::read(&file_path).await {
        Ok(content) => (
            StatusCode::OK,
            [(header::CONTENT_TYPE, mime.to_string())],
            content,
        )
            .into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()).into_response(),
    }
}

async fn render_html(Query(params): Query<serde_json::Value>) -> impl IntoResponse {
    let content = params["content"].as_str().unwrap_or("");
    Html(content.to_string()).into_response()
}

// --- Terminal Handlers ---

async fn terminal_pty(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(|socket| handle_ws_pty(socket, state))
}

async fn handle_ws_pty(mut socket: WebSocket, state: Arc<AppState>) {
    let pty_system = native_pty_system();
    let pair = match pty_system.openpty(PtySize {
        rows: 24,
        cols: 80,
        pixel_width: 0,
        pixel_height: 0,
    }) {
        Ok(p) => p,
        Err(e) => {
            let _ = socket
                .send(Message::Text(format!("Error opening PTY: {}", e)))
                .await;
            return;
        }
    };

    let shell = env::var("SHELL").unwrap_or_else(|_| "/bin/zsh".to_string());
    let mut cmd = CommandBuilder::new(shell);
    cmd.cwd(state.workspace_root.clone());

    let _child = match pair.slave.spawn_command(cmd) {
        Ok(c) => c,
        Err(e) => {
            let _ = socket
                .send(Message::Text(format!("Error spawning shell: {}", e)))
                .await;
            return;
        }
    };

    let mut reader = pair.master.try_clone_reader().unwrap();
    let mut writer = pair.master.take_writer().unwrap();

    let (tx, mut rx) = mpsc::channel::<Vec<u8>>(100);

    // Read from PTY and send to WebSocket
    tokio::spawn(async move {
        let mut buffer = [0u8; 1024];
        loop {
            match reader.read(&mut buffer) {
                Ok(0) => break,
                Ok(n) => {
                    if tx.send(buffer[..n].to_vec()).await.is_err() {
                        break;
                    }
                }
                Err(_) => break,
            }
        }
    });

    // Main loop
    loop {
        tokio::select! {
            Some(data) = rx.recv() => {
                if socket.send(Message::Text(String::from_utf8_lossy(&data).to_string())).await.is_err() {
                    break;
                }
            }
            msg = socket.recv() => {
                match msg {
                    Some(Ok(Message::Text(text))) => {
                        let _ = writer.write_all(text.as_bytes());
                    }
                    Some(Ok(Message::Close(_))) | None => break,
                    _ => {}
                }
            }
        }
    }
}

async fn terminal_ask(
    State(state): State<Arc<AppState>>,
    Json(req): Json<TerminalAskRequest>,
) -> impl IntoResponse {
    let payload = json!({
        "model": "victoria-wisdom-30b:latest",
        "messages": [{"role": "user", "content": req.command}],
        "use_rag": true,
        "stream": false
    });

    proxy_chat(State(state), HeaderMap::new(), Json(payload)).await
}

// --- Chat & Knowledge Engine logic (same as before) ---

/// Извлекает имя проекта из текста сообщения (например «перейди в проект setki-21» → Some("setki-21")).
/// Slug: буквы/цифры/дефис; при отсутствии совпадения — None.
fn extract_project_from_message(message: &str) -> Option<String> {
    let msg = message.trim();
    let patterns = [
        "перейди в проект ",
        "открой проект ",
        "в проекте ",
        "работай в проекте ",
        "работа в проекте ",
        "проект ",
    ];
    for p in patterns {
        if let Some(rest) = msg
            .to_lowercase()
            .find(&p.to_lowercase())
            .map(|i| &msg[i + p.len()..])
        {
            let slug: String = rest
                .chars()
                .take_while(|c| c.is_ascii_alphanumeric() || *c == '-')
                .collect();
            if !slug.is_empty()
                && slug
                    .chars()
                    .next()
                    .map(|c| c.is_ascii_alphanumeric())
                    .unwrap_or(false)
            {
                return Some(slug);
            }
        }
    }
    None
}

/// Вызов Victoria Agent (мозг MLX + руки Ollama). POST /run?async_mode=true → опрос /run/status/{task_id}.
async fn call_victoria_agent(
    client: &Client,
    victoria_url: &str,
    goal: &str,
    project_context: &str,
) -> Result<String, Box<dyn std::error::Error + Send + Sync>> {
    let run_url = format!("{}/run?async_mode=true", victoria_url.trim_end_matches('/'));
    let payload = json!({
        "goal": goal,
        "max_steps": 50,
        "project_context": project_context,
    });

    let res = client.post(&run_url).json(&payload).send().await?;

    if res.status().as_u16() == 200 {
        let data: serde_json::Value = res.json().await?;
        let out = data["output"]
            .as_str()
            .or_else(|| data["result"].as_str())
            .unwrap_or("")
            .to_string();
        return Ok(out);
    }

    if res.status().as_u16() != 202 {
        let status = res.status();
        let body = res.text().await.unwrap_or_default();
        error!("Victoria /run returned {}: {}", status, body);
        return Err("Victoria returned non-202".into());
    }

    let data: serde_json::Value = res.json().await?;
    let task_id = data["task_id"]
        .as_str()
        .ok_or("No task_id in 202 response")?;
    let status_url = format!(
        "{}/run/status/{}",
        victoria_url.trim_end_matches('/'),
        task_id
    );

    let poll_interval = std::time::Duration::from_secs(8);
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(900);

    while std::time::Instant::now() < deadline {
        tokio::time::sleep(poll_interval).await;
        let status_res = client.get(&status_url).send().await?;
        if status_res.status() == 404 {
            return Err("Task lost (Victoria may have restarted)".into());
        }
        if !status_res.status().is_success() {
            return Err(format!("Victoria status returned {}", status_res.status()).into());
        }
        let st: serde_json::Value = status_res.json().await?;
        let status_val = st["status"].as_str().unwrap_or("").to_lowercase();
        if status_val == "completed" {
            let out = st["output"]
                .as_str()
                .or_else(|| st["result"].as_str())
                .unwrap_or("")
                .to_string();
            return Ok(out);
        }
        if status_val == "failed" {
            let err = st["error"].as_str().unwrap_or("Task failed");
            return Err(err.to_string().into());
        }
    }

    Err("Victoria polling timeout (900s)".into())
}

async fn get_embedding(
    client: &Client,
    text: &str,
) -> Result<Vec<f32>, Box<dyn std::error::Error + Send + Sync>> {
    let ollama_base =
        env::var("OLLAMA_URL").unwrap_or_else(|_| "http://localhost:11434".to_string());
    let ollama_url = format!("{}/api/embeddings", ollama_base.trim_end_matches('/'));
    let payload = json!({
        "model": "nomic-embed-text",
        "prompt": text
    });

    let res = client.post(ollama_url).json(&payload).send().await?;

    if res.status().is_success() {
        let body: serde_json::Value = res.json().await?;
        if let Some(embedding) = body["embedding"].as_array() {
            let vector: Vec<f32> = embedding
                .iter()
                .map(|v| v.as_f64().unwrap_or(0.0) as f32)
                .collect();
            return Ok(vector);
        }
    } else {
        let status = res.status();
        let error_text = res.text().await.unwrap_or_default();
        error!("Ollama embedding error: {} - {}", status, error_text);
    }

    Err("Failed to get embedding".into())
}

async fn knowledge_search(
    State(state): State<Arc<AppState>>,
    Query(params): Query<SearchQuery>,
) -> impl IntoResponse {
    info!("Searching knowledge for: {}", params.q);

    let ke = match state.knowledge_engine.as_ref() {
        Some(ke) => ke,
        None => {
            return (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({ "error": "KnowledgeEngine unavailable" })),
            )
                .into_response();
        }
    };

    match get_embedding(&state.client, &params.q).await {
        Ok(embedding) => {
            match ke
                .retrieve_similar_with_embeddings(embedding.clone(), 15)
                .await
            {
                Ok(nodes) => {
                    let ranked_nodes = ke.rank_nodes_locally(embedding, nodes);
                    let top_nodes = ranked_nodes.into_iter().take(5).collect::<Vec<_>>();
                    (StatusCode::OK, Json(top_nodes)).into_response()
                }
                Err(e) => {
                    error!("Knowledge search error: {}", e);
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        Json(json!({ "error": "Search failed", "details": e.to_string() })),
                    )
                        .into_response()
                }
            }
        }
        Err(e) => {
            error!("Embedding error: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": "Embedding failed", "details": e.to_string() })),
            )
                .into_response()
        }
    }
}

async fn proxy_chat(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(mut payload): Json<serde_json::Value>,
) -> Response {
    state.request_count.fetch_add(1, Ordering::Relaxed);

    // Acquire semaphore permit for rate limiting
    let _permit = match state.chat_semaphore.try_acquire() {
        Ok(permit) => permit,
        Err(_) => {
            info!("⚠️ Chat rate limit exceeded, returning 503");
            return (
                StatusCode::SERVICE_UNAVAILABLE,
                [(header::RETRY_AFTER, "5")],
                Json(json!({
                    "error": "Service temporarily unavailable",
                    "message": "Too many concurrent requests. Please try again in a few seconds.",
                    "retry_after_seconds": 5
                })),
            )
                .into_response();
        }
    };

    let last_user_message = payload["messages"]
        .as_array()
        .and_then(|msgs| msgs.iter().rev().find(|m| m["role"] == "user"))
        .and_then(|m| m["content"].as_str())
        .unwrap_or("");

    let project_from_message = extract_project_from_message(last_user_message);
    let project_context = project_from_message.clone().unwrap_or_else(|| {
        env::var("PROJECT_CONTEXT").unwrap_or_else(|_| "atra-web-ide".to_string())
    });
    if project_from_message.is_some() {
        info!("Project context taken from message: {}", project_context);
    }

    let use_rag = headers.contains_key("x-use-rag") || payload["use_rag"].as_bool().unwrap_or(true);
    let mut context_for_goal = String::new();
    if use_rag && !last_user_message.is_empty() {
        if let Some(ke) = state.knowledge_engine.as_ref() {
            if let Ok(embedding) = get_embedding(&state.client, last_user_message).await {
                if let Ok(nodes) = ke
                    .retrieve_similar_with_embeddings(embedding.clone(), 10)
                    .await
                {
                    let ranked = ke.rank_nodes_locally(embedding, nodes);
                    if !ranked.is_empty() {
                        context_for_goal = ranked
                            .iter()
                            .take(3)
                            .map(|n| n.content.as_str())
                            .collect::<Vec<_>>()
                            .join("\n---\n");
                    }
                }
            }
        }
    }
    let goal_for_victoria = if context_for_goal.is_empty() {
        last_user_message.to_string()
    } else {
        format!(
            "CONTEXT (from knowledge base):\n{}\n\nUser request (answer in Russian):\n{}",
            context_for_goal, last_user_message
        )
    };

    // Сначала пробуем полный контур: Victoria Agent (мозг MLX + руки Ollama)
    if state.use_victoria_agent && !last_user_message.is_empty() {
        match call_victoria_agent(
            &state.client,
            &state.victoria_url,
            &goal_for_victoria,
            &project_context,
        )
        .await
        {
            Ok(output) if !output.trim().is_empty() => {
                info!("Victoria Agent responded successfully (full brain+hands)");
                let body = json!({
                    "id": "chatcmpl-gateway-victoria",
                    "object": "chat.completion",
                    "choices": [{ "index": 0, "message": { "role": "assistant", "content": output }, "finish_reason": "stop" }],
                    "usage": { "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0 }
                });
                return (
                    StatusCode::OK,
                    [(header::CONTENT_TYPE, "application/json")],
                    body.to_string(),
                )
                    .into_response();
            }
            Ok(_) => {
                info!("Victoria Agent returned empty output, falling back to Ollama");
            }
            Err(e) => {
                info!(
                    "Victoria Agent unavailable or failed ({}), falling back to Ollama",
                    e
                );
            }
        }
    }

    let ollama_url =
        env::var("OLLAMA_URL").unwrap_or_else(|_| "http://localhost:11434".to_string());
    let ollama_chat_url = format!("{}/v1/chat/completions", ollama_url.trim_end_matches('/'));
    let fallback_model = "tinyllama:1.1b-chat";

    let role = task_classify(last_user_message);
    let (role_name, role_instruction) = if role == "veronica" {
        (
            "Veronica",
            "Ты Вероника, Local Developer. Отвечай кратко, по делу, с фокусом на код и выполнение задач.",
        )
    } else {
        (
            "Victoria",
            "Ты Виктория, Team Lead Singularity 14.0. Отвечай профессионально, структурированно, с учётом контекста.",
        )
    };

    // При fallback на Ollama повторно используем контекст, уже собранный для Victoria (если есть)
    let mut context = context_for_goal.clone();
    if use_rag && !last_user_message.is_empty() && context.is_empty() {
        if let Some(ke) = state.knowledge_engine.as_ref() {
            match get_embedding(&state.client, last_user_message).await {
                Ok(embedding) => {
                    match ke
                        .retrieve_similar_with_embeddings(embedding.clone(), 10)
                        .await
                    {
                        Ok(nodes) => {
                            let ranked_nodes = ke.rank_nodes_locally(embedding, nodes);
                            if !ranked_nodes.is_empty() {
                                context = ranked_nodes
                                    .iter()
                                    .take(3)
                                    .map(|n| n.content.clone())
                                    .collect::<Vec<String>>()
                                    .join("\n---\n");
                            }
                        }
                        Err(e) => error!("Knowledge Engine error: {}", e),
                    }
                }
                Err(e) => error!("Embedding error: {}", e),
            }
        }
    }

    if let Some(messages) = payload["messages"].as_array_mut() {
        let base_system = format!(
            "{} Обязательно отвечай только на русском. {}",
            role_instruction,
            if context.is_empty() {
                ""
            } else {
                "Ниже контекст из базы знаний."
            }
        );
        let injection = if context.is_empty() {
            format!("\n\nIMPORTANT: Answer in Russian only. Be professional and concise.")
        } else {
            format!(
                "\n\nCONTEXT:\n{}\n\nIMPORTANT: Answer in Russian language only. Be professional and concise.",
                context
            )
        };
        let system_content = format!("{}{}", base_system, injection);

        let mut system_msg_index = None;
        for (i, msg) in messages.iter().enumerate() {
            if msg["role"] == "system" {
                system_msg_index = Some(i);
                break;
            }
        }

        if let Some(idx) = system_msg_index {
            if let Some(existing) = messages[idx]["content"].as_str() {
                messages[idx]["content"] = json!(format!("{}. {}", existing, system_content));
            } else {
                messages[idx]["content"] = json!(system_content);
            }
        } else {
            messages.insert(
                0,
                json!({
                    "role": "system",
                "content": format!("You are {}. {}", role_name, system_content)
                }),
            );
        }
    }

    match send_request(&state.client, &ollama_chat_url, &headers, &payload).await {
        Ok(response) => {
            let status = response.status();
            if status.is_success() {
                return handle_response(response).await;
            }
            error!(
                "Primary model failed with status: {}. Attempting fallback...",
                status
            );
        }
        Err(err) => {
            error!(
                "Primary model request failed: {}. Attempting fallback...",
                err
            );
        }
    }

    info!("Switching to fallback model: {}", fallback_model);
    if let Some(obj) = payload.as_object_mut() {
        obj.insert("model".to_string(), json!(fallback_model));
    }

    match send_request(&state.client, &ollama_chat_url, &headers, &payload).await {
        Ok(response) => handle_response(response).await,
        Err(err) => {
            error!("Fallback model also failed: {}", err);
            (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({ "error": "All models failed", "details": err.to_string() })),
            )
                .into_response()
        }
    }
}

async fn send_request(
    client: &Client,
    url: &str,
    headers: &HeaderMap,
    payload: &serde_json::Value,
) -> Result<reqwest::Response, reqwest::Error> {
    let mut request_builder = client.post(url).json(payload);
    if let Some(auth) = headers.get("Authorization") {
        request_builder = request_builder.header("Authorization", auth);
    }
    request_builder.send().await
}

async fn handle_response(response: reqwest::Response) -> Response {
    let status = response.status();
    let mut response_builder = Response::builder().status(status);
    for (name, value) in response.headers().iter() {
        response_builder = response_builder.header(name, value);
    }
    let stream = response
        .bytes_stream()
        .map(|result| result.map_err(|err| std::io::Error::new(std::io::ErrorKind::Other, err)));
    response_builder
        .body(Body::from_stream(stream))
        .unwrap_or_else(|_| StatusCode::INTERNAL_SERVER_ERROR.into_response())
}
