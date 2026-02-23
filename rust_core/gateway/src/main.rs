use axum::{
    body::Body,
    extract::State,
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use futures_util::StreamExt;
use reqwest::Client;
use serde_json::json;
use std::net::SocketAddr;
use std::sync::Arc;

struct AppState {
    client: Client,
}

#[tokio::main]
async fn main() {
    // Initialize logging
    tracing_subscriber::fmt::init();

    let state = Arc::new(AppState {
        client: Client::new(),
    });

    let app = Router::new()
        .route("/health", get(health_check))
        .route("/v1/chat/completions", post(proxy_chat))
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], 8081));
    println!("🚀 Rust API Gateway listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn health_check() -> &'static str {
    "OK"
}

async fn proxy_chat(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(payload): Json<serde_json::Value>,
) -> Response {
    let ollama_url = "http://localhost:11434/v1/chat/completions";

    let mut request_builder = state.client.post(ollama_url).json(&payload);

    if let Some(auth) = headers.get("Authorization") {
        request_builder = request_builder.header("Authorization", auth);
    }

    let response = match request_builder.send().await {
        Ok(res) => res,
        Err(err) => {
            return (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({
                    "error": "Ollama service is unavailable",
                    "details": err.to_string()
                })),
            )
                .into_response();
        }
    };

    let status = response.status();
    let mut response_builder = Response::builder().status(status);

    for (name, value) in response.headers().iter() {
        response_builder = response_builder.header(name, value);
    }

    let stream = response.bytes_stream().map(|result| {
        result.map_err(|err| std::io::Error::new(std::io::ErrorKind::Other, err))
    });

    response_builder
        .body(Body::from_stream(stream))
        .unwrap_or_else(|_| StatusCode::INTERNAL_SERVER_ERROR.into_response())
}
