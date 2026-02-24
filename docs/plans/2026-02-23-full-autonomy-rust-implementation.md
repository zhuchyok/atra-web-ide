# Full Autonomy & Rust Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Rust-based Scout-agent for offline knowledge indexing and a high-performance API Gateway to replace Python-based routing.

**Architecture:** 
- **Scout-agent:** A standalone Rust binary using `reqwest` for crawling and `sqlx` for storing дистиллированные знания in PostgreSQL (knowledge_nodes).
- **API Gateway:** An `axum` based server that routes requests between Victoria (Docker) and MLX/Ollama (Host), optimizing for low latency and high concurrency.

**Tech Stack:** Rust, Axum, Tokio, Sqlx (PostgreSQL), Reqwest, Serde.

---

### Task 1: Initialize Rust Workspace
**Files:**
- Create: `Cargo.toml` (Workspace)
- Create: `rust_core/Cargo.toml`
- Create: `rust_core/scout/Cargo.toml`
- Create: `rust_core/gateway/Cargo.toml`

**Step 1: Create workspace Cargo.toml**
```toml
[workspace]
members = [
    "rust_core/scout",
    "rust_core/gateway",
]
resolver = "2"
```

**Step 2: Initialize Scout and Gateway projects**
Run: `mkdir -p rust_core/scout/src rust_core/gateway/src`
Run: `cargo init rust_core/scout --bin`
Run: `cargo init rust_core/gateway --bin`

**Step 3: Commit**
```bash
git add Cargo.toml rust_core/
git commit -m "infra: initialize rust workspace for scout and gateway"
```

---

### Task 2: Implement Scout-agent (Basic Crawler)
**Files:**
- Modify: `rust_core/scout/Cargo.toml`
- Modify: `rust_core/scout/src/main.rs`

**Step 1: Add dependencies to Scout**
```toml
[dependencies]
tokio = { version = "1", features = ["full"] }
reqwest = { version = "0.11", features = ["json"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
sqlx = { version = "0.7", features = ["runtime-tokio-rustls", "postgres", "chrono", "uuid"] }
dotenv = "0.15"
```

**Step 2: Implement basic crawl logic in `rust_core/scout/src/main.rs`**
```rust
use sqlx::postgres::PgPoolOptions;
use std::env;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenv::dotenv().ok();
    let db_url = env::var("DATABASE_URL")?;
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&db_url).await?;

    println!("🚀 Scout-agent started. Indexing Rust docs...");
    // TODO: Implement crawling logic for doc.rust-lang.org
    Ok(())
}
```

**Step 3: Commit**
```bash
git add rust_core/scout/
git commit -m "feat(scout): basic scout-agent structure with db connection"
```

---

### Task 3: Implement API Gateway (Basic Routing)
**Files:**
- Modify: `rust_core/gateway/Cargo.toml`
- Modify: `rust_core/gateway/src/main.rs`

**Step 1: Add dependencies to Gateway**
```toml
[dependencies]
axum = "0.7"
tokio = { version = "1", features = ["full"] }
tower-http = { version = "0.5", features = ["cors", "trace"] }
reqwest = { version = "0.12", features = ["json", "stream"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
tracing = "0.1"
tracing-subscriber = "0.3"
```

**Step 2: Implement basic proxy in `rust_core/gateway/src/main.rs`**
```rust
use axum::{
    routing::{get, post},
    Router,
    response::IntoResponse,
    Json,
};
use std::net::SocketAddr;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let app = Router::new()
        .route("/health", get(health_check))
        .route("/v1/chat/completions", post(proxy_chat));

    let addr = SocketAddr::from(([0, 0, 0, 0], 8081));
    println!("🚀 Rust API Gateway listening on {}", addr);
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn health_check() -> &'static str {
    "OK"
}

async fn proxy_chat(Json(payload): Json<serde_json::Value>) -> impl IntoResponse {
    // TODO: Implement routing logic to MLX/Ollama
    Json(payload)
}
```

**Step 3: Commit**
```bash
git add rust_core/gateway/
git commit -m "feat(gateway): basic axum gateway on port 8081"
```
