// handlers/admin.rs - Обработчики для админа

use crate::AppState;
use crate::handlers::{ApiResult, bad_request, ok};
use crate::npm::NpmClient;
use axum::extract::Multipart;
use axum::{
    Json,
    extract::{Path, Query, State},
    http::StatusCode,
};
use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Serialize)]
pub struct OrderListItem {
    pub id: String,
    pub order_number: String,
    pub dealer_name: Option<String>,
    pub client_name: String,
    pub client_phone: String,
    pub status: String,
    pub total_amount: Decimal,
    pub created_at: String,
}

pub async fn list_all_orders(State(state): State<Arc<AppState>>) -> ApiResult<Vec<OrderListItem>> {
    use moskit_core::repository::{DealerRepository, PostgresDealerRepository};
    use moskit_core::repository::{OrderRepository, PostgresOrderRepository};

    let order_repo = PostgresOrderRepository::new(state.pool.clone());
    let dealer_repo = PostgresDealerRepository::new(state.pool.clone());

    let orders = order_repo
        .list(100, 0)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    let mut response = Vec::new();
    for o in orders {
        let dealer_name = if let Some(d_id) = o.dealer_id {
            dealer_repo
                .find_by_id(d_id)
                .await
                .ok()
                .flatten()
                .map(|d| d.name)
        } else {
            None
        };

        response.push(OrderListItem {
            id: o.id.to_string(),
            order_number: o.order_number,
            dealer_name,
            client_name: o.client_name,
            client_phone: o.client_phone,
            status: o.status.as_str().to_string(),
            total_amount: o.total_amount,
            created_at: o.created_at.to_rfc3339(),
        });
    }

    ok(response)
}

#[derive(Debug, Serialize)]
pub struct OrderDetailResponse {
    pub id: String,
    pub order_number: String,
    pub dealer_name: Option<String>,
    pub client_name: String,
    pub client_phone: String,
    pub client_address: Option<String>,
    pub status: String,
    pub total_amount: Decimal,
    pub created_at: String,
    pub comment: Option<String>,
    pub extra_services: Option<String>,
    pub installation_price: Option<Decimal>,
    pub delivery_price: Option<Decimal>,
    pub measurement_price: Option<Decimal>,
    pub items: Vec<OrderDetailItem>,
}

#[derive(Debug, Serialize)]
pub struct OrderDetailItem {
    pub id: String,
    pub name: String,
    pub quantity: i32,
    pub unit_price: Decimal,
    pub total_price: Decimal,
    pub params: serde_json::Value,
}

