// handlers/pricing.rs - Управление ценами

use crate::AppState;
use crate::handlers::{ApiResult, bad_request, ok};
use axum::{Json, extract::State};
use moskit_core::entity::{GlobalPricing, MarkupCategoryCoefficient, MarkupConfig, PricingItem};
use moskit_core::repository::{PostgresSettingsRepository, SettingsRepository};
use rust_decimal_macros::dec;
use std::sync::Arc;

fn default_markup_category_coefficients()
-> std::collections::HashMap<String, MarkupCategoryCoefficient> {
    [
        (
            "standart",
            MarkupCategoryCoefficient {
                dealer: dec!(1.28),
                client: dec!(2.13),
            },
        ),
        (
            "antimoshka",
            MarkupCategoryCoefficient {
                dealer: dec!(1.28),
                client: dec!(2.13),
            },
        ),
        (
            "antikoshka",
            MarkupCategoryCoefficient {
                dealer: dec!(1.28),
                client: dec!(2.13),
            },
        ),
        (
            "ultravyu",
            MarkupCategoryCoefficient {
                dealer: dec!(1.28),
                client: dec!(2.13),
            },
        ),
        (
            "antipyl",
            MarkupCategoryCoefficient {
                dealer: dec!(1.28),
                client: dec!(2.13),
            },
        ),
        (
            "vstavnaya",
            MarkupCategoryCoefficient {
                dealer: dec!(1.28),
                client: dec!(2.13),
            },
        ),
    ]
    .into_iter()
    .map(|(k, v)| (k.to_string(), v))
    .collect()
}

fn enrich_markup_with_defaults(mut pricing: GlobalPricing) -> Result<GlobalPricing, String> {
    if pricing.markup.category_coefficients.is_empty() {
        pricing.markup.category_coefficients = default_markup_category_coefficients();
    }
    Ok(pricing)
}

