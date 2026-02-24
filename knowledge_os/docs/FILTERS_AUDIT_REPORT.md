# АУДИТ ФИЛЬТРОВ: BTC-ТРЕНД, НОВОСТИ/АНОМАЛИИ, КИТЫ

## 📊 Анализ систем фильтрации сигналов

### Основные компоненты:

#### 1. **BTC Тренд фильтр:**

- **`get_btc_trend_status(df_btc, use_soft_filter=True)`** - Получение статуса тренда BTC
- **`btc_trend_filter(df_btc)`** - Строгий фильтр (цена > EMA200 И EMA25 растёт)
- **`btc_trend_filter_soft(df_btc)`** - Мягкий фильтр (цена > EMA200)

#### 2. **Фильтры новостей:**

- **`get_coingecko_news(symbol)`** - Новости с CoinGecko
- **`get_tradingview_news(symbol)`** - Новости с TradingView
- **`get_coindesk_news(symbol)`** - Новости с CoinDesk
- **`get_cryptoslate_news(symbol)`** - Новости с Cryptoslate
- **`get_bitcoincom_news(symbol)`** - Новости с Bitcoin.com
- **`get_cointelegraph_news(symbol)`** - Новости с Cointelegraph

#### 3. **Фильтры аномалий:**

- **`get_anomaly_indicator(symbol)`** - Расчет индикатора аномалий
- **`calculate_anomaly_based_volume()`** - Корректировка объема на основе аномалий
- **`calculate_anomaly_based_risk()`** - Корректировка риска на основе аномалий

#### 4. **Фильтры китов:**

- **`WhaleSignalIntegrator`** - Интеграция данных о китах
- **Бесплатная система** (`FreeWhaleSignalIntegrator`)
- **Платная система** (`WhaleSignalIntegrator`)

### 🔧 Анализ фильтров:

#### **BTC Тренд фильтр:**

```python
def btc_trend_filter(df_btc):
    """Строгий фильтр тренда биткоина: цена > EMA200 И EMA25 растёт"""
    df_btc = df_btc.copy()
    df_btc["ema200"] = ta.trend.EMAIndicator(df_btc["close"], window=200).ema_indicator()
    df_btc["ema25"] = ta.trend.EMAIndicator(df_btc["close"], window=25).ema_indicator()
    df_btc["trend"] = (df_btc["close"] > df_btc["ema200"]) & (df_btc["ema25"].diff() > 0)
    return df_btc["trend"]

def btc_trend_filter_soft(df_btc):
    """Мягкий фильтр тренда биткоина: только цена > EMA200"""
    df_btc = df_btc.copy()
    df_btc["ema200"] = ta.trend.EMAIndicator(df_btc["close"], window=200).ema_indicator()
    df_btc["trend"] = df_btc["close"] > df_btc["ema200"]
    return df_btc["trend"]
```

- **Плюсы**: Простая и понятная логика
- **Минусы**: Длинное окно EMA200 (200 свечей) может быть запаздывающим

#### **Фильтры новостей:**

```python
# Много источников новостей:
- CoinGecko
- TradingView
- CoinDesk
- Cryptoslate
- Bitcoin.com
- Cointelegraph

# Кэширование с TTL 3600 сек (1 час)
NEWS_CACHE = {
    'blocked': {},      # {symbol: блокировка_до_utc}
    'positive': {},     # {symbol: пост_новости}
    'combined': {}      # {symbol: объединенные_новости}
}
```

- **Плюсы**: Множество источников, хорошее кэширование
- **Минусы**: Сложная логика объединения новостей

#### **Фильтры аномалий:**

```python
async def get_anomaly_indicator(symbol):
    """Получает индикатор 'Аномалия' для символа с кэшированием"""
    now_ts = _t.time()
    cached = ANOMALY_CACHE.get(symbol)
    if cached and now_ts - cached.get("ts", 0) < ANOMALY_TTL_SEC:
        return cached.get("data")

    # Получение данных с CoinGecko
    market_data = await get_coingecko_market_data(symbol)
    if not market_data:
        return ANOMALY_CACHE.get(symbol, {}).get("data")

    volume_24h = market_data["volume_24h"]
    market_cap = market_data["market_cap"]
    data = calculate_anomaly_indicator(volume_24h, market_cap)

    ANOMALY_CACHE[symbol] = {"ts": now_ts, "data": data}
    return data
```