pub async fn get_order_detail(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> ApiResult<OrderDetailResponse> {
    use moskit_core::repository::{DealerRepository, PostgresDealerRepository};
    use moskit_core::repository::{OrderRepository, PostgresOrderRepository};

    let order_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;
    let order_repo = PostgresOrderRepository::new(state.pool.clone());
    let dealer_repo = PostgresDealerRepository::new(state.pool.clone());

    let order = order_repo
        .find_by_id(order_id)
        .await
        .map_err(|e| bad_request(&e.to_string()))?
        .ok_or_else(|| bad_request("Order not found"))?;

    let dealer_name = if let Some(d_id) = order.dealer_id {
        dealer_repo
            .find_by_id(d_id)
            .await
            .ok()
            .flatten()
            .map(|d| d.name)
    } else {
        None
    };

    let items = order
        .items
        .into_iter()
        .map(|i| OrderDetailItem {
            id: i.id.to_string(),
            name: i.name,
            quantity: i.quantity,
            unit_price: i.unit_price,
            total_price: i.total_price,
            params: i.params,
        })
        .collect();

    ok(OrderDetailResponse {
        id: order.id.to_string(),
        order_number: order.order_number,
        dealer_name,
        client_name: order.client_name,
        client_phone: order.client_phone,
        client_address: order.client_address,
        status: order.status.as_str().to_string(),
        total_amount: order.total_amount,
        created_at: order.created_at.to_rfc3339(),
        comment: order.comment,
        extra_services: order.extra_services,
        installation_price: order.installation_price,
        delivery_price: order.delivery_price,
        measurement_price: order.measurement_price,
        items,
    })
}

pub async fn delete_order(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> ApiResult<serde_json::Value> {
    let order_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;

    sqlx::query("DELETE FROM order_items WHERE order_id = $1")
        .bind(order_id)
        .execute(&state.pool)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    let result = sqlx::query("DELETE FROM orders WHERE id = $1")
        .bind(order_id)
        .execute(&state.pool)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    if result.rows_affected() == 0 {
        return Err(bad_request("Order not found"));
    }

    ok(serde_json::json!({ "success": true }))
}

pub async fn delete_callback(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> ApiResult<serde_json::Value> {
    let callback_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;

    let result = sqlx::query("DELETE FROM callback_requests WHERE id = $1")
        .bind(callback_id)
        .execute(&state.pool)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    if result.rows_affected() == 0 {
        return Err(bad_request("Callback not found"));
    }

    ok(serde_json::json!({ "success": true }))
}

#[derive(Debug, Serialize)]
pub struct CallbackListItem {
    pub id: String,
    pub dealer_id: Option<String>,
    pub dealer_name: Option<String>,
    pub name: String,
    pub phone: String,
    pub city: Option<String>,
    pub domain: Option<String>,
    pub extra_services: Option<String>,
    pub created_at: String,
}

pub async fn list_all_callbacks(
    State(state): State<Arc<AppState>>,
) -> ApiResult<Vec<CallbackListItem>> {
    use moskit_core::repository::{DealerRepository, PostgresDealerRepository};

    let dealer_repo = PostgresDealerRepository::new(state.pool.clone());

    let rows = sqlx::query("SELECT id, dealer_id, name, phone, city, domain, extra_services, created_at FROM callback_requests ORDER BY created_at DESC")
        .fetch_all(&state.pool)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    let mut response = Vec::new();
    for r in rows {
        use sqlx::Row;
        let d_id: Option<Uuid> = r.get("dealer_id");
        let dealer_name = if let Some(id) = d_id {
            dealer_repo
                .find_by_id(id)
                .await
                .ok()
                .flatten()
                .map(|d| d.name)
        } else {
            None
        };

        let created_at: DateTime<Utc> = r.get("created_at");

        response.push(CallbackListItem {
            id: r.get::<Uuid, _>("id").to_string(),
            dealer_id: d_id.map(|id| id.to_string()),
            dealer_name,
            name: r.get("name"),
            phone: r.get("phone"),
            city: r.get("city"),
            domain: r.get("domain"),
            extra_services: r.get("extra_services"),
            created_at: created_at.to_rfc3339(),
        });
    }

    ok(response)
}

pub async fn list_dealers(State(state): State<Arc<AppState>>) -> ApiResult<serde_json::Value> {
    use moskit_core::repository::{DealerRepository, PostgresDealerRepository};
    let repo = PostgresDealerRepository::new(state.pool.clone());
    let dealers = repo
        .list(100, 0)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;
    ok(serde_json::json!(dealers))
}

pub async fn get_dealer(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> ApiResult<serde_json::Value> {
    use moskit_core::repository::{DealerRepository, PostgresDealerRepository};
    let dealer_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;
    let repo = PostgresDealerRepository::new(state.pool.clone());
    let dealer = repo
        .find_by_id(dealer_id)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;
    match dealer {
        Some(d) => ok(serde_json::json!(d)),
        None => Err(bad_request("Dealer not found")),
    }
}

pub async fn update_order_status(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
    Json(payload): Json<serde_json::Value>,
) -> ApiResult<serde_json::Value> {
    let order_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;
    let status_str = payload
        .get("status")
        .and_then(|v| v.as_str())
        .ok_or_else(|| bad_request("Status is required"))?;

    sqlx::query("UPDATE orders SET status = $1, updated_at = NOW() WHERE id = $2")
        .bind(status_str)
        .bind(order_id)
        .execute(&state.pool)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    ok(serde_json::json!({ "success": true }))
}

pub async fn get_admin_stats(State(state): State<Arc<AppState>>) -> ApiResult<serde_json::Value> {
    let orders_count: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM orders")
        .fetch_one(&state.pool)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    let dealers_count: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM dealers")
        .fetch_one(&state.pool)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    let total_revenue: (Option<Decimal>,) = sqlx::query_as("SELECT SUM(total_amount) FROM orders")
        .fetch_one(&state.pool)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    ok(serde_json::json!({
        "orders_count": orders_count.0,
        "dealers_count": dealers_count.0,
        "total_revenue": total_revenue.0.unwrap_or(Decimal::ZERO),
    }))
}

pub async fn upload_image(
    State(_state): State<Arc<AppState>>,
    mut multipart: Multipart,
) -> ApiResult<serde_json::Value> {
    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|e| bad_request(&e.to_string()))?
    {
        let _name = field.name().unwrap_or("file").to_string();
        let file_name = field.file_name().unwrap_or("image.png").to_string();
        let data = field
            .bytes()
            .await
            .map_err(|e| bad_request(&e.to_string()))?;
        println!("Uploading file: {} ({} bytes)", file_name, data.len());
    }
    ok(serde_json::json!({ "url": "/uploads/temp.png" }))
}

#[derive(Debug, Deserialize)]
pub struct UpsertDealerRequest {
    pub name: String,
    pub city: String,
    pub phone: String,
    pub email: Option<String>,
    pub address: Option<String>,
    pub domain: Option<String>,
    pub delivery_mode: Option<String>,
    pub payment_type: Option<String>,
    pub balance: Option<Decimal>,
    pub credit_limit: Option<Decimal>,
    pub role: Option<String>,
    pub margin_config: Option<serde_json::Value>,
    pub margin_percent: Option<f64>,
    pub urgent_margin_percent: Option<f64>,
    pub delivery_margin_percent: Option<f64>,
    pub installation_margin_percent: Option<f64>,
    pub measurement_margin_percent: Option<f64>,
    pub branding: Option<serde_json::Value>,
    pub contacts: Option<serde_json::Value>,
    pub legal_info: Option<serde_json::Value>,
    pub seo_config: Option<serde_json::Value>,
}

fn build_margin_config(payload: &UpsertDealerRequest) -> serde_json::Value {
    let mut margin = payload
        .margin_config
        .clone()
        .unwrap_or_else(|| serde_json::json!({}));
    if !margin.is_object() {
        margin = serde_json::json!({});
    }
    let obj = margin.as_object_mut().expect("margin config object");

    if !obj.contains_key("city_multiplier") {
        obj.insert("city_multiplier".to_string(), serde_json::json!(1.0));
    }
    if !obj.contains_key("branch_multiplier") {
        obj.insert("branch_multiplier".to_string(), serde_json::json!(1.0));
    }
    if !obj.contains_key("volume_discounts") {
        obj.insert("volume_discounts".to_string(), serde_json::json!([]));
    }
    if !obj.contains_key("category_margins") {
        obj.insert("category_margins".to_string(), serde_json::json!({}));
    }
    if !obj.contains_key("category_coefficients") {
        obj.insert(
            "category_coefficients".to_string(),
            serde_json::json!({
                "standart": { "dealer": 1.28, "client": 2.13 },
                "antimoshka": { "dealer": 1.28, "client": 2.13 },
                "antikoshka": { "dealer": 1.28, "client": 2.13 },
                "ultravyu": { "dealer": 1.28, "client": 2.13 },
                "antipyl": { "dealer": 1.28, "client": 2.13 },
                "vstavnaya": { "dealer": 1.28, "client": 2.13 }
            }),
        );
    }

    let base_margin = payload.margin_percent.unwrap_or_else(|| {
        obj.get("base_margin_percent")
            .and_then(|v| v.as_f64())
            .unwrap_or(30.0)
    });
    obj.insert(
        "base_margin_percent".to_string(),
        serde_json::json!(base_margin),
    );
    obj.insert(
        "urgent_margin_percent".to_string(),
        serde_json::json!(payload.urgent_margin_percent),
    );
    obj.insert(
        "delivery_margin_percent".to_string(),
        serde_json::json!(payload.delivery_margin_percent),
    );
    obj.insert(
        "installation_margin_percent".to_string(),
        serde_json::json!(payload.installation_margin_percent),
    );
    obj.insert(
        "measurement_margin_percent".to_string(),
        serde_json::json!(payload.measurement_margin_percent),
    );

    margin
}

fn normalize_domain(domain: Option<String>) -> Option<String> {
    domain
        .map(|d| {
            let cleaned = d
                .trim()
                .trim_start_matches("http://")
                .trim_start_matches("https://")
                .trim_start_matches("www.")
                .split('/')
                .next()
                .unwrap_or("")
                .split(':')
                .next()
                .unwrap_or("")
                .to_lowercase();
            idna::domain_to_ascii(&cleaned).unwrap_or(cleaned)
        })
        .filter(|d| !d.is_empty())
}

pub async fn create_dealer(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<UpsertDealerRequest>,
) -> ApiResult<serde_json::Value> {
    let name = payload.name.trim().to_string();
    let city = payload.city.trim().to_string();
    let phone = payload.phone.trim().to_string();

    if name.is_empty() || city.is_empty() || phone.is_empty() {
        return Err(bad_request("Поля name, city и phone обязательны"));
    }

    let margin_config = build_margin_config(&payload);
    let domain = normalize_domain(payload.domain);
    let delivery_mode = payload
        .delivery_mode
        .unwrap_or_else(|| "self_pickup".to_string());
    let payment_type = payload
        .payment_type
        .unwrap_or_else(|| "postpaid".to_string());
    let role = payload.role.clone().unwrap_or_else(|| "dealer".to_string());
    let balance = payload.balance.unwrap_or(Decimal::ZERO);
    let credit_limit = payload.credit_limit.unwrap_or(Decimal::ZERO);
    let branding = payload.branding.unwrap_or_else(|| serde_json::json!({}));
    let contacts = payload.contacts.unwrap_or_else(|| {
        serde_json::json!({
            "phones": [],
            "emails": [],
            "additional_cities": [],
            "branches": []
        })
    });
    let legal_info = payload.legal_info.unwrap_or_else(|| serde_json::json!({}));
    let seo_config = payload.seo_config.unwrap_or_else(|| serde_json::json!({}));

    let dealer_id = sqlx::query_scalar::<_, Uuid>(
        r#"
        INSERT INTO dealers (
            name, city, phone, email, address, domain,
            margin_config,
            delivery_mode, payment_type, balance, credit_limit, role,
            branding, contacts, legal_info, seo_config
        )
        VALUES (
            $1, $2, $3, $4, $5, $6,
            $7,
            $8, $9, $10, $11, $12,
            $13, $14, $15, $16
        )
        RETURNING id
        "#,
    )
    .bind(name)
    .bind(city)
    .bind(phone)
    .bind(payload.email.filter(|v| !v.trim().is_empty()))
    .bind(payload.address.filter(|v| !v.trim().is_empty()))
    .bind(domain)
    .bind(margin_config)
    .bind(delivery_mode)
    .bind(payment_type)
    .bind(balance)
    .bind(credit_limit)
    .bind(role)
    .bind(branding)
    .bind(contacts)
    .bind(legal_info)
    .bind(seo_config)
    .fetch_one(&state.pool)
    .await
    .map_err(|e| {
        let msg = e.to_string();
        if msg.contains("dealers_domain_key") {
            bad_request("Домен уже занят другим дилером")
        } else {
            bad_request(&msg)
        }
    })?;

    ok(serde_json::json!({
        "status": "created",
        "dealer_id": dealer_id
    }))
}

pub async fn update_dealer(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
    Json(payload): Json<UpsertDealerRequest>,
) -> ApiResult<serde_json::Value> {
    let dealer_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;
    let name = payload.name.trim().to_string();
    let city = payload.city.trim().to_string();
    let phone = payload.phone.trim().to_string();

    if name.is_empty() || city.is_empty() || phone.is_empty() {
        return Err(bad_request("Поля name, city и phone обязательны"));
    }

    let margin_config = build_margin_config(&payload);
    let domain = normalize_domain(payload.domain);
    let delivery_mode = payload
        .delivery_mode
        .unwrap_or_else(|| "self_pickup".to_string());
    let payment_type = payload
        .payment_type
        .unwrap_or_else(|| "postpaid".to_string());
    let role = payload.role.clone().unwrap_or_else(|| "dealer".to_string());
    let balance = payload.balance.unwrap_or(Decimal::ZERO);
    let credit_limit = payload.credit_limit.unwrap_or(Decimal::ZERO);
    let branding = payload.branding.unwrap_or_else(|| serde_json::json!({}));
    let contacts = payload.contacts.unwrap_or_else(|| {
        serde_json::json!({
            "phones": [],
            "emails": [],
            "additional_cities": [],
            "branches": []
        })
    });
    let legal_info = payload.legal_info.unwrap_or_else(|| serde_json::json!({}));
    let seo_config = payload.seo_config.unwrap_or_else(|| serde_json::json!({}));

    let result = sqlx::query(
        r#"
        UPDATE dealers
        SET
            name = $1,
            city = $2,
            phone = $3,
            email = $4,
            address = $5,
            domain = $6,
            margin_config = $7,
            delivery_mode = $8,
            payment_type = $9,
            balance = $10,
            credit_limit = $11,
            role = $12,
            branding = $13,
            contacts = $14,
            legal_info = $15,
            seo_config = $16,
            updated_at = NOW()
        WHERE id = $17
        "#,
    )
    .bind(name)
    .bind(city)
    .bind(phone)
    .bind(payload.email.filter(|v| !v.trim().is_empty()))
    .bind(payload.address.filter(|v| !v.trim().is_empty()))
    .bind(domain)
    .bind(margin_config)
    .bind(delivery_mode)
    .bind(payment_type)
    .bind(balance)
    .bind(credit_limit)
    .bind(role)
    .bind(branding)
    .bind(contacts)
    .bind(legal_info)
    .bind(seo_config)
    .bind(dealer_id)
    .execute(&state.pool)
    .await
    .map_err(|e| {
        let msg = e.to_string();
        if msg.contains("dealers_domain_key") {
            bad_request("Домен уже занят другим дилером")
        } else {
            bad_request(&msg)
        }
    })?;

    if result.rows_affected() == 0 {
        return Err(bad_request("Dealer not found"));
    }

    ok(serde_json::json!({
        "status": "updated",
        "dealer_id": dealer_id
    }))
}

#[derive(Debug, Deserialize)]
pub struct UpdateBalanceRequest {
    pub amount: Decimal,
    pub description: Option<String>,
}

pub async fn update_dealer_balance(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
    Json(payload): Json<UpdateBalanceRequest>,
) -> ApiResult<serde_json::Value> {
    use sqlx::Row;

    if payload.amount <= Decimal::ZERO {
        return Err(bad_request("Сумма пополнения должна быть больше нуля"));
    }

    let dealer_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;
    let mut tx = state
        .pool
        .begin()
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    let row = sqlx::query("SELECT balance FROM dealers WHERE id = $1 FOR UPDATE")
        .bind(dealer_id)
        .fetch_optional(&mut *tx)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    let Some(row) = row else {
        return Err(bad_request("Dealer not found"));
    };

    let current_balance: Decimal = row.get("balance");
    let new_balance = current_balance + payload.amount;

    sqlx::query("UPDATE dealers SET balance = $1, updated_at = NOW() WHERE id = $2")
        .bind(new_balance)
        .bind(dealer_id)
        .execute(&mut *tx)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    sqlx::query(
        r#"
        INSERT INTO transactions (dealer_id, amount, balance_after, type, description)
        VALUES ($1, $2, $3, 'deposit', $4)
        "#,
    )
    .bind(dealer_id)
    .bind(payload.amount)
    .bind(new_balance)
    .bind(
        payload
            .description
            .unwrap_or_else(|| "Пополнение баланса из админки".to_string()),
    )
    .execute(&mut *tx)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    tx.commit().await.map_err(|e| bad_request(&e.to_string()))?;

    ok(serde_json::json!({
        "success": true,
        "dealer_id": dealer_id,
        "amount": payload.amount,
        "new_balance": new_balance
    }))
}

pub async fn list_dealer_transactions(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> ApiResult<serde_json::Value> {
    use sqlx::Row;

    let dealer_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;
    let rows = sqlx::query(
        r#"
        SELECT id, amount, balance_after, type, order_id, description, created_at
        FROM transactions
        WHERE dealer_id = $1
        ORDER BY created_at DESC
        LIMIT 200
        "#,
    )
    .bind(dealer_id)
    .fetch_all(&state.pool)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    let data: Vec<serde_json::Value> = rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "id": r.get::<Uuid, _>("id"),
                "amount": r.get::<Decimal, _>("amount"),
                "balance_after": r.get::<Decimal, _>("balance_after"),
                "type": r.get::<String, _>("type"),
                "order_id": r.get::<Option<Uuid>, _>("order_id"),
                "description": r.get::<Option<String>, _>("description"),
                "created_at": r.get::<DateTime<Utc>, _>("created_at"),
            })
        })
        .collect();

    ok(serde_json::json!(data))
}

