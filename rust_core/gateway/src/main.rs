use axum::{
    routing::{get, post},
    Router,
    response::IntoResponse,
    Json,
};
use std::net::SocketAddr;
use tracing_subscriber;

#[tokio::main]
async fn main() {
    // Initialize logging
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
    println!("📡 Received chat request: {:?}", payload);
    // TODO: Implement routing logic to MLX/Ollama
    Json(payload)
}
