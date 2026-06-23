// entity/order.rs - Сущность заказа

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::{FromRow, Type};
use uuid::Uuid;

/// Статус заказа
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Type)]
#[sqlx(type_name = "TEXT")]
pub enum OrderStatus {
    New,            // Новый (ожидает подтверждения)
    Confirmed,      // Подтверждён
    InProduction,   // В производстве
    Ready,          // Готов к выдаче/монтажу
    InInstallation, // На монтаже
    Completed,      // Выполнен
    Cancelled,      // Отменён
}

impl OrderStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            OrderStatus::New => "new",
            OrderStatus::Confirmed => "confirmed",
            OrderStatus::InProduction => "in_production",
            OrderStatus::Ready => "ready",
            OrderStatus::InInstallation => "in_installation",
            OrderStatus::Completed => "completed",
            OrderStatus::Cancelled => "cancelled",
        }
    }
}

/// Подстатус производства
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Type)]
#[sqlx(type_name = "TEXT")]
pub enum ProductionSubStatus {
    Pending,      // В очереди
    Cutting,      // Раскрой
    Welding,      // Сварка
    Assembly,     // Сборка
    QualityCheck, // Контроль качества
    Packaging,    // Упаковка
}

impl ProductionSubStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Pending => "pending",
            Self::Cutting => "cutting",
            Self::Welding => "welding",
            Self::Assembly => "assembly",
            Self::QualityCheck => "quality_check",
            Self::Packaging => "packaging",
        }
    }
    pub fn from_str(s: &str) -> Option<Self> {
        let s = s.to_lowercase();
        match s.as_str() {
            "pending" => Some(Self::Pending),
            "cutting" => Some(Self::Cutting),
            "welding" => Some(Self::Welding),
            "assembly" => Some(Self::Assembly),
            "quality_check" => Some(Self::QualityCheck),
            "packaging" => Some(Self::Packaging),
            _ => None,
        }
    }
}

/// Статус монтажа
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Type)]
#[sqlx(type_name = "TEXT")]
pub enum InstallationStatus {
    Scheduled,  // Запланирован
    InProgress, // В процессе
    Completed,  // Завершён
    Cancelled,  // Отменён
}

use rust_decimal::Decimal;

/// Позиция заказа
#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct OrderItem {
    pub id: Uuid,
    pub product_id: Uuid,
    pub name: String,
    pub params: serde_json::Value, // Параметры (размеры, цвет, тип)
    pub quantity: i32,
    pub unit_price: Decimal,
    pub total_price: Decimal,
    pub dealer_cost: Decimal, // Себестоимость для дилера
}

/// Заказ
#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Order {
    pub id: Uuid,
    pub order_number: String,
    pub dealer_id: Option<Uuid>,
    pub branch_id: Option<Uuid>, // Филиал (сайт), с которого пришел заказ
    pub client_name: String,
    pub client_phone: String,
    pub client_address: Option<String>,
    #[sqlx(skip)]
    pub items: Vec<OrderItem>,
    pub status: OrderStatus,
    pub production_sub_status: Option<ProductionSubStatus>,
    pub installation_status: Option<InstallationStatus>,
    pub total_amount: Decimal,        // Итоговая сумма для клиента
    pub dealer_cost: Decimal,         // Себестоимость для дилера (закупка)
    pub dealer_profit: Decimal,       // Прибыль дилера (total_amount - dealer_cost - доп. расходы)
    pub dealer_price_total: Decimal,  // "Замороженная" цена дилера в момент заказа
    pub selling_price_total: Decimal, // "Замороженная" цена продажи в момент заказа
    pub potential_profit: Decimal,    // (Selling - Dealer - Service)
    pub department_id: Option<Uuid>,
    pub installation_price: Option<Decimal>,
    pub delivery_price: Option<Decimal>,
    pub measurement_price: Option<Decimal>,
    pub comment: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

impl Order {
    pub fn new(
        dealer_id: Option<Uuid>,
        client_name: String,
        client_phone: String,
        items: Vec<OrderItem>,
    ) -> Self {
        let now = Utc::now();
        let total_amount: Decimal = items.iter().map(|i| i.total_price).sum();

        Self {
            id: Uuid::new_v4(),
            order_number: format!(
                "MS-{}-{}",
                chrono::Utc::now().format("%Y%m%d%H%M%S%3f"),
                &Uuid::new_v4().simple().to_string()[..6]
            ),
            dealer_id,
            branch_id: None,
            client_name,
            client_phone,
            client_address: None,
            items,
            status: OrderStatus::New,
            production_sub_status: None,
            installation_status: None,
            total_amount,
            dealer_cost: Decimal::ZERO,
            dealer_profit: Decimal::ZERO,
            dealer_price_total: Decimal::ZERO,
            selling_price_total: Decimal::ZERO,
            potential_profit: Decimal::ZERO,
            department_id: None,
            installation_price: None,
            delivery_price: None,
            measurement_price: None,
            comment: None,
            created_at: now,
            updated_at: now,
        }
    }

    /// Проверка возможности перехода в новый статус
    pub fn can_transition_to(&self, new_status: OrderStatus) -> bool {
        match (self.status, new_status) {
            (OrderStatus::New, OrderStatus::Confirmed) => true,
            (OrderStatus::New, OrderStatus::Cancelled) => true,
            (OrderStatus::Confirmed, OrderStatus::InProduction) => true,
            (OrderStatus::Confirmed, OrderStatus::Cancelled) => true,
            (OrderStatus::InProduction, OrderStatus::Ready) => true,
            (OrderStatus::Ready, OrderStatus::InInstallation) => true,
            (OrderStatus::Ready, OrderStatus::Completed) => true,
            (OrderStatus::InInstallation, OrderStatus::Completed) => true,
            (_, OrderStatus::Cancelled) => self.status != OrderStatus::Completed,
            _ => false,
        }
    }
}
