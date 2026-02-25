use axum::{
    routing::get,
    Router,
};
use std::net::SocketAddr;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Инициализация логирования
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "atra_core=debug".into()))
        .with(tracing_subscriber::fmt::layer())
        .init();

    tracing::info!("🚀 Starting Atra OS Kernel (Rust)...");

    // Маршруты
    let app = Router::new()
        .route("/health", get(|| async { "OK" }))
        .route("/api/v1/info", get(|| async { "Atra OS Kernel v0.1.0" }));

    // Запуск сервера
    let addr = SocketAddr::from(([0, 0, 0, 0], 8081));
    tracing::info!("📡 Listening on {}", addr);
    
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