pub async fn list_dealer_users(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> ApiResult<serde_json::Value> {
    use sqlx::Row;

    let dealer_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;
    let rows = sqlx::query(
        r#"
        SELECT id, name, email, role, is_active, created_at
        FROM users
        WHERE dealer_id = $1
        ORDER BY created_at DESC
        "#,
    )
    .bind(dealer_id)
    .fetch_all(&state.pool)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    let data: Vec<serde_json::Value> = rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "id": r.get::<Uuid, _>("id"),
                "name": r.get::<String, _>("name"),
                "email": r.get::<String, _>("email"),
                "role": r.get::<String, _>("role"),
                "is_active": r.get::<bool, _>("is_active"),
                "created_at": r.get::<DateTime<Utc>, _>("created_at"),
            })
        })
        .collect();

    ok(serde_json::json!(data))
}

pub async fn get_dealer_stats(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> ApiResult<serde_json::Value> {
    use sqlx::Row;

    let dealer_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;
    let row = sqlx::query(
        r#"
        SELECT
            COUNT(*)::bigint AS total_orders,
            COUNT(*) FILTER (WHERE status = 'new')::bigint AS new_orders,
            COUNT(*) FILTER (WHERE status = 'in_production')::bigint AS in_production_orders,
            COUNT(*) FILTER (WHERE status = 'completed')::bigint AS completed_orders,
            COALESCE(SUM(total_amount), 0) AS total_revenue,
            COALESCE(SUM(dealer_profit), 0) AS total_profit
        FROM orders
        WHERE dealer_id = $1
        "#,
    )
    .bind(dealer_id)
    .fetch_one(&state.pool)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    ok(serde_json::json!({
        "total_orders": row.get::<i64, _>("total_orders"),
        "new_orders": row.get::<i64, _>("new_orders"),
        "in_production_orders": row.get::<i64, _>("in_production_orders"),
        "completed_orders": row.get::<i64, _>("completed_orders"),
        "total_revenue": row.get::<Decimal, _>("total_revenue"),
        "total_profit": row.get::<Decimal, _>("total_profit"),
    }))
}

pub async fn get_dealer_stats_by_branch(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> ApiResult<serde_json::Value> {
    use sqlx::Row;

    let dealer_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;
    let rows = sqlx::query(
        r#"
        SELECT
            COALESCE(branch_id::text, 'no_branch') AS branch_id,
            COUNT(*)::bigint AS orders_count,
            COALESCE(SUM(total_amount), 0) AS total_revenue,
            COALESCE(SUM(dealer_profit), 0) AS total_profit
        FROM orders
        WHERE dealer_id = $1
        GROUP BY branch_id
        ORDER BY orders_count DESC
        "#,
    )
    .bind(dealer_id)
    .fetch_all(&state.pool)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    let data: Vec<serde_json::Value> = rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "branch_id": r.get::<String, _>("branch_id"),
                "orders_count": r.get::<i64, _>("orders_count"),
                "total_revenue": r.get::<Decimal, _>("total_revenue"),
                "total_profit": r.get::<Decimal, _>("total_profit"),
            })
        })
        .collect();

    ok(serde_json::json!(data))
}

