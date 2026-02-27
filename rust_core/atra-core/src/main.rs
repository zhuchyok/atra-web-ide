use axum::{
    Router,
    extract::Json,
    http::StatusCode,
    response::Html,
    routing::{get, post},
};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[derive(Deserialize)]
struct LoginRequest {
    email: String,
    password: String,
}

#[derive(Serialize)]
struct LoginSuccess {
    user_id: u32,
    role: String,
    name: String,
    token: String,
}

async fn auth_login(Json(body): Json<LoginRequest>) -> (StatusCode, Json<serde_json::Value>) {
    let email = body.email.trim().to_lowercase();
    let admin_email = std::env::var("AUTH_ADMIN_EMAIL").unwrap_or_else(|_| String::new());
    let admin_password = std::env::var("AUTH_ADMIN_PASSWORD").unwrap_or_else(|_| String::new());

    if admin_email.is_empty() || admin_password.is_empty() {
        tracing::warn!("Auth not configured: set AUTH_ADMIN_EMAIL and AUTH_ADMIN_PASSWORD");
        return (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(
                serde_json::json!({ "message": "Вход временно недоступен. Свяжитесь с менеджером." }),
            ),
        );
    }

    if email == admin_email && body.password == admin_password {
        let response = LoginSuccess {
            user_id: 1,
            role: "admin".to_string(),
            name: "Администратор".to_string(),
            token: format!("atra-{}", uuid::Uuid::new_v4()),
        };
        return (
            StatusCode::OK,
            Json(serde_json::to_value(response).unwrap()),
        );
    }

    (
        StatusCode::UNAUTHORIZED,
        Json(serde_json::json!({ "message": "Неверный email или пароль" })),
    )
}

async fn root_page() -> Html<&'static str> {
    Html(
        r#"<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Atra OS</title></head>
<body style="font-family:sans-serif;max-width:40em;margin:2em auto;padding:0 1em">
<h1>Atra OS Kernel</h1>
<p>API доступен по эндпоинтам:</p>
<ul>
<li><a href="/health">/health</a> — проверка работы</li>
<li><a href="/api/v1/info">/api/v1/info</a> — информация о версии</li>
</ul>
</body></html>"#,
    )
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Инициализация логирования
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "atra_core=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    tracing::info!("🚀 Starting Atra OS Kernel (Rust)...");

    // Маршруты
    let app = Router::new()
        .route("/", get(root_page))
        .route("/health", get(|| async { "OK" }))
        .route("/api/v1/info", get(|| async { "Atra OS Kernel v0.1.0" }))
        .route("/api/v1/auth/login", post(auth_login));

    // Запуск сервера
    let addr = SocketAddr::from(([0, 0, 0, 0], 8081));
    tracing::info!("📡 Listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
