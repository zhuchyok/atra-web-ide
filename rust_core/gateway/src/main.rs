use axum::{
    body::Body,
    extract::State,
    http::{HeaderMap, StatusCode, Method},
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use futures_util::StreamExt;
use reqwest::Client;
use serde_json::json;
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;
use tower_http::cors::{Any, CorsLayer};
use tracing::{info, error};

struct AppState {
    client: Client,
}

#[tokio::main]
async fn main() {
    // Initialize logging
    tracing_subscriber::fmt::init();

    let client = Client::builder()
        .timeout(Duration::from_secs(60))
        .build()
        .expect("Failed to create reqwest client");

    let state = Arc::new(AppState { client });

    // Configure CORS
    let cors = CorsLayer::new()
        .allow_origin([
            "http://localhost:3000".parse().unwrap(),
            "http://localhost:3002".parse().unwrap(),
        ])
        .allow_methods([Method::GET, Method::POST])
        .allow_headers(Any);

    let app = Router::new()
        .route("/health", get(health_check))
        .route("/v1/chat/completions", post(proxy_chat))
        .layer(cors)
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], 8081));
    info!("🚀 Rust API Gateway listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn health_check() -> &'static str {
    "OK"
}

async fn proxy_chat(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(mut payload): Json<serde_json::Value>,
) -> Response {
    let ollama_url = "http://localhost:11434/v1/chat/completions";
    let fallback_model = "phi3.5:3.8b";

    // Attempt primary request
    match send_request(&state.client, ollama_url, &headers, &payload).await {
        Ok(response) => {
            let status = response.status();
            if status.is_success() {
                return handle_response(response).await;
            }
            error!("Primary model failed with status: {}. Attempting fallback...", status);
        }
        Err(err) => {
            error!("Primary model request failed: {}. Attempting fallback...", err);
        }
    }

    // Fallback logic
    info!("Switching to fallback model: {}", fallback_model);
    if let Some(obj) = payload.as_object_mut() {
        obj.insert("model".to_string(), json!(fallback_model));
    }

    match send_request(&state.client, ollama_url, &headers, &payload).await {
        Ok(response) => handle_response(response).await,
        Err(err) => {
            error!("Fallback model also failed: {}", err);
            (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({
                    "error": "All models failed",
                    "details": err.to_string()
                })),
            ).into_response()
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

    let stream = response.bytes_stream().map(|result| {
        result.map_err(|err| std::io::Error::new(std::io::ErrorKind::Other, err))
    });

    response_builder
        .body(Body::from_stream(stream))
        .unwrap_or_else(|_| StatusCode::INTERNAL_SERVER_ERROR.into_response())
}
