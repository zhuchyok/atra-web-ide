# 📚 API Reference - ATRA Trading System

**Автор:** Мария (Technical Writer)  
**Ментор:** Виктор (Team Lead) + все эксперты  
**Дата:** November 23, 2025  
**Версия:** 1.0

---

## 📋 СОДЕРЖАНИЕ

1. [Core Modules](#core-modules)
2. [ML Modules](#ml-modules)
3. [Risk Management](#risk-management)
4. [Database](#database)
5. [Exchange Adapters](#exchange-adapters)
6. [Utilities](#utilities)

---

## 🔧 CORE MODULES

### `signal_live.py`

Основной модуль генерации торговых сигналов.

#### **Основные функции:**

```python
async def run_hybrid_signal_system_fixed():
    """
    Запускает гибридную систему генерации сигналов
    
    Returns:
        None
    """
```

```python
async def _generate_signal_impl(
    symbol: str,
    direction: str,
    regime_data: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Генерирует торговый сигнал для символа
    
    Args:
        symbol: Торговый символ (например, 'BTCUSDT')
        direction: Направление ('long' или 'short')
        regime_data: Данные о рыночном режиме
    
    Returns:
        Tuple[bool, Optional[str]]: (успех, сообщение об ошибке)
    """
```

#### **Фильтры:**

- `check_mtf_confirmation()` - Multi-timeframe подтверждение
- `check_ml_filter()` - ML фильтр сигналов
- `check_adx_filter()` - ADX фильтр силы тренда
- `check_time_filter()` - Временной фильтр
- `check_volume_filter()` - Фильтр объёма

---

### `lightgbm_predictor.py`

ML система для предсказания успешности сигналов.

#### **Класс: `LightGBMPredictor`**

```python
class LightGBMPredictor:
    """
    LightGBM система для предсказания успешности торговых сигналов
    
    Использует два подхода:
    1. Классификация - вероятность успеха (0-100%)
    2. Регрессия - размер прибыли в процентах
    """
    
    def __init__(
        self,
        patterns_file: str = "ai_learning_data/trading_patterns.json",
        model_dir: str = "ai_learning_data/lightgbm_models"
    ):
        """
        Args:
            patterns_file: Путь к файлу с паттернами
            model_dir: Директория для сохранения моделей
        """
    
    def predict(
        self,
        pattern: Dict[str, Any],
        min_win_probability: float = 0.40,
        min_expected_profit: float = 0.50
    ) -> Dict[str, Any]:
        """
        Предсказывает успешность сигнала
        
        Args:
            pattern: Словарь с данными паттерна
            min_win_probability: Минимальная вероятность успеха
            min_expected_profit: Минимальная ожидаемая прибыль
        
        Returns:
            Dict с предсказаниями:
            - success_probability: float (0-1)
            - expected_profit_pct: float
            - passed: bool
            - reason: str
        """
```

#### **Методы:**

- `load_patterns()` - Загружает паттерны из файла
- `prepare_features()` - Подготавливает features для обучения
- `train_models()` - Обучает модели
- `predict()` - Предсказывает успешность сигнала
- `save_models()` - Сохраняет модели
- `load_models()` - Загружает модели

---

## 💼 RISK MANAGEMENT

### `risk_manager.py`

Система управления рисками.

#### **Класс: `RiskManager`**

```python
class RiskManager:
    """
    Главный класс управления рисками
    
    Предоставляет:
    - Управление позициями
    - Расчет размера позиций
    - Мониторинг рисков
    - Корреляционный анализ
    """
    
    def __init__(self, risk_limits: RiskLimits = None):
        """
        Args:
            risk_limits: Лимиты риска (по умолчанию стандартные)
        """
```

#### **Класс: `PositionSizer`**

```python
class PositionSizer:
    """
    Калькулятор размера позиций
    
    Методы:
    - calculate_position_size() - Стандартный расчет
    - calculate_kelly_position_size() - Kelly Criterion
    - calculate_adaptive_risk() - Адаптивный риск
    """
    
    def calculate_position_size(
        self,
        balance: float,
        entry_price: float,
        stop_loss_price: float,
        risk_pct: float = None,
        max_position_pct: float = None,
        use_kelly: bool = False,
        win_rate: float = None,
        avg_win_loss_ratio: float = None
    ) -> Dict[str, float]:
        """
        Вычисляет размер позиции
        
        Args:
            balance: Текущий баланс
            entry_price: Цена входа
            stop_loss_price: Цена стоп-лосса
            risk_pct: Процент риска
            max_position_pct: Максимальный размер позиции
            use_kelly: Использовать Kelly Criterion
            win_rate: Вероятность выигрыша (для Kelly)
            avg_win_loss_ratio: Средний выигрыш/проигрыш (для Kelly)
        
        Returns:
            Dict с размером позиции и метриками
        """
    
    def calculate_kelly_position_size(
        self,
        balance: float,
        entry_price: float,
        stop_loss_price: float,
        win_rate: float = 0.5,
        avg_win_loss_ratio: float = 1.5,
        use_fractional: bool = True,
        kelly_fraction: float = 0.25
    ) -> Dict[str, float]:
        """
        Вычисляет размер позиции используя Kelly Criterion
        
        Формула: f = (p * b - q) / b
        
        Args:
            balance: Текущий баланс
            entry_price: Цена входа
            stop_loss_price: Цена стоп-лосса
            win_rate: Вероятность выигрыша (0.0 - 1.0)
            avg_win_loss_ratio: Средний выигрыш / Средний проигрыш
            use_fractional: Использовать Fractional Kelly
            kelly_fraction: Доля от полного Kelly (0.25 = Quarter Kelly)
        
        Returns:
            Dict с размером позиции и метриками Kelly
        """
```

#### **Dataclasses:**

```python
@dataclass
class Position:
    """Позиция в портфеле"""
    symbol: str
    side: str  # 'long' или 'short'
    quantity: float
    entry_price: float
    current_price: float
    leverage: float = 1.0
    risk_pct: float = 2.0
    margin_used: float = 0.0
    unrealized_pnl: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RiskLimits:
    """Лимиты риска"""
    max_position_size_pct: float = 10.0
    max_total_risk_pct: float = 20.0
    max_correlation: float = 0.7
    max_positions: int = 10
    max_drawdown_pct: float = 15.0
    margin_call_threshold: float = 0.8

@dataclass
class PortfolioMetrics:
    """Метрики портфеля"""
    total_balance: float
    used_margin: float
    free_margin: float
    total_risk: float
    total_pnl: float
    positions_count: int
    max_correlation: float
    portfolio_beta: float
    var_95: float
    sharpe_ratio: float
```

---

## 🗄️ DATABASE

### `db.py`

Класс для работы с базой данных.

#### **Класс: `Database`**

```python
class Database:
    """
    Класс для работы с базой данных сигналов и сделок
    
    Основные методы:
    - add_signal() - Добавить сигнал
    - get_active_signals() - Получить активные сигналы
    - update_signal() - Обновить сигнал
    - add_position() - Добавить позицию
    - get_positions() - Получить позиции
    """
    
    def __init__(self, db_path: str = "trading.db", use_connection_pool: bool = True):
        """
        Args:
            db_path: Путь к файлу БД
            use_connection_pool: Использовать connection pool
        """
```

#### **Основные методы:**

```python
def add_signal(
    self,
    user_id: int,
    symbol: str,
    direction: str,
    entry_price: float,
    tp1: float,
    tp2: float,
    sl: float,
    risk_pct: float,
    leverage: float = 1.0,
    quality_score: float = None,
    quality_meta: str = None
) -> int:
    """
    Добавляет торговый сигнал в БД
    
    Returns:
        ID созданного сигнала
    """

def get_active_signals(self, user_id: int = None) -> List[Dict]:
    """
    Получает активные сигналы
    
    Args:
        user_id: ID пользователя (опционально)
    
    Returns:
        List[Dict] активных сигналов
    """
```

---

### `db_connection_pool.py`

Connection pool для SQLite.

#### **Класс: `SQLiteConnectionPool`**

```python
class SQLiteConnectionPool:
    """
    Connection Pool для SQLite
    
    Переиспользует соединения вместо создания новых
    """
    
    @contextmanager
    def get_connection(self):
        """
        Context manager для получения соединения из пула
        
        Usage:
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")
        """
```

#### **Функция: `get_db_pool()`**

```python
def get_db_pool(db_path: str = None, max_connections: int = 5) -> SQLiteConnectionPool:
    """
    Получить глобальный connection pool
    
    Args:
        db_path: Путь к БД (требуется при первом вызове)
        max_connections: Максимальное количество соединений
    
    Returns:
        SQLiteConnectionPool instance
    """
```

---

## 📊 ML MODULES

### `purged_k_fold.py`

Purged K-Fold Cross-Validation для временных рядов.

#### **Класс: `PurgedKFold`**

```python
class PurgedKFold:
    """
    Purged K-Fold Cross-Validation для временных рядов
    
    Предотвращает data leakage через:
    - Purge period - удаляет данные между train и test
    - Embargo period - временной зазор
    """
    
    def __init__(
        self,
        n_splits: int = 5,
        purge_gap: int = 1,
        embargo_pct: float = 0.01
    ):
        """
        Args:
            n_splits: Количество фолдов
            purge_gap: Количество периодов для удаления
            embargo_pct: Процент данных для embargo
        """
    
    def split(
        self,
        X: pd.DataFrame,
        y: Optional[np.ndarray] = None,
        groups: Optional[np.ndarray] = None,
        timestamps: Optional[pd.Series] = None
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Генерирует индексы для train/test разделения с purge
        
        Returns:
            List of (train_indices, test_indices) tuples
        """
```

#### **Функция: `purged_train_test_split()`**

```python
def purged_train_test_split(
    X: pd.DataFrame,
    y: np.ndarray,
    test_size: float = 0.2,
    purge_gap: int = 1,
    embargo_pct: float = 0.01,
    timestamps: Optional[pd.Series] = None,
    random_state: Optional[int] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    """
    Purged train/test split для временных рядов
    
    Returns:
        X_train, X_test, y_train, y_test
    """
```

---

## 🔄 EXCHANGE ADAPTERS

### `exchange_adapter.py`

Адаптер для работы с биржами.

#### **Основные методы:**

```python
async def place_order(
    symbol: str,
    side: str,
    amount: float,
    price: float = None,
    order_type: str = "limit"
) -> Dict[str, Any]:
    """
    Размещает ордер на бирже
    
    Args:
        symbol: Торговый символ
        side: 'buy' или 'sell'
        amount: Количество
        price: Цена (для limit ордеров)
        order_type: Тип ордера ('limit' или 'market')
    
    Returns:
        Dict с информацией об ордере
    """

async def place_stop_loss_order(
    symbol: str,
    side: str,
    amount: float,
    stop_price: float
) -> Optional[Dict[str, Any]]:
    """
    Размещает стоп-лосс ордер
    
    Returns:
        Dict с информацией об ордере или None
    """

async def place_take_profit_order(
    symbol: str,
    side: str,
    amount: float,
    tp_price: float,
    tp_level: int = 1
) -> Optional[Dict[str, Any]]:
    """
    Размещает take-profit ордер
    
    Returns:
        Dict с информацией об ордере или None
    """
```

---

## 🛠️ UTILITIES

### `structured_logging.py`

Структурированное логирование.

#### **Функция: `configure_structured_logging()`**

```python
def configure_structured_logging(
    level: str = "INFO",
    json_format: bool = True
) -> logging.Logger:
    """
    Настраивает структурированное логирование
    
    Args:
        level: Уровень логирования
        json_format: Использовать JSON формат
    
    Returns:
        Настроенный logger
    """
```

---

### `prometheus_metrics.py`

Prometheus метрики.

#### **Функции:**

```python
def record_signal_generated(symbol: str, signal_type: str, pattern_type: str):
    """Записывает метрику генерации сигнала"""

def record_signal_accepted(symbol: str, signal_type: str):
    """Записывает метрику принятия сигнала"""

def record_signal_rejected(symbol: str, signal_type: str, reason: str):
    """Записывает метрику отклонения сигнала"""

def record_ml_prediction(
    symbol: str,
    signal_type: str,
    success_probability: float,
    expected_profit: float
):
    """Записывает метрику ML предсказания"""

def start_metrics_server(port: int = 8000):
    """Запускает HTTP сервер для Prometheus метрик"""
```

---

## 📝 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### Пример 1: Генерация сигнала

```python
from signal_live import _generate_signal_impl

# Генерируем сигнал
success, error = await _generate_signal_impl("BTCUSDT", "long")
if success:
    print("✅ Сигнал сгенерирован!")
else:
    print(f"❌ Ошибка: {error}")
```

### Пример 2: ML предсказание

```python
from lightgbm_predictor import LightGBMPredictor

predictor = LightGBMPredictor()
predictor.load_models()

pattern = {
    'rsi': 45.0,
    'macd': 0.5,
    'volume_ratio': 1.2,
    # ... другие features
}

prediction = predictor.predict(pattern, min_win_probability=0.40)
print(f"Вероятность успеха: {prediction['success_probability']:.2%}")
```

### Пример 3: Расчет размера позиции (Kelly Criterion)

```python
from risk_manager import PositionSizer

sizer = PositionSizer()

position_info = sizer.calculate_position_size(
    balance=10000.0,
    entry_price=50000.0,
    stop_loss_price=49000.0,
    use_kelly=True,
    win_rate=0.6,
    avg_win_loss_ratio=1.8
)

print(f"Размер позиции: {position_info['position_size']:.6f}")
print(f"Kelly fraction: {position_info['kelly_fraction']:.4f}")
```

### Пример 4: Purged K-Fold CV

```python
from purged_k_fold import purged_train_test_split
import pandas as pd
import numpy as np

X = pd.DataFrame({'feature1': range(100)})
y = np.array([0, 1] * 50)

X_train, X_test, y_train, y_test = purged_train_test_split(
    X, y,
    test_size=0.2,
    purge_gap=1,
    embargo_pct=0.01
)
```

---

## 🔗 СВЯЗАННЫЕ ДОКУМЕНТЫ

- [Architecture Documentation](./architecture.rst)
- [Testing Guide](../TESTING.md)
- [Deployment Guide](../README_DEPLOY.md)

---

**Статус:** ✅ API Reference готов  
**Обновление:** Ежемесячно  
**Автор:** Мария (Technical Writer)