#[derive(Debug, Deserialize)]
pub struct ChartQuery {
    pub days: Option<i64>,
}

pub async fn get_dealer_chart_stats(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
    Query(query): Query<ChartQuery>,
) -> ApiResult<serde_json::Value> {
    use sqlx::Row;

    let dealer_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;
    let days = query.days.unwrap_or(14).clamp(1, 90);

    let rows = sqlx::query(
        r#"
        SELECT
            DATE(created_at) AS day,
            COALESCE(SUM(total_amount), 0) AS sales
        FROM orders
        WHERE dealer_id = $1
          AND created_at >= NOW() - ($2::text || ' days')::interval
        GROUP BY day
        ORDER BY day ASC
        "#,
    )
    .bind(dealer_id)
    .bind(days)
    .fetch_all(&state.pool)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    let labels: Vec<String> = rows
        .iter()
        .map(|r| {
            let day: chrono::NaiveDate = r.get("day");
            day.format("%d.%m").to_string()
        })
        .collect();
    let sales: Vec<Decimal> = rows.iter().map(|r| r.get::<Decimal, _>("sales")).collect();

    ok(serde_json::json!({
        "labels": labels,
        "sales": sales,
    }))
}

#[derive(Debug, Deserialize)]
pub struct CreateDepartmentRequest {
    pub name: String,
    pub markup_config: Option<serde_json::Value>,
}

