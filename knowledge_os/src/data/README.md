# Модуль данных ATRA

Централизованное управление данными из внешних источников с кэшированием, валидацией и техническим анализом.

## 🏗️ Архитектура

```
src/data/
├── __init__.py           # Экспорты всех компонентов
├── providers.py          # Провайдеры данных (CoinGecko, TradingView)
├── cache.py              # Расширенная система кэширования
├── validation.py         # Валидация данных
├── technical.py          # Технические индикаторы
└── README.md             # Эта документация
```

## 🔌 Провайдеры данных (providers.py)

### DataProvider

Абстрактный базовый класс для всех провайдеров данных.

**Возможности:**

- Rate limiting
- Retry стратегия с exponential backoff
- Обработка ошибок HTTP
- Автоматическое кэширование

### CoinGeckoProvider

Провайдер данных CoinGecko API.

**Методы:**

```python
# Получение списка монет
coin_list = coingecko.get_coin_list()

# Получение данных конкретной монеты
coin_data = coingecko.get_coin_data('bitcoin')

# Получение графика
chart_data = coingecko.get_market_chart('bitcoin', days=7)

# Получение трендов
trending = coingecko.get_trending_coins()
```

### TradingViewProvider

Провайдер данных TradingView для технического анализа.

**Методы:**

```python
# Получение технического анализа
ta_data = tradingview.get_technical_analysis('BTCUSDT')
```

## 💾 Система кэширования (cache.py)

### DataCache

Базовый класс для всех типов кэша с TTL.

**Возможности:**

- Автоматическое истечение TTL
- Статистика hit/miss/eviction
- Ограничение размера
- Метаданные кэшированных элементов

### Специализированные кэши

```python
from src.data import OHLCDataCache, NewsDataCache, AnomalyDataCache, WhaleDataCache

# OHLC данные
ohlc_cache = OHLCDataCache()
ohlc_cache.set('BTC', data, ttl=1800)  # 30 минут

# Новости
news_cache = NewsDataCache()
news_cache.set('BTC_news', news_data, ttl=3600)  # 1 час

# Аномалии
anomaly_cache = AnomalyDataCache()
anomaly_cache.set('BTC_anomaly', anomaly_data, ttl=600)  # 10 минут

# Данные о китах
whale_cache = WhaleDataCache()
whale_cache.set('BTC_whale', whale_data, ttl=1800)  # 30 минут
```

### Статистика кэша

```python
stats = ohlc_cache.get_stats()
print(f"Items: {stats['items_count']}")
print(f"Hit rate: {stats['hit_rate_percent']}%")
print(f"Memory usage: {stats['total_size_bytes']} bytes")
```

## 🔍 Валидация данных (validation.py)

### DataValidator

Базовый класс для всех валидаторов.

**Возможности:**

- Отслеживание ошибок и предупреждений
- Структурированные сообщения об ошибках
- Статистика валидации

### PriceValidator

Валидация ценовых данных.

```python
from src.data import PriceValidator

validator = PriceValidator()

test_data = {
    'symbol': 'BTC',
    'price': 45000.50,
    'volume': 1000000,
    'timestamp': '2024-01-01T12:00:00'
}

is_valid = validator.validate(test_data)
if not is_valid:
    errors = validator.get_errors()
    print("Validation errors:", errors)
```

### VolumeValidator

Валидация данных объемов.

### NewsValidator

Валидация новостных данных.

## 📊 Технические индикаторы (technical.py)

### TechnicalIndicators

Централизованный класс для расчета всех технических индикаторов.

```python
from src.data import technical_indicators

prices = [45000, 45100, 45200, 45300, 45250, 45150]

# Отдельные индикаторы
rsi = technical_indicators.calculate_rsi(prices)
bollinger = technical_indicators.calculate_bollinger_bands(prices)
trend = technical_indicators.calculate_trend_strength(prices)

# Все индикаторы сразу
ohlc_data = [
    {'close': p, 'volume': 1000000, 'high': p+100, 'low': p-100, 'open': p-50}
    for p in prices
]

all_indicators = technical_indicators.get_all_technical_indicators(ohlc_data)
```

### Доступные индикаторы