- **Плюсы**: Кэширование с TTL 600 сек, использует реальные данные
- **Минусы**: Зависит от внешнего API CoinGecko

#### **Фильтры китов:**

```python
# Две системы:
1. Бесплатная: FreeWhaleSignalIntegrator
2. Платная: WhaleSignalIntegrator

# Интеграция в сообщениях:
whale_info = await whale_integrator.generate_whale_enhanced_message(symbol, enhanced_signal)
```

- **Плюсы**: Усиливает сигналы данными о крупных транзакциях
- **Минусы**: Дополнительная зависимость от внешних сервисов

### 🚨 Выявленные проблемы:

#### **Проблема 1: Дублирование кода в фильтрах новостей**

- 6 разных функций для получения новостей из разных источников
- Каждая имеет похожую структуру и обработку ошибок
- **Рекомендация**: Создать базовый класс `NewsProvider`

#### **Проблема 2: Сложная логика объединения новостей**

```python
# В get_combined_news:
for source_func in news_sources:
    try:
        news = await source_func(symbol)
        if news:
            all_news.extend(news)
    except Exception as e:
        print(f"[NewsFilter] Ошибка {source_func.__name__}: {e}")
        continue
```

- **Проблема**: Нет приоритизации источников, простое объединение

#### **Проблема 3: Зависимость от внешних API**

- **CoinGecko** для аномалий (может быть недоступен)
- **Различные новостные API** (могут иметь квоты/ограничения)
- **Китовые сервисы** (платные/бесплатные варианты)
- **Рекомендация**: Добавить fallback логику

#### **Проблема 4: Настройки фильтров размазаны**

```python
# В config.py:
RISK_FILTERS = {
    "min_volume_24h": 50_000_000,
    "max_spread_pct": 2.0,
    "min_price": 0.01,
    "max_price": 100_000,
    "max_volatility_pct": 15.0,
    "min_profit_pct": 0.5,
    "max_profit_pct": 5.0,
}

# В shared_utils.py:
ENHANCED_FILTERS = {
    "use_rsi_filter": False,
    "rsi_overbought": 75,
    "rsi_oversold": 25,
    "use_volume_filter": False,
    "volume_ratio_threshold": 1.1,
    "use_adx_filter": False,
    "adx_threshold": 22,
    "use_bb_squeeze_filter": False,
    "bb_squeeze_threshold": 0.85,
    "use_time_filter": False,
    "use_correlation_filter": False,
    "correlation_threshold": 0.8,
}
```

- **Проблема**: Настройки в разных файлах, нет единой системы конфигурации

#### **Проблема 5: Отсутствие метрик эффективности фильтров**

- Нет статистики о том, как часто фильтры срабатывают
- Нет данных о том, как фильтры влияют на качество сигналов
- **Рекомендация**: Добавить логирование и метрики

### 🔧 Рекомендации по улучшению:

#### **1. Рефакторинг фильтров новостей:**

```python
class NewsProvider:
    def __init__(self, name, priority=1):
        self.name = name
        self.priority = priority

    async def get_news(self, symbol):
        raise NotImplementedError

class CoinGeckoNewsProvider(NewsProvider):
    def __init__(self):
        super().__init__("CoinGecko", priority=1)

    async def get_news(self, symbol):
        # Реализация
        pass

class NewsFilterManager:
    def __init__(self):
        self.providers = [
            CoinGeckoNewsProvider(),
            TradingViewNewsProvider(),
            # ...
        ]

    async def get_combined_news(self, symbol):
        all_news = []
        for provider in sorted(self.providers, key=lambda x: x.priority):
            try:
                news = await provider.get_news(symbol)
                if news:
                    all_news.extend(news)
            except Exception as e:
                print(f"[NewsFilter] Ошибка {provider.name}: {e}")

        return self._deduplicate_news(all_news)
```