pub async fn create_department(
    State(state): State<Arc<AppState>>,
    Path(dealer_id): Path<String>,
    Json(payload): Json<CreateDepartmentRequest>,
) -> ApiResult<serde_json::Value> {
    let dealer_uuid = Uuid::parse_str(&dealer_id).map_err(|_| bad_request("Invalid UUID"))?;
    let name = payload.name.trim();
    if name.is_empty() {
        return Err(bad_request("Название отдела обязательно"));
    }

    let id = sqlx::query_scalar::<_, Uuid>(
        r#"
        INSERT INTO dealer_departments (dealer_id, name, markup_config, is_active)
        VALUES ($1, $2, $3, true)
        RETURNING id
        "#,
    )
    .bind(dealer_uuid)
    .bind(name)
    .bind(
        payload
            .markup_config
            .unwrap_or_else(|| serde_json::json!({})),
    )
    .fetch_one(&state.pool)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    ok(serde_json::json!({ "id": id, "dealer_id": dealer_uuid, "name": name }))
}

pub async fn list_departments(
    State(state): State<Arc<AppState>>,
    Path(dealer_id): Path<String>,
) -> ApiResult<serde_json::Value> {
    use sqlx::Row;

    let dealer_uuid = Uuid::parse_str(&dealer_id).map_err(|_| bad_request("Invalid UUID"))?;
    let rows = sqlx::query(
        r#"
        SELECT id, dealer_id, name, markup_config, is_active, created_at, updated_at
        FROM dealer_departments
        WHERE dealer_id = $1
        ORDER BY created_at DESC
        "#,
    )
    .bind(dealer_uuid)
    .fetch_all(&state.pool)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    let data: Vec<serde_json::Value> = rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "id": r.get::<Uuid, _>("id"),
                "dealer_id": r.get::<Uuid, _>("dealer_id"),
                "name": r.get::<String, _>("name"),
                "markup_config": r.get::<serde_json::Value, _>("markup_config"),
                "is_active": r.get::<bool, _>("is_active"),
                "created_at": r.get::<DateTime<Utc>, _>("created_at"),
                "updated_at": r.get::<DateTime<Utc>, _>("updated_at"),
            })
        })
        .collect();

    ok(serde_json::json!(data))
}