| Индикатор        | Описание                      | Параметры                 |
| ---------------- | ----------------------------- | ------------------------- |
| RSI              | Relative Strength Index       | period=14                 |
| Momentum         | Momentum                      | period=10                 |
| Volume Ratio     | Соотношение объема к среднему | -                         |
| Fear/Greed Index | Индекс страха/жадности        | -                         |
| Bollinger Bands  | Полосы Боллинджера            | period=20, std_dev=2.0    |
| Moving Averages  | Скользящие средние            | periods=[10,20,50,200]    |
| Trend Strength   | Сила тренда                   | sma_short=20, sma_long=50 |
| Volume Profile   | Профиль объема                | num_bins=10               |

## 🚀 Использование

### Базовое использование

```python
from src.data import (
    get_coingecko_data,
    get_tradingview_data,
    validate_price_data,
    calculate_rsi
)

# Получение данных
btc_data = get_coingecko_data('BTC')
btc_analysis = get_tradingview_data('BTCUSDT')

# Валидация
is_valid = validate_price_data(btc_data)

# Расчет индикаторов
prices = [item['close'] for item in btc_data.get('prices', [])]
rsi_value = calculate_rsi(prices)
```

### Продвинутое использование

```python
from src.data import (
    CoinGeckoProvider,
    OHLCDataCache,
    PriceValidator,
    technical_indicators
)

# Создание провайдера с кэшированием
provider = CoinGeckoProvider()
cache = OHLCDataCache()
validator = PriceValidator()

# Получение и валидация данных
data = provider.get_data('BTC')
if validator.validate(data):
    # Кэширование валидных данных
    cache.set('BTC_data', data)

    # Расчет всех технических индикаторов
    if 'ohlc' in data:
        indicators = technical_indicators.get_all_technical_indicators(data['ohlc'])
        print(f"Calculated {len(indicators)} indicators")
```

## ⚙️ Конфигурация

Настройки находятся в `src/core/config.py`:

```python
# Rate limits для API
API_RATE_LIMITS = {
    "coingecko": 50,      # запросов в минуту
    "tradingview": 30,
    "default": 10
}

# Настройки кэша
CACHE_SETTINGS = {
    "ohlc_max_size": 500,
    "news_max_size": 200,
    "anomaly_max_size": 300,
    "default_ttl": 300
}

# Валидация цен
PRICE_VALIDATION = {
    "min_price": 0.000001,
    "max_price": 1000000,
    "max_decimals": 18
}
```

## 📈 Мониторинг

### Статистика провайдеров

```python
provider_stats = coingecko.get_status()
print(f"Requests: {provider_stats['request_count']}")
print(f"Last request: {provider_stats['last_request']}")
```

### Статистика кэша

```python
cache_stats = ohlc_cache.get_stats()
print(f"Items: {cache_stats['items_count']}")
print(f"Hit rate: {cache_stats['hit_rate_percent']}%")
print(f"Memory: {cache_stats['total_size_bytes']} bytes")
```

### Статистика валидации

```python
validation_stats = validator.get_stats()
print(f"Errors: {validation_stats['error_count']}")
print(f"Warnings: {validation_stats['warning_count']}")
```

## 🧪 Тестирование

```bash
# Тестирование всех компонентов
python3 -c "
from src.data import *
print('Testing data system...')
# ... тестовый код
"
```

## 🔄 Интеграция с существующим кодом

Новая система данных обратно совместима с существующим кодом:

```python
# Старый способ (все еще работает)
from signal_live import get_coingecko_data, calculate_rsi

# Новый способ (рекомендуется)
from src.data import get_coingecko_data, calculate_rsi
```

## 📋 Зависимости

- requests >= 2.25.0
- urllib3 >= 1.26.0
- statistics (built-in)
- datetime (built-in)
- json (built-in)
- hashlib (built-in)

## 🚨 Обработка ошибок

Все компоненты системы данных включают комплексную обработку ошибок:

- **Network errors**: Автоматические retry с backoff
- **API errors**: Graceful degradation
- **Validation errors**: Подробные сообщения об ошибках
- **Cache errors**: Fallback на fresh data

## 📊 Производительность

- **Кэширование**: TTL-based с автоматической очисткой
- **Rate limiting**: Предотвращение превышения лимитов API
- **Memory management**: Ограничение размера кэша
- **Async ready**: Архитектура готова для асинхронности

---

_Модуль данных ATRA v1.0_
_Централизованное управление данными с 2024 г._