pub async fn get_global_pricing_internal(
    repo: &PostgresSettingsRepository,
) -> Result<GlobalPricing, String> {
    let value = repo
        .get_value("global_pricing")
        .await
        .map_err(|e| e.to_string())?;

    if let Some(value) = value {
        let pricing: GlobalPricing = serde_json::from_value(value).map_err(|e| e.to_string())?;
        return enrich_markup_with_defaults(pricing);
    }

    // Fallback на дефолты если в БД пусто
    let mesh = vec![
        PricingItem {
            id: "standart".to_string(),
            name: "Стандарт".to_string(),
            price: dec!(63.0),
            unit: None,
        },
        PricingItem {
            id: "antimoshka".to_string(),
            name: "Антимошка".to_string(),
            price: dec!(265.0),
            unit: None,
        },
        PricingItem {
            id: "ultravyu".to_string(),
            name: "Ультравью".to_string(),
            price: dec!(295.0),
            unit: None,
        },
        PricingItem {
            id: "antikoshka".to_string(),
            name: "Антикошка".to_string(),
            price: dec!(414.0),
            unit: None,
        },
        PricingItem {
            id: "antipyl".to_string(),
            name: "Антипыль".to_string(),
            price: dec!(645.0),
            unit: None,
        },
    ];
    let profiles = vec![
        PricingItem {
            id: "white".to_string(),
            name: "Белый (Рамочная)".to_string(),
            price: dec!(60.0),
            unit: None,
        },
        PricingItem {
            id: "brown".to_string(),
            name: "Коричневый (Рамочная)".to_string(),
            price: dec!(64.8),
            unit: None,
        },
        PricingItem {
            id: "anthracite".to_string(),
            name: "Антрацит (Рамочная)".to_string(),
            price: dec!(70.0),
            unit: None,
        },
        PricingItem {
            id: "ral".to_string(),
            name: "RAL (Рамочная)".to_string(),
            price: dec!(60.0),
            unit: None,
        },
        PricingItem {
            id: "white_vsn".to_string(),
            name: "Белый (Вставная VSN)".to_string(),
            price: dec!(151.0),
            unit: None,
        },
        PricingItem {
            id: "brown_vsn".to_string(),
            name: "Коричневый (Вставная VSN)".to_string(),
            price: dec!(153.0),
            unit: None,
        },
        PricingItem {
            id: "anthracite_vsn".to_string(),
            name: "Антрацит (Вставная VSN)".to_string(),
            price: dec!(163.0),
            unit: None,
        },
        PricingItem {
            id: "ral_vsn".to_string(),
            name: "RAL (Вставная VSN)".to_string(),
            price: dec!(251.0),
            unit: None,
        },
        PricingItem {
            id: "impost_white".to_string(),
            name: "Поперечина (Белая)".to_string(),
            price: dec!(62.0),
            unit: None,
        },
        PricingItem {
            id: "impost_brown".to_string(),
            name: "Поперечина (Коричневая)".to_string(),
            price: dec!(67.2),
            unit: None,
        },
        PricingItem {
            id: "impost_anthracite".to_string(),
            name: "Поперечина (Антрацит)".to_string(),
            price: dec!(75.0),
            unit: None,
        },
        PricingItem {
            id: "ral_painting".to_string(),
            name: "Наценка покраски RAL (мп)".to_string(),
            price: dec!(100.0),
            unit: None,
        },
    ];
    let markup = MarkupConfig {
        dealer: dec!(1.43),
        client: dec!(2.13),
        category_coefficients: default_markup_category_coefficients(),
        manufacturing_base: dec!(50.0),
        manufacturing_percent: dec!(5.0),
        measurement_base: dec!(270.0),
        measurement_percent: dec!(5.0),
        measurement_profit_factor: dec!(5.0),
        urgent_profit_factor: dec!(10.0),
        installation_profit_factor: dec!(33.0),
        delivery_profit_factor: dec!(33.0),
    };

    let components = vec![
        PricingItem {
            id: "corner_white".to_string(),
            name: "Уголок (Белый)".to_string(),
            price: dec!(3.75),
            unit: None,
        },
        PricingItem {
            id: "corner_brown".to_string(),
            name: "Уголок (Коричневый)".to_string(),
            price: dec!(6.0),
            unit: None,
        },
        PricingItem {
            id: "corner_anthracite".to_string(),
            name: "Уголок (Антрацит)".to_string(),
            price: dec!(7.0),
            unit: None,
        },
        PricingItem {
            id: "corner_vsn_white".to_string(),
            name: "Уголок VSN (Белый)".to_string(),
            price: dec!(14.8),
            unit: None,
        },
        PricingItem {
            id: "corner_vsn_brown".to_string(),
            name: "Уголок VSN (Коричневый)".to_string(),
            price: dec!(4.85),
            unit: None,
        },
        PricingItem {
            id: "corner_vsn_anthracite".to_string(),
            name: "Уголок VSN (Антрацит)".to_string(),
            price: dec!(7.15),
            unit: None,
        },
        PricingItem {
            id: "handle_plastic".to_string(),
            name: "Ручка пластик (шт)".to_string(),
            price: dec!(2.2),
            unit: None,
        },
        PricingItem {
            id: "handle_metal".to_string(),
            name: "Ручка металл (шт)".to_string(),
            price: dec!(8.0),
            unit: None,
        },
        PricingItem {
            id: "mount_plastic".to_string(),
            name: "Крепления пластик (шт)".to_string(),
            price: dec!(40.0),
            unit: None,
        },
        PricingItem {
            id: "mount_metal".to_string(),
            name: "Крепления металл (шт)".to_string(),
            price: dec!(40.0),
            unit: None,
        },
        PricingItem {
            id: "mount_vsn".to_string(),
            name: "Крепление VSN (шт)".to_string(),
            price: dec!(30.0),
            unit: None,
        },
        PricingItem {
            id: "mount_impost".to_string(),
            name: "Крепление импоста (шт)".to_string(),
            price: dec!(1.8),
            unit: None,
        },
        PricingItem {
            id: "screw".to_string(),
            name: "Саморез (шт)".to_string(),
            price: dec!(1.0),
            unit: None,
        },
        PricingItem {
            id: "rivet".to_string(),
            name: "Клепка (шт)".to_string(),
            price: dec!(5.0),
            unit: None,
        },
        PricingItem {
            id: "washer".to_string(),
            name: "Шайба (шт)".to_string(),
            price: dec!(2.0),
            unit: None,
        },
        PricingItem {
            id: "cord".to_string(),
            name: "Шнур (мп)".to_string(),
            price: dec!(4.6),
            unit: None,
        },
        PricingItem {
            id: "stretch".to_string(),
            name: "Стретч-пленка (упаковка)".to_string(),
            price: dec!(24.0),
            unit: None,
        },
    ];

    let services = vec![
        PricingItem {
            id: "installation".to_string(),
            name: "Монтаж (рамочная)".to_string(),
            price: dec!(300.0),
            unit: None,
        },
        PricingItem {
            id: "installation_vsn".to_string(),
            name: "Монтаж (вставная VSN)".to_string(),
            price: dec!(100.0),
            unit: None,
        },
        PricingItem {
            id: "installation_plisse".to_string(),
            name: "Монтаж (плиссе)".to_string(),
            price: dec!(500.0),
            unit: None,
        },
        PricingItem {
            id: "delivery".to_string(),
            name: "Доставка".to_string(),
            price: dec!(300.0),
            unit: None,
        },
        PricingItem {
            id: "delivery_mixed".to_string(),
            name: "Доставка (смежная)".to_string(),
            price: dec!(100.0),
            unit: None,
        },
    ];

    Ok(GlobalPricing {
        mesh,
        profiles,
        components,
        services,
        markup,
    })
}

pub async fn get_global_pricing(State(state): State<Arc<AppState>>) -> ApiResult<GlobalPricing> {
    tracing::info!("GET /api/v1/admin/pricing called");
    let repo = PostgresSettingsRepository::new(state.pool.clone());
    let pricing = get_global_pricing_internal(&repo)
        .await
        .map_err(|e| bad_request(&e))?;
    ok(pricing)
}

pub async fn update_global_pricing(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<GlobalPricing>,
) -> ApiResult<GlobalPricing> {
    tracing::info!("Updating global pricing: {:?}", payload);
    let repo = PostgresSettingsRepository::new(state.pool.clone());

    let value = serde_json::to_value(&payload).map_err(|e| bad_request(&e.to_string()))?;
    repo.set_value("global_pricing", value)
        .await
        .map_err(|e| bad_request(&e.to_string()))?;

    ok(payload)
}