pub async fn list_audit_logs(
    State(state): State<Arc<AppState>>,
    Path(dealer_id): Path<String>,
) -> ApiResult<serde_json::Value> {
    use sqlx::Row;

    let dealer_uuid = Uuid::parse_str(&dealer_id).map_err(|_| bad_request("Invalid UUID"))?;
    let rows = sqlx::query(
        r#"
        SELECT id, user_id, dealer_id, action, entity_type, entity_id, old_data, new_data, ip_address, created_at
        FROM audit_logs
        WHERE dealer_id = $1
        ORDER BY created_at DESC
        LIMIT 200
        "#,
    )
    .bind(dealer_uuid)
    .fetch_all(&state.pool)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    let data: Vec<serde_json::Value> = rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "id": r.get::<Uuid, _>("id"),
                "user_id": r.get::<Option<Uuid>, _>("user_id"),
                "dealer_id": r.get::<Option<Uuid>, _>("dealer_id"),
                "action": r.get::<String, _>("action"),
                "entity_type": r.get::<String, _>("entity_type"),
                "entity_id": r.get::<Option<Uuid>, _>("entity_id"),
                "old_data": r.get::<Option<serde_json::Value>, _>("old_data"),
                "new_data": r.get::<Option<serde_json::Value>, _>("new_data"),
                "ip_address": r.get::<Option<String>, _>("ip_address"),
                "created_at": r.get::<DateTime<Utc>, _>("created_at"),
            })
        })
        .collect();

    ok(serde_json::json!(data))
}
pub async fn upload_file(
    State(_state): State<Arc<AppState>>,
    mut multipart: Multipart,
) -> ApiResult<serde_json::Value> {
    let mut saved_url: Option<String> = None;
    let upload_dir = std::path::Path::new("uploads");
    tokio::fs::create_dir_all(upload_dir)
        .await
        .map_err(|e| bad_request(&format!("Не удалось создать директорию uploads: {e}")))?;

    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|e| bad_request(&e.to_string()))?
    {
        let original_name = field.file_name().unwrap_or("file.bin").to_string();
        let data = field
            .bytes()
            .await
            .map_err(|e| bad_request(&e.to_string()))?;

        if data.is_empty() {
            continue;
        }

        // Ограничиваем размер загружаемого файла до 10MB.
        if data.len() > 10 * 1024 * 1024 {
            return Err(bad_request("Файл слишком большой (максимум 10MB)"));
        }

        let ext = original_name
            .rsplit('.')
            .next()
            .map(|e| e.to_lowercase())
            .filter(|e| matches!(e.as_str(), "png" | "jpg" | "jpeg" | "webp" | "gif" | "svg"))
            .unwrap_or_else(|| "png".to_string());

        let file_name = format!("{}.{}", Uuid::new_v4(), ext);
        let file_path = upload_dir.join(&file_name);

        tokio::fs::write(&file_path, &data)
            .await
            .map_err(|e| bad_request(&format!("Ошибка сохранения файла: {e}")))?;

        saved_url = Some(format!("/uploads/{file_name}"));
        break;
    }

    match saved_url {
        Some(url) => ok(serde_json::json!({ "url": url })),
        None => Err(bad_request("Файл не передан")),
    }
}
pub async fn get_production_orders(
    State(state): State<Arc<AppState>>,
) -> ApiResult<serde_json::Value> {
    use sqlx::Row;

    let rows = sqlx::query(
        r#"
        SELECT
            id,
            order_number,
            client_name,
            created_at,
            status,
            production_sub_status
        FROM orders
        WHERE status IN ('confirmed', 'in_production')
        ORDER BY created_at DESC
        LIMIT 200
        "#,
    )
    .fetch_all(&state.pool)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    let data: Vec<serde_json::Value> = rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "id": r.get::<Uuid, _>("id"),
                "order_number": r.get::<Option<String>, _>("order_number"),
                "client_name": r.get::<Option<String>, _>("client_name"),
                "created_at": r.get::<DateTime<Utc>, _>("created_at"),
                "status": r.get::<String, _>("status"),
                "production_sub_status": r.get::<Option<String>, _>("production_sub_status"),
                "items": serde_json::json!([]),
            })
        })
        .collect();

    ok(serde_json::json!(data))
}
pub async fn activate_dealer_domain(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> ApiResult<serde_json::Value> {
    use sqlx::Row;

    let dealer_id = Uuid::parse_str(&id).map_err(|_| bad_request("Invalid UUID"))?;
    let row = sqlx::query("SELECT domain FROM dealers WHERE id = $1")
        .bind(dealer_id)
        .fetch_optional(&state.pool)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    let Some(row) = row else {
        return Err(bad_request("Dealer not found"));
    };

    let current_domain: Option<String> = row.get("domain");
    let domain = normalize_domain(current_domain)
        .ok_or_else(|| bad_request("У дилера не заполнен домен"))?;
    let www_domain = format!("www.{domain}");

    let mut tx = state
        .pool
        .begin()
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    sqlx::query("UPDATE dealers SET domain = $1, updated_at = NOW() WHERE id = $2")
        .bind(&domain)
        .bind(dealer_id)
        .execute(&mut *tx)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    sqlx::query("UPDATE dealer_domains SET is_primary = false WHERE dealer_id = $1")
        .bind(dealer_id)
        .execute(&mut *tx)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    sqlx::query(
        r#"
        INSERT INTO dealer_domains (dealer_id, domain, is_primary, ssl_enabled)
        VALUES ($1, $2, true, true)
        ON CONFLICT (domain)
        DO UPDATE SET
            dealer_id = EXCLUDED.dealer_id,
            is_primary = true,
            ssl_enabled = true
        "#,
    )
    .bind(dealer_id)
    .bind(&domain)
    .execute(&mut *tx)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    sqlx::query(
        r#"
        INSERT INTO dealer_domains (dealer_id, domain, is_primary, ssl_enabled)
        VALUES ($1, $2, false, true)
        ON CONFLICT (domain)
        DO UPDATE SET
            dealer_id = EXCLUDED.dealer_id,
            ssl_enabled = true
        "#,
    )
    .bind(dealer_id)
    .bind(&www_domain)
    .execute(&mut *tx)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    tx.commit().await.map_err(|e| bad_request(&e.to_string()))?;

    // Применяем домен в Nginx Proxy Manager (создаем/обновляем proxy host).
    let npm_client = NpmClient::new();
    let proxy_host_id = npm_client
        .create_proxy_host(&domain)
        .await
        .map_err(|e| bad_request(&format!("Ошибка активации в NPM: {e}")))?;

    ok(serde_json::json!({
        "success": true,
        "message": format!("Домен {} активирован", domain),
        "domain": domain,
        "proxy_host_id": proxy_host_id
    }))
}
