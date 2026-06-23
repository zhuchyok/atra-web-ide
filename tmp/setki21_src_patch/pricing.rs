// entity/pricing.rs - Ценообразование

use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CategoryCoefficient {
    pub dealer: f64,
    pub client: f64,
}

/// Конфигурация наценки дилера
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MarginConfig {
    /// Базовая наценка (напр. 30% = 1.30)
    pub base_margin_percent: f64,
    /// Коэффициент города (1.0 - столица, 0.8 - регион)
    pub city_multiplier: f64,
    /// Дополнительный коэффициент филиала/менеджера (напр. 1.05 = +5%)
    pub branch_multiplier: f64,
    /// Скидки за объём
    pub volume_discounts: Vec<VolumeDiscount>,
    /// Наценки по категориям
    pub category_margins: std::collections::HashMap<String, f64>,
    /// Коэффициенты по категориям (дилер/клиент)
    #[serde(default)]
    pub category_coefficients: std::collections::HashMap<String, CategoryCoefficient>,
    /// Наценка на срочность (%)
    pub urgent_margin_percent: Option<f64>,
    /// Наценка на доставку (%)
    pub delivery_margin_percent: Option<f64>,
    /// Наценка на монтаж (%)
    pub installation_margin_percent: Option<f64>,
    /// Наценка на замер (%)
    pub measurement_margin_percent: Option<f64>,
    /// Шаблон заголовка SEO
    pub title_template: Option<String>,
    /// Шаблон описания SEO
    pub description_template: Option<String>,
    /// Ключевые слова SEO
    pub keywords: Option<String>,
}

impl MarginConfig {
    /// Получить множитель наценки
    pub fn get_multiplier(&self) -> Decimal {
        let base =
            Decimal::from_f64_retain(1.0 + (self.base_margin_percent / 100.0)).unwrap_or(dec!(1.3));
        let city = Decimal::from_f64_retain(self.city_multiplier).unwrap_or(dec!(1.0));
        let branch = Decimal::from_f64_retain(self.branch_multiplier).unwrap_or(dec!(1.0));
        (base * city * branch).round_dp(4)
    }

    /// Получить множитель для услуги (срочность, доставка и т.д.)
    pub fn get_service_multiplier(&self, service_margin: Option<f64>) -> Decimal {
        let margin = service_margin.unwrap_or(0.0);
        Decimal::from_f64_retain(1.0 + (margin / 100.0)).unwrap_or(dec!(1.0))
    }
}

impl Default for MarginConfig {
    fn default() -> Self {
        Self {
            base_margin_percent: 30.0,
            city_multiplier: 1.0,
            branch_multiplier: 1.0,
            volume_discounts: Vec::new(),
            category_margins: std::collections::HashMap::new(),
            category_coefficients: std::collections::HashMap::new(),
            urgent_margin_percent: None,
            delivery_margin_percent: None,
            installation_margin_percent: None,
            measurement_margin_percent: None,
            title_template: None,
            description_template: None,
            keywords: None,
        }
    }
}

/// Скидка за объём
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VolumeDiscount {
    pub min_orders_per_month: u32,
    pub discount_percent: f64,
}

/// Элемент прайс-листа
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PricingItem {
    pub id: String,
    pub name: String,
    pub price: Decimal,
    #[serde(default)]
    pub unit: Option<String>,
}

/// Глобальная конфигурация цен
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GlobalPricing {
    pub mesh: Vec<PricingItem>,
    pub profiles: Vec<PricingItem>,
    pub components: Vec<PricingItem>,
    pub services: Vec<PricingItem>,
    pub markup: MarkupConfig,
}

/// Конфигурация наценок
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MarkupConfig {
    pub dealer: Decimal,
    pub client: Decimal,
    pub manufacturing_base: Decimal,
    pub manufacturing_percent: Decimal,
    pub measurement_base: Decimal,
    pub measurement_percent: Decimal,
    #[serde(default)]
    pub measurement_profit_factor: Decimal,
    #[serde(default)]
    pub urgent_profit_factor: Decimal,
    #[serde(default)]
    pub installation_profit_factor: Decimal,
    #[serde(default)]
    pub delivery_profit_factor: Decimal,
}

/// Результат расчёта цены для дилера
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DealerPrice {
    /// Себестоимость для дилера
    pub dealer_cost: Decimal,
    /// Рекомендованная цена
    pub suggested_price: Decimal,
    /// Цена которую выставил дилер
    pub actual_price: Decimal,
    /// Наценка дилера (%)
    pub margin_percent: Decimal,
    /// Прибыль дилера
    pub dealer_profit: Decimal,
}

/// Конфигурация цены товара
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PriceConfig {
    /// Базовая цена (себестоимость)
    pub base_price: Decimal,
    /// Цена для дилера (с наценкой производителя)
    pub dealer_price: Decimal,
    /// Минимальная цена для дилера
    pub min_dealer_price: Decimal,
    /// Наценка дилера по умолчанию (%)
    pub default_dealer_margin: Decimal,
}
