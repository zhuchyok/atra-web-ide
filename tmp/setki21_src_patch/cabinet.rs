// handlers/cabinet.rs - Обработчики для личного кабинета директора

use crate::AppState;
use crate::handlers::{ApiResult, bad_request, ok};
use axum::{
    Json,
    extract::{Path, State},
    routing::{delete, get, post, put},
};
use bcrypt::{DEFAULT_COST, hash};
use moskit_core::entity::{Dealer, DealerBranch, User, UserRole};
use moskit_core::repository::{
    DealerRepository, PostgresDealerRepository, PostgresUserRepository, UserRepository,
};
use rand::distributions::Alphanumeric;
use rand::{Rng, thread_rng};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Deserialize)]
pub struct CreateBranchRequest {
    pub name: String,
    pub domain: Option<String>,
    pub city: Option<String>,
    pub branch_multiplier: Option<f64>,
}

#[derive(Debug, Deserialize)]
pub struct UpdateBranchRequest {
    pub name: String,
    pub domain: Option<String>,
    pub city: Option<String>,
    pub branch_multiplier: Option<f64>,
    pub is_active: bool,
}

/// Список филиалов дилера
pub async fn list_branches(
    State(state): State<Arc<AppState>>,
    Path(dealer_id): Path<String>,
) -> ApiResult<Vec<DealerBranch>> {
    let d_id = Uuid::parse_str(&dealer_id).map_err(|_| bad_request("Invalid Dealer UUID"))?;
    let repo = PostgresDealerRepository::new(state.pool.clone());

    let branches = repo
        .find_branches_by_dealer(d_id)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;
    ok(branches)
}

/// Создание филиала
pub async fn create_branch(
    State(state): State<Arc<AppState>>,
    Path(dealer_id): Path<String>,
    Json(payload): Json<CreateBranchRequest>,
) -> ApiResult<DealerBranch> {
    let d_id = Uuid::parse_str(&dealer_id).map_err(|_| bad_request("Invalid Dealer UUID"))?;
    let repo = PostgresDealerRepository::new(state.pool.clone());

    let branch = DealerBranch {
        id: Uuid::new_v4(),
        dealer_id: d_id,
        name: payload.name,
        domain: payload.domain,
        city: payload.city,
        margin_config: serde_json::json!({
            "branch_multiplier": payload.branch_multiplier.unwrap_or(1.0)
        }),
        is_active: true,
        created_at: chrono::Utc::now(),
        updated_at: chrono::Utc::now(),
    };

    let created = repo
        .create_branch(branch)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;
    ok(created)
}

/// Обновление филиала
pub async fn update_branch(
    State(state): State<Arc<AppState>>,
    Path((_dealer_id, branch_id)): Path<(String, String)>,
    Json(payload): Json<UpdateBranchRequest>,
) -> ApiResult<DealerBranch> {
    let b_id = Uuid::parse_str(&branch_id).map_err(|_| bad_request("Invalid Branch UUID"))?;
    let repo = PostgresDealerRepository::new(state.pool.clone());

    // Сначала получаем текущий филиал
    // Нам нужен метод find_branch_by_id, но пока сделаем через SQL напрямую
    let mut branch =
        sqlx::query_as::<_, DealerBranch>("SELECT * FROM dealer_branches WHERE id = $1")
            .bind(b_id)
            .fetch_optional(&state.pool)
            .await
            .map_err(|e| bad_request(&e.to_string()))?
            .ok_or_else(|| bad_request("Branch not found"))?;

    branch.name = payload.name;
    branch.domain = payload.domain;
    branch.city = payload.city;
    branch.is_active = payload.is_active;
    branch.margin_config = serde_json::json!({
        "branch_multiplier": payload.branch_multiplier.unwrap_or(1.0)
    });

    let updated = repo
        .update_branch(branch)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;
    ok(updated)
}

/// Удаление филиала
pub async fn delete_branch(
    State(state): State<Arc<AppState>>,
    Path((_dealer_id, branch_id)): Path<(String, String)>,
) -> ApiResult<serde_json::Value> {
    let b_id = Uuid::parse_str(&branch_id).map_err(|_| bad_request("Invalid Branch UUID"))?;
    let repo = PostgresDealerRepository::new(state.pool.clone());

    repo.delete_branch(b_id)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;
    ok(serde_json::json!({"status": "success"}))
}

