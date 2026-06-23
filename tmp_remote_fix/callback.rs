//! Прокси POST /api/callback в Nuxt (web). В проде NPM направляет /api/* в moskit-api,
//! а эндпоинт обратного звонка и отправка письма реализованы в Nuxt (server/api/callback.post.ts).
//!
//! Дополнительно, перед проксированием в Nuxt, мы пишем заявку в БД (`callback_requests`),
//! чтобы заявка гарантированно попадала в админку "Звонки", даже если SMTP/Nuxt вернёт ошибку.

use axum::{
    body::{Body, Bytes},
    extract::State,
    http::{HeaderMap, StatusCode, header},
    response::{IntoResponse, Response},
};
use reqwest::Client;
use serde::Deserialize;
use std::{sync::Arc, time::Duration};
use uuid::Uuid;

use crate::AppState;

const DEFAULT_CALLBACK_PROXY_URL: &str = "http://web:3000";

#[derive(Debug, Deserialize)]
struct CallbackProxyPayload {
    name: Option<String>,
    phone: Option<String>,
    city: Option<String>,
    domain: Option<String>,
    extra_services: Option<String>,
}

fn normalize_domain(raw: &str) -> String {
    let mut d = raw.trim().to_lowercase();
    if let Some(rest) = d.strip_prefix("http://") {
        d = rest.to_string();
    }
    if let Some(rest) = d.strip_prefix("https://") {
        d = rest.to_string();
    }
    if let Some(idx) = d.find('/') {
        d = d[..idx].to_string();
    }
    if let Some(idx) = d.find(':') {
        d = d[..idx].to_string();
    }
    if let Some(rest) = d.strip_prefix("www.") {
        d = rest.to_string();
    }
    d
}

async fn resolve_dealer_id(pool: &sqlx::PgPool, domain: &str) -> Option<Uuid> {
    let d = normalize_domain(domain);
    if d.is_empty() {
        return None;
    }

    let from_domains: Option<Uuid> = sqlx::query_scalar(
        "SELECT dealer_id FROM dealer_domains \
         WHERE lower(regexp_replace(domain, '^www\\.', '')) = $1 LIMIT 1",
    )
    .bind(&d)
    .fetch_optional(pool)
    .await
    .ok()
    .flatten();

    if from_domains.is_some() {
        return from_domains;
    }

    sqlx::query_scalar(
        "SELECT id FROM dealers \
         WHERE lower(regexp_replace(coalesce(domain, ''), '^www\\.', '')) = $1 LIMIT 1",
    )
    .bind(&d)
    .fetch_optional(pool)
    .await
    .ok()
    .flatten()
}

async fn persist_callback(state: &Arc<AppState>, headers: &HeaderMap, body_bytes: &[u8]) {
    let payload: CallbackProxyPayload = match serde_json::from_slice(body_bytes) {
        Ok(p) => p,
        Err(e) => {
            tracing::warn!("callback proxy: cannot parse body for DB persist: {}", e);
            return;
        }
    };

    let name = payload.name.unwrap_or_default().trim().to_string();
    let phone = payload.phone.unwrap_or_default().trim().to_string();
    if name.is_empty() || phone.is_empty() {
        tracing::warn!("callback proxy: skip DB persist because name/phone are empty");
        return;
    }

    let domain = payload
        .domain
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .or_else(|| {
            headers
                .get("host")
                .and_then(|h| h.to_str().ok())
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
        });

    let dealer_id = if let Some(d) = &domain {
        resolve_dealer_id(&state.pool, d).await
    } else {
        None
    };

    let insert = sqlx::query(
        "INSERT INTO callback_requests \
         (dealer_id, name, phone, city, domain, extra_services, status, created_at, updated_at) \
         VALUES ($1, $2, $3, $4, $5, $6, 'new', NOW(), NOW())",
    )
    .bind(dealer_id)
    .bind(&name)
    .bind(&phone)
    .bind(
        payload
            .city
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty()),
    )
    .bind(domain.clone())
    .bind(
        payload
            .extra_services
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty()),
    )
    .execute(&state.pool)
    .await;

    match insert {
        Ok(_) => tracing::info!(
            "callback persisted in DB (dealer_id={:?}, domain={:?})",
            dealer_id,
            domain
        ),
        Err(e) => tracing::error!("callback proxy: failed to persist callback_requests: {}", e),
    }
}

/// Проксирует POST /api/callback в Nuxt (web). Тело передаётся как есть.
pub async fn proxy_callback(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    body: Bytes,
) -> Response {
    let body_bytes = if body.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            [(header::CONTENT_TYPE, "application/json")],
            r#"{"message":"Invalid body"}"#,
        )
            .into_response();
    } else {
        body
    };

    // Пишем callback в БД для отображения в админке "Звонки".
    // Не блокируем отправку письма, если запись в БД не удалась — важно сохранить лид во всех каналах.
    persist_callback(&state, &headers, &body_bytes).await;

    let url = std::env::var("CALLBACK_PROXY_URL")
        .unwrap_or_else(|_| DEFAULT_CALLBACK_PROXY_URL.to_string());
    let full_url = format!("{}/api/callback", url.trim_end_matches('/'));

    let client = match Client::builder().timeout(Duration::from_secs(15)).build() {
        Ok(c) => c,
        Err(e) => {
            tracing::error!("callback proxy: client build: {}", e);
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                [(header::CONTENT_TYPE, "application/json")],
                r#"{"message":"Ошибка сервиса"}"#,
            )
                .into_response();
        }
    };

    let resp = match client
        .post(&full_url)
        .header("Content-Type", "application/json")
        .body(body_bytes.to_vec())
        .send()
        .await
    {
        Ok(r) => r,
        Err(e) => {
            tracing::error!("callback proxy: request to Nuxt failed: {}", e);
            return (
                StatusCode::BAD_GATEWAY,
                [(header::CONTENT_TYPE, "application/json")],
                format!(r#"{{"message":"Сервис временно недоступен"}}"#),
            )
                .into_response();
        }
    };

    let status =
        StatusCode::from_u16(resp.status().as_u16()).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
    let body = match resp.bytes().await {
        Ok(b) => b.to_vec(),
        Err(e) => {
            tracing::warn!("callback proxy: read response body: {}", e);
            return (
                StatusCode::BAD_GATEWAY,
                [(header::CONTENT_TYPE, "application/json")],
                r#"{"message":"Ошибка ответа сервиса"}"#,
            )
                .into_response();
        }
    };

    (
        status,
        [(header::CONTENT_TYPE, "application/json")],
        Body::from(body),
    )
        .into_response()
}