#### **2. Улучшенная система аномалий с fallback:**

```python
class AnomalyDetector:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 600

    async def get_anomaly_indicator(self, symbol):
        # 1. Проверяем кэш
        cached = self.cache.get(symbol)
        if cached and time.time() - cached.get("ts", 0) < self.cache_ttl:
            return cached.get("data")

        # 2. Пытаемся получить данные от CoinGecko
        try:
            market_data = await get_coingecko_market_data(symbol)
            if market_data:
                data = self.calculate_anomaly_indicator(market_data)
                self.cache[symbol] = {"ts": time.time(), "data": data}
                return data
        except Exception as e:
            print(f"[Anomaly] Ошибка CoinGecko: {e}")

        # 3. Fallback на кэшированные данные
        return cached.get("data") if cached else None

    async def get_anomaly_indicator_fallback(self, symbol):
        # Альтернативный расчет без внешних API
        # На основе технических индикаторов
        pass
```

#### **3. Централизованная конфигурация фильтров:**

```python
@dataclass
class FilterConfig:
    # BTC тренд
    use_btc_trend_filter: bool = True
    btc_trend_soft_filter: bool = True

    # Новостные фильтры
    news_filter_enabled: bool = True
    news_block_negative: bool = True
    news_enhance_positive: bool = True
    news_sources_priority: List[str] = field(default_factory=lambda: [
        "coingecko", "tradingview", "coindesk"
    ])

    # Аномалии
    anomaly_filter_enabled: bool = True
    anomaly_cache_ttl: int = 600

    # Киты
    whale_filter_enabled: bool = True
    whale_free_mode: bool = True

    # Риск фильтры
    min_volume_24h: float = 50_000_000
    max_spread_pct: float = 2.0
    min_price: float = 0.01
    max_price: float = 100_000

# Глобальная конфигурация
filter_config = FilterConfig()
```

#### **4. Система метрик для фильтров:**

```python
class FilterMetrics:
    def __init__(self):
        self.metrics = {
            'btc_trend': {'allowed': 0, 'blocked': 0},
            'news': {'positive': 0, 'negative': 0, 'neutral': 0},
            'anomaly': {'high': 0, 'medium': 0, 'low': 0},
            'whale': {'bullish': 0, 'bearish': 0, 'neutral': 0}
        }

    def log_filter_action(self, filter_type, action, details=None):
        if filter_type in self.metrics:
            if action in self.metrics[filter_type]:
                self.metrics[filter_type][action] += 1

        # Логирование в файл
        logging.info(f"[FilterMetrics] {filter_type}: {action} {details or ''}")

    def get_stats(self):
        return self.metrics.copy()
```

### 📋 План улучшений:

#### **Фаза 1: Консолидация и рефакторинг**

1. Создать базовые классы для провайдеров новостей
2. Централизовать конфигурацию фильтров
3. Упростить логику объединения новостей

#### **Фаза 2: Улучшение надежности**

1. Добавить fallback логику для аномалий
2. Улучшить обработку ошибок API
3. Добавить retry логику для внешних запросов

#### **Фаза 3: Мониторинг и метрики**

1. Добавить систему метрик для фильтров
2. Логировать эффективность каждого фильтра
3. Создать dashboard для анализа фильтров

#### **Фаза 4: Оптимизация**

1. Кэшировать результаты фильтров
2. Оптимизировать запросы к внешним API
3. Добавить асинхронную обработку

### 🎯 Приоритеты:

#### **Высокий приоритет:**

1. Создать базовые классы для провайдеров новостей
2. Централизовать конфигурацию фильтров
3. Добавить fallback логику для аномалий

#### **Средний приоритет:**

1. Упростить логику объединения новостей
2. Добавить систему метрик для фильтров
3. Улучшить обработку ошибок API

#### **Низкий приоритет:**

1. Оптимизировать кэширование фильтров
2. Добавить асинхронную обработку
3. Создать dashboard для анализа эффективности

---

_Аудит фильтров завершен. Система имеет хорошую функциональность, но требует рефакторинга для улучшения надежности и поддерживаемости._