#[derive(Debug, Deserialize)]
pub struct CreateManagerRequest {
    pub name: String,
    pub email: String,
    pub phone: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct CreatedUserResponse {
    pub id: String,
    pub email: String,
    pub password: String,
}

/// Создание менеджера (сотрудника) дилера
pub async fn create_manager(
    State(state): State<Arc<AppState>>,
    Path(dealer_id): Path<String>,
    Json(payload): Json<CreateManagerRequest>,
) -> ApiResult<CreatedUserResponse> {
    let d_id = Uuid::parse_str(&dealer_id).map_err(|_| bad_request("Invalid Dealer UUID"))?;

    // Генерируем пароль
    let password: String = thread_rng()
        .sample_iter(&Alphanumeric)
        .take(10)
        .map(char::from)
        .collect();

    let password_hash = hash(&password, DEFAULT_COST).map_err(|e| bad_request(&e.to_string()))?;

    let mut user = User::new(
        payload.email.clone(),
        password_hash,
        payload.name,
        UserRole::Dealer, // Менеджеры дилера имеют ту же роль в системе, но привязаны к тому же dealer_id
    );
    user.dealer_id = Some(d_id);
    user.phone = payload.phone;

    let repo = PostgresUserRepository::new(state.pool.clone());
    let created = repo
        .create(user)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    ok(CreatedUserResponse {
        id: created.id.to_string(),
        email: created.email,
        password,
    })
}

/// Список всех пользователей дилера (директор + менеджеры)
pub async fn list_cabinet_users(
    State(state): State<Arc<AppState>>,
    Path(dealer_id): Path<String>,
) -> ApiResult<Vec<User>> {
    let d_id = Uuid::parse_str(&dealer_id).map_err(|_| bad_request("Invalid Dealer UUID"))?;
    let repo = PostgresUserRepository::new(state.pool.clone());

    let users = repo
        .list_by_dealer(d_id)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;
    ok(users)
}

#[derive(Debug, Deserialize)]
pub struct CreateSubDealerRequest {
    pub name: String,
    pub city: String,
    pub phone: String,
    pub email: String,
    pub margin_percent: Option<f64>,
}

/// Создание суб-дилера директором
pub async fn create_subdealer(
    State(state): State<Arc<AppState>>,
    Path(parent_id): Path<String>,
    Json(payload): Json<CreateSubDealerRequest>,
) -> ApiResult<CreatedUserResponse> {
    let p_id = Uuid::parse_str(&parent_id).map_err(|_| bad_request("Invalid Parent UUID"))?;

    let dealer_repo = PostgresDealerRepository::new(state.pool.clone());
    let user_repo = PostgresUserRepository::new(state.pool.clone());

    // 1. Создаем дилера с parent_id
    let dealer_id = Uuid::new_v4();
    let dealer = Dealer {
        id: dealer_id,
        parent_id: Some(p_id),
        role: "subdealer".to_string(),
        name: payload.name.clone(),
        city: payload.city,
        phone: payload.phone,
        email: Some(payload.email.clone()),
        address: None,
        domain: None,
        margin_config: moskit_core::entity::MarginConfig {
            base_margin_percent: payload.margin_percent.unwrap_or(30.0),
            city_multiplier: 1.0,
            branch_multiplier: 1.0,
            volume_discounts: vec![],
            category_margins: std::collections::HashMap::new(),
            category_coefficients: std::collections::HashMap::new(),
            urgent_margin_percent: None,
            delivery_margin_percent: None,
            installation_margin_percent: None,
            measurement_margin_percent: None,
            title_template: None,
            description_template: None,
            keywords: None,
        },
        delivery_mode: moskit_core::entity::DeliveryMode::SelfPickup,
        payment_type: moskit_core::entity::PaymentType::Postpaid,
        balance: rust_decimal_macros::dec!(0.0),
        credit_limit: rust_decimal_macros::dec!(0.0),
        branding: Default::default(),
        contacts: Default::default(),
        legal_info: Default::default(),
        seo_config: Default::default(),
        is_active: true,
        created_at: chrono::Utc::now(),
        updated_at: chrono::Utc::now(),
    };

    dealer_repo
        .create(dealer)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    // 2. Создаем пользователя для суб-дилера
    let password: String = thread_rng()
        .sample_iter(&Alphanumeric)
        .take(10)
        .map(char::from)
        .collect();

    let password_hash = hash(&password, DEFAULT_COST).map_err(|e| bad_request(&e.to_string()))?;

    let mut user = User::new(
        payload.email.clone(),
        password_hash,
        payload.name,
        UserRole::Dealer,
    );
    user.dealer_id = Some(dealer_id);

    user_repo
        .create(user)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    ok(CreatedUserResponse {
        id: dealer_id.to_string(),
        email: payload.email,
        password,
    })
}

/// Список суб-дилеров для директора
pub async fn list_subdealers(
    State(state): State<Arc<AppState>>,
    Path(parent_id): Path<String>,
) -> ApiResult<Vec<Dealer>> {
    let p_id = Uuid::parse_str(&parent_id).map_err(|_| bad_request("Invalid Parent UUID"))?;

    // Нам нужен метод в репозитории для поиска по parent_id
    // Пока сделаем через SQL напрямую здесь для скорости
    let dealers = sqlx::query_as::<_, Dealer>(
        r#"
        SELECT id, parent_id, role, name, city, phone, email, address, domain, margin_config,
               delivery_mode::text as delivery_mode, payment_type::text as payment_type,
               balance, credit_limit, branding, contacts, legal_info, seo_config, is_active, created_at, updated_at
        FROM dealers
        WHERE parent_id = $1
        ORDER BY created_at DESC
        "#
    )
    .bind(p_id)
    .fetch_all(&state.pool)
    .await
    .map_err(|e| bad_request(&e.to_string()))?;

    ok(dealers)
}
