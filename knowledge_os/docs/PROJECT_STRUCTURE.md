# 📁 СТРУКТУРА ПРОЕКТА ATRA

**Версия:** 2.0  
**Дата обновления:** 2025-11-19  
**Статус:** Production Ready

---

## 📋 ОГЛАВЛЕНИЕ

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Структура директорий](#структура-директорий)
3. [Основные модули](#основные-модули)
4. [Компоненты системы](#компоненты-системы)
5. [Потоки данных](#потоки-данных)
6. [Конфигурация](#конфигурация)
7. [База данных](#база-данных)
8. [Развертывание](#развертывание)

---

## 🏗️ ОБЗОР АРХИТЕКТУРЫ

ATRA (Algorithmic Trading Robot Assistant) — это комплексная система алгоритмической торговли для криптовалютного рынка, построенная на принципах модульной архитектуры.

### Основные принципы:

- **Модульность**: Четкое разделение ответственности между компонентами
- **Асинхронность**: Использование asyncio для неблокирующих операций
- **Масштабируемость**: Поддержка множественных пользователей и символов
- **Надежность**: Система fallback для критических компонентов
- **Мониторинг**: Встроенная система observability и метрик

### Архитектурные слои:

```
┌─────────────────────────────────────────┐
│     Пользовательский интерфейс          │
│  (Telegram Bot, Web Dashboard, REST API)│
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│     Бизнес-логика                       │
│  (Signal Generation, Risk Management)   │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│     Слой данных                         │
│  (Exchange API, Database, Cache)        │
└─────────────────────────────────────────┘
```

---

## 📂 СТРУКТУРА ДИРЕКТОРИЙ

```
atra/
├── 📁 src/                          # Основной исходный код
│   ├── 📁 signals/                  # Генерация и обработка сигналов
│   ├── 📁 filters/                  # Фильтры сигналов
│   ├── 📁 analysis/                 # Анализ рынка
│   ├── 📁 strategies/               # Торговые стратегии
│   ├── 📁 indicators/               # Технические индикаторы
│   ├── 📁 patterns/                 # Паттерны свечей
│   ├── 📁 market/                   # Анализ рынка
│   ├── 📁 technical/                # Технический анализ
│   ├── 📁 metrics/                 # Метрики и статистика
│   ├── 📁 optimization/             # Оптимизация параметров
│   ├── 📁 data/                     # Провайдеры данных
│   ├── 📁 core/                     # Ядро системы
│   ├── 📁 telegram/                 # Telegram интеграция
│   └── 📁 utils/                    # Утилиты
│
├── 📁 scripts/                      # Вспомогательные скрипты
│   ├── 📁 backtest_*.py             # Бэктестинг
│   ├── 📁 monitor_*.py              # Мониторинг
│   ├── 📁 optimize_*.py             # Оптимизация
│   ├── 📁 fix_*.py                  # Исправления
│   └── 📁 deploy_*.sh               # Развертывание
│
├── 📁 observability/                # Система observability
│   ├── agent_coordinator.py         # Координация агентов
│   ├── tracing.py                   # Трассировка
│   ├── metrics.py                    # Метрики
│   ├── feedback.py                   # Обратная связь
│   └── evolution_engine.py          # Эволюция системы
│
├── 📁 monitoring/                   # Мониторинг инфраструктуры
│   └── infra_metrics.py             # Метрики инфраструктуры
│
├── 📁 agent_gym/                    # Оффлайн симуляции и тестирование агентов
│   ├── scenarios.py                 # Сценарии тестирования (SignalThroughput, ExecutionFallback)
│   ├── configs/                     # Конфигурации сценариев (JSON)
│   ├── reports/                     # Отчеты о результатах симуляций
│   └── __init__.py
│
├── 📁 risk_monitor/                 # Мониторинг рисков
│   ├── calculations.py              # Расчеты рисков
│   ├── metrics.py                    # Метрики рисков
│   └── telegram.py                   # Уведомления
│
├── 📁 data/                         # Данные и кэш
│   ├── historical_data_loader.py    # Загрузка исторических данных
│   └── 📁 cache/                    # Кэш данных
│
├── 📁 backtests/                    # Результаты бэктестов
│   └── *.json                       # JSON отчеты
│
├── 📁 logs/                         # Логи системы
│   └── *.log                        # Файлы логов
│
├── 📁 docs/                         # Документация
│   ├── PROJECT_STRUCTURE.md         # Этот файл
│   └── *.md                         # Другая документация
│
├── 📁 archive/                      # Архивные файлы
│   └── experimental/                # Экспериментальные модули
│
├── 📁 infrastructure/               # Инфраструктура
│   ├── docker/                      # Docker конфигурации
│   ├── terraform/                   # Terraform конфигурации
│   └── kubernetes/                  # Kubernetes манифесты
│
├── 📁 tests/                        # Тесты
│   ├── unit/                        # Юнит-тесты
│   ├── integration/                 # Интеграционные тесты
│   └── performance/                 # Тесты производительности
│
├── 📄 main.py                       # Точка входа
├── 📄 config.py                     # Конфигурация
├── 📄 signal_live.py                # Генерация сигналов
├── 📄 telegram_handlers.py          # Обработчики Telegram
├── 📄 auto_execution.py             # Автоматическое исполнение
├── 📄 exchange_api.py               # API биржи
├── 📄 db.py                         # База данных
└── 📄 requirements.txt              # Зависимости
```

---

## 🔧 ОСНОВНЫЕ МОДУЛИ

### 1. **main.py** — Точка входа системы

**Назначение:** Инициализация и запуск всех компонентов системы

**Основные функции:**

- Инициализация базы данных
- Запуск Telegram бота
- Запуск системы генерации сигналов
- Запуск системы оптимизации
- Запуск мониторинга
- Обработка graceful shutdown

**Ключевые компоненты:**

```python
- run_hybrid_signal_system_fixed()    # Генерация сигналов
- run_telegram_bot_in_existing_loop() # Telegram бот
- run_optimization_system()           # Оптимизация
- run_ai_learning_system()            # AI обучение
- run_rest_api_async()                # REST API
```

**Детальная структура:**

**Инициализация:**

```python
# Проверка зависимостей
check_critical_dependencies()

# Инициализация БД
initialize_database_on_startup()
sync_user_data_from_json_to_db()

# Инициализация системных интеграций
initialize_system_integrations()
initialize_system_settings()

# Инициализация фильтра рыночной капитализации
initialize_market_cap_filtering()
```

**Запуск компонентов:**

```python
# Основной event loop
loop = asyncio.get_event_loop()

# Параллельный запуск всех систем
tasks = [
    run_telegram_bot_in_existing_loop(),      # Telegram бот
    run_hybrid_signal_system_fixed(),          # Генерация сигналов
    run_optimization_system(),                  # Оптимизация
    run_ai_learning_system(),                  # AI обучение
    run_rest_api_async(),                      # REST API (если доступен)
    _sync_positions_periodically(),            # Синхронизация позиций
    run_price_monitoring(),                    # Мониторинг цен
]

# Graceful shutdown
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
```

**Параметры запуска:**

- `--backtest`: Запуск бэктеста
- `--dca-backtest`: Бэктест DCA стратегии
- `--env`: Указание окружения (dev/prod)

**Логирование:**

- Ротация логов через `RotatingFileHandler`
- Уровни: INFO, WARNING, ERROR
- Файлы: `main.log`, `bot.log`, `atra.log`

**Обработка ошибок:**

- Try-except блоки для каждого компонента
- Graceful degradation при сбоях
- Автоматический перезапуск критических компонентов

---

### 2. **signal_live.py** — Генерация сигналов

**Назначение:** Основной модуль генерации торговых сигналов

**Основные функции:**

- Получение рыночных данных (OHLCV)
- Расчет технических индикаторов
- Применение фильтров
- Генерация сигналов (LONG/SHORT)
- Отправка сигналов в Telegram
- Сохранение в базу данных

**Ключевые классы и функции:**

```python
- _generate_signal_impl()            # Генерация сигнала
- send_signal()                       # Отправка сигнала
- process_symbol_signals()            # Обработка символов
- run_hybrid_signal_system_fixed()   # Основной цикл
```

**Детальная структура:**

**Получение данных:**

```python
async def get_symbol_data(symbol: str, force_fresh: bool = False):
    """
    Получение OHLCV данных с fallback механизмом

    Источники (в порядке приоритета):
    1. Binance API
    2. Bybit API
    3. OKX API
    4. Кэш (если доступен)

    Параметры:
    - symbol: Торговый символ (например, "BTCUSDT")
    - force_fresh: Принудительное обновление (игнорировать кэш)

    Возвращает:
    - DataFrame с колонками: timestamp, open, high, low, close, volume
    """
```

**Расчет индикаторов:**

```python
def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Добавляет технические индикаторы к DataFrame

    Индикаторы:
    - RSI (14 периодов)
    - MACD (12, 26, 9)
    - EMA Fast (12) / EMA Slow (26)
    - Bollinger Bands (20, 2.0)
    - ATR (14)
    - ADX (14)
    - Volume Profile

    Возвращает:
    - DataFrame с добавленными колонками индикаторов
    """
```

**Генерация сигналов:**

```python
async def _generate_signal_impl(
    symbol: str,
    df: pd.DataFrame,
    user_data: Dict[str, Any],
    regime_data: Dict[str, Any] = None
) -> tuple:
    """
    Генерация торгового сигнала

    Паттерны:
    1. Классический EMA кроссовер
       - LONG: EMA Fast > EMA Slow (бычий)
       - SHORT: EMA Fast < EMA Slow (медвежий)

    2. Pullback Entry
       - Откат к EMA после пробоя
       - Подтверждение объемом

    3. Zone-based
       - Вход в зоне поддержки/сопротивления
       - Фибоначчи уровни

    Фильтры (последовательно):
    1. BTC/ETH/SOL Trend Filter
    2. Volume Imbalance Filter
    3. False Breakout Detector
    4. RSI Warning Filter
    5. ML Filter Optimizer

    Возвращает:
    - (signal_data, None) если сигнал сгенерирован
    - (None, reason) если сигнал заблокирован
    """
```

**Отправка сигнала:**

```python
async def send_signal(
    symbol: str,
    signal_type: str,  # "LONG" или "SHORT"
    signal_price: float,
    user_data: Dict[str, Any],
    ...
) -> bool:
    """
    Отправка сигнала пользователю

    Процесс:
    1. Проверка корреляционных рисков
    2. Проверка портфельных рисков
    3. Формирование сообщения
    4. Отправка в Telegram (оба бота: DEV и PROD)
    5. Сохранение в БД (signals_log, accepted_signals)
    6. Автоисполнение (если включено и PROD режим)

    Возвращает:
    - True если сигнал успешно отправлен
    - False если отправка не удалась
    """
```

**Основной цикл:**

```python
async def run_hybrid_signal_system_fixed():
    """
    Основной цикл генерации сигналов

    Интервал: ~30-60 секунд (зависит от количества символов)

    Процесс:
    1. Загрузка пользователей из БД
    2. Получение списка символов (AUTO_FETCH_COINS или COINS)
    3. Для каждого символа:
       a. Получение данных
       b. Расчет индикаторов
       c. Генерация сигнала
       d. Применение фильтров
       e. Отправка (если прошел)
    4. Логирование статистики

    Статистика:
    - Обработано символов
    - Отправлено сигналов
    - Заблокировано фильтрами
    """
```

**Фильтры:**

- **BTC/ETH/SOL Trend Filter**: Проверка тренда основных монет
- **Volume Imbalance Filter**: Анализ объемов с ML оптимизацией
- **False Breakout Detector**: Детекция ложных пробоев
- **RSI Filter**: Предупреждения при экстремальных значениях RSI
- **ML Filter Optimizer**: Адаптивная оптимизация параметров фильтров

---

### 3. **telegram_handlers.py** — Обработчики Telegram

**Назначение:** Обработка команд и сообщений от пользователей

**Основные функции:**

- Обработка команд (`/start`, `/help`, `/positions`, etc.)
- Принятие сигналов (`/accept`)
- Управление позициями
- Отправка уведомлений
- Обработка кнопок

**Ключевые функции:**

```python
- notify_user()                      # Отправка сообщений
- handle_message()                  # Обработка сообщений
- button_callback()                  # Обработка кнопок
- start_accept_button_ttl()         # TTL для кнопок
```

**Детальная структура:**

**Команды бота:**

```python
/start          # Начало работы, регистрация пользователя
/help           # Справка по командам
/positions      # Список активных позиций
/trade_history  # История сделок
/balance        # Текущий баланс
/settings       # Настройки пользователя
/accept         # Принятие сигнала вручную
```

**Обработка кнопок:**

```python
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка нажатий на кнопки

    Формат callback_data:
    - accept|SYMBOL|TIMESTAMP|PRICE|QUANTITY|DIRECTION|RISK|LEVERAGE
    - close|POSITION_ID|PARTIAL|AMOUNT
    - dca|SYMBOL|TIMESTAMP|PRICE|QUANTITY

    Процесс:
    1. Парсинг callback_data
    2. Валидация параметров
    3. Проверка TTL (время жизни кнопки)
    4. Выполнение действия
    5. Обновление сообщения
    6. Удаление кнопки после использования
    """
```

**Отправка сообщений:**

```python
async def notify_user(user_id, text, **kwargs):
    """
    Отправка сообщения пользователю

    Параметры:
    - user_id: ID пользователя в Telegram
    - text: Текст сообщения (HTML формат)
    - _timeout: Таймаут отправки (по умолчанию 5 сек)
    - _return_message: Вернуть message_id (для обновления)
    - _send_to_both_bots: Отправить в оба бота (DEV и PROD)
    - reply_markup: Клавиатура с кнопками

    Особенности:
    - Rate limiting (1 сек между сообщениями)
    - Retry логика при ошибках
    - Обработка Flood Control
    - Автоматическое форматирование HTML

    Возвращает:
    - True/False при успехе/ошибке
    - Dict с message_id при _return_message=True
    """
```

**TTL для кнопок:**

```python
async def start_accept_button_ttl(chat_id, message_id, expiry_iso, callback_data):
    """
    Установка времени жизни для кнопки принятия сигнала

    Параметры:
    - expiry_iso: Время истечения (ISO формат)
    - callback_data: Данные кнопки

    Процесс:
    1. Создание задачи с таймером
    2. Ожидание до времени истечения
    3. Обновление сообщения (удаление кнопки)
    4. Логирование события

    По умолчанию: 5 минут
    """
```

**Обработка принятия сигнала:**

```python
async def handle_accept_signal(user_id, signal_data):
    """
    Обработка принятия сигнала пользователем

    Процесс:
    1. Валидация сигнала (проверка времени, цены)
    2. Проверка баланса пользователя
    3. Расчет размера позиции
    4. Открытие позиции на бирже (если ручной режим)
    5. Сохранение в БД (accepted_signals)
    6. Обновление статуса в signals_log
    7. Уведомление пользователя

    Режимы:
    - Manual: Пользователь сам открывает позицию
    - Auto: Позиция открывается автоматически (PROD)
    """
```

---

### 4. **auto_execution.py** — Автоматическое исполнение

**Назначение:** Автоматическое открытие позиций на бирже

**Основные функции:**

- Открытие позиций по сигналам
- Установка Stop Loss и Take Profit
- Управление размером позиции
- Синхронизация с биржей

**Ключевые классы:**

```python
class AutoExecutionService:
    - execute_and_open()             # Открытие позиции
    - place_stop_loss_order()        # Установка SL
    - place_take_profit_order()      # Установка TP
```

**Детальная структура:**

**Критические проверки:**

```python
async def execute_and_open(...):
    """
    Автоматическое открытие позиции

    КРИТИЧЕСКИЕ ПРОВЕРКИ:
    1. ATRA_ENV == "prod" (только в продакшене!)
       - DEV/TEST окружения НИКОГДА не открывают позиции
       - Блокировка с логированием ошибки

    2. Валидация размера позиции
       - Минимальный размер: 0.0001
       - Максимальный размер: баланс * leverage
       - Проверка через PositionSizeValidator

    3. Авторизация агента
       - Проверка через observability.agent_identity
       - Логирование всех действий
    """
```

**Процесс открытия позиции:**

```python
# 1. Нормализация направления
direction = "BUY" if direction.upper() == "LONG" else "SELL"

# 2. Расчет количества
if trade_mode == 'futures' and leverage > 1:
    # Для futures: количество = (margin * leverage) / price
    amount = (quantity_usdt * leverage) / entry_price
else:
    # Для spot: количество = сумма / price
    amount = quantity_usdt / entry_price

# 3. Открытие позиции
order_result = await adapter.place_order(
    symbol=symbol,
    side=direction,
    amount=amount,
    order_type='market'  # или 'limit'
)

# 4. Установка SL
if sl_price:
    await place_stop_loss_order(
        symbol, direction, amount, sl_price
    )

# 5. Установка TP1/TP2
if tp1_price:
    await place_take_profit_order(
        symbol, direction, amount, tp1_price, tp_type='TP1'
    )
if tp2_price:
    await place_take_profit_order(
        symbol, direction, amount, tp2_price, tp_type='TP2'
    )

# 6. Сохранение в БД
await acceptance_db.create_active_position(...)
await acceptance_db.update_signal_status(...)
```

**Установка Stop Loss:**

```python
async def place_stop_loss_order(symbol, direction, amount, sl_price):
    """
    Установка Stop Loss ордера

    Логика:
    - LONG: SL ниже цены входа
    - SHORT: SL выше цены входа

    Тип ордера:
    - Stop Market (Bitget)
    - Stop Limit (Binance)

    Обработка ошибок:
    - Retry при временных ошибках
    - Логирование в order_audit_log
    - Fallback на ручную установку
    """
```

**Установка Take Profit:**

```python
async def place_take_profit_order(symbol, direction, amount, tp_price, tp_type='TP1'):
    """
    Установка Take Profit ордера

    Параметры:
    - tp_type: 'TP1' или 'TP2'

    Логика:
    - LONG: TP выше цены входа
    - SHORT: TP ниже цены входа

    Частичное закрытие:
    - TP1: 50% позиции
    - TP2: 50% позиции (остаток)
    """
```

**Аудит и логирование:**

```python
# Все операции логируются в order_audit_log
await audit_log.log_order(
    order_type='market',
    symbol=symbol,
    side=direction,
    amount=amount,
    price=entry_price,
    status='filled',
    user_id=user_id
)
```

---

### 5. **exchange_api.py** — API биржи

**Назначение:** Интеграция с криптовалютными биржами

**Поддерживаемые биржи:**

- Binance
- Bybit
- OKX
- Bitget

**Основные функции:**

```python
- get_klines()                       # Получение свечей
- get_current_price()                # Текущая цена
- get_filtered_top_usdt_pairs_fast() # Топ пары
- place_order()                      # Размещение ордера
```

**Детальная структура:**

**Fallback механизм:**

```python
async def get_klines(symbol, timeframe='1h', limit=300):
    """
    Получение свечей с автоматическим fallback

    Порядок попыток:
    1. Binance API (приоритет)
    2. Bybit API (fallback)
    3. OKX API (fallback)
    4. Кэш (если доступен)

    Обработка ошибок:
    - Rate limiting: автоматическое ожидание
    - Network errors: retry с экспоненциальной задержкой
    - Invalid symbol: пропуск символа

    Возвращает:
    - DataFrame с колонками: timestamp, open, high, low, close, volume
    - None при ошибке всех источников
    """
```

**Получение топ пар:**

```python
async def get_filtered_top_usdt_pairs_fast(top_n=500, final_limit=200):
    """
    Получение топ торговых пар с фильтрацией

    Фильтры:
    1. Только USDT пары
    2. Минимальный объем 24h (например, $1M)
    3. Минимальная ликвидность
    4. Исключение стейблкоинов
    5. Исключение blacklist

    Параметры:
    - top_n: Количество пар для анализа (500)
    - final_limit: Финальный список (200)

    Возвращает:
    - List[str] символов (например, ['BTCUSDT', 'ETHUSDT', ...])
    """
```

**Получение текущей цены:**

```python
async def get_current_price_robust(symbol):
    """
    Надежное получение текущей цены

    Источники:
    1. Exchange API (real-time)
    2. Ticker cache (если доступен)
    3. Последняя свеча (fallback)

    Кэширование:
    - TTL: 5 секунд
    - Обновление в фоне

    Возвращает:
    - float: текущая цена
    - None при ошибке
    """
```

**Rate Limiting:**

```python
class RateLimiter:
    """
    Управление лимитами API запросов

    Лимиты по биржам:
    - Binance: 1200 requests/min (weighted)
    - Bybit: 120 requests/min
    - OKX: 20 requests/2sec

    Реализация:
    - Token bucket алгоритм
    - Автоматическое ожидание при превышении
    - Логирование предупреждений
    """
```

**Exchange Adapter:**

```python
class ExchangeAdapter:
    """
    Адаптер для работы с биржами

    Поддерживаемые операции:
    - place_order()           # Размещение ордера
    - cancel_order()          # Отмена ордера
    - get_positions()         # Получение позиций
    - get_balance()           # Получение баланса
    - get_open_orders()       # Открытые ордера

    Абстракция:
    - Единый интерфейс для всех бирж
    - Автоматическая нормализация данных
    - Обработка различий в API
    """
```

---

### 6. **config.py** — Конфигурация

**Назначение:** Централизованное хранение всех настроек

**Основные разделы:**

- Фильтры (BTC/ETH/SOL trend, Volume, RSI)
- Риск-менеджмент (leverage, risk_pct)
- Telegram настройки
- База данных
- API ключи
- ML настройки

**Ключевые константы:**

```python
- COINS                              # Список монет
- DEFAULT_RISK_PCT                   # Риск по умолчанию
- DEFAULT_LEVERAGE                   # Плечо по умолчанию
- TELEGRAM_TOKEN                     # Токен бота
- VOLUME_IMBALANCE_FILTER_CONFIG     # Настройки фильтров
```

---

## 🧩 КОМПОНЕНТЫ СИСТЕМЫ

### 📊 Система генерации сигналов

```
signal_live.py
├── Получение данных
│   ├── get_symbol_data()
│   └── get_ohlc_with_fallback()
├── Расчет индикаторов
│   ├── add_technical_indicators()
│   ├── RSI, MACD, EMA, Bollinger Bands
│   └── ATR, ADX, Volume Profile
├── Генерация сигналов
│   ├── _generate_signal_impl()
│   ├── Классические паттерны (EMA crossover)
│   ├── Pullback entry
│   └── Zone-based signals
├── Фильтрация
│   ├── Trend filters (BTC/ETH/SOL)
│   ├── Volume imbalance
│   ├── False breakout
│   ├── RSI warning
│   └── ML optimization
└── Отправка
    ├── send_signal()
    ├── notify_user_enhanced()
    └── Сохранение в БД
```

---

### 🔍 Система фильтров

**Расположение:** `src/filters/`

**Основные фильтры:**

1. **SmartTrendFilter** (`smart_trend_filter.py`)
   - Проверка тренда BTC/ETH/SOL
   - Multi-timeframe confirmation
   - Адаптивные пороги

   **Детали:**

   ```python
   class SmartTrendFilter:
       """
       Умный фильтр тренда основных монет

       Логика:
       - Определяет релевантную монету (BTC/ETH/SOL) по корреляции
       - Проверяет тренд на 1h и 4h таймфреймах
       - Использует EMA (10/22 для soft, 12/26 для strict)
       - Блокирует сильные контр-тренды (>1% разница EMA)
       - Разрешает слабые тренды (<0.2% разница) для боковика

       Параметры:
       - BTC_TREND_EMA_SOFT = 50
       - BTC_TREND_EMA_STRICT = 200
       - BTC_TREND_USE_MULTITF = True

       Режимы:
       - Soft: Менее строгие требования
       - Strict: Строгие требования к тренду
       """
   ```

2. **VolumeImbalanceFilter** (`volume_imbalance.py`)
   - Анализ объемов
   - ML оптимизация порогов
   - Подтверждение направления

   **Детали:**

   ```python
   class VolumeImbalanceFilter:
       """
       Фильтр дисбаланса объемов

       Логика:
       - Сравнивает текущий объем с средним
       - Проверяет направление объема (buy/sell)
       - ML оптимизация порогов под рыночные условия

       Параметры (по умолчанию):
       - min_volume_ratio = 1.2 (объем должен быть на 20% выше среднего)
       - require_volume_confirmation = True

       ML оптимизация:
       - Адаптация порогов под волатильность
       - Учет рыночного режима (тренд/боковик)
       - Релаксация для интрадей торговли

       Возвращает:
       - FilterResult(passed=True) если объем подтверждает сигнал
       - FilterResult(passed=False, reason="LOW_VOLUME") если блокирует
       """
   ```

3. **FalseBreakoutDetector** (`false_breakout_detector.py`)
   - Детекция ложных пробоев
   - Анализ объема, momentum, уровней
   - ML веса для факторов

   **Детали:**

   ```python
   class FalseBreakoutDetector:
       """
       Детектор ложных пробоев

       Анализ факторов:
       1. Volume (40% веса по умолчанию)
          - Объем при пробое должен быть выше среднего
          - Подтверждение направления пробоя

       2. Momentum (30% веса)
          - Сила движения цены
          - RSI, MACD гистограмма
          - Скорость изменения цены

       3. Level Quality (30% веса)
          - Качество пробоя уровня
          - Количество касаний уровня
          - Время удержания выше/ниже уровня

       ML оптимизация:
       - Динамические веса факторов
       - Адаптация под волатильность
       - Учет рыночного режима

       Пороги:
       - min_total_confidence = 0.20 (по умолчанию)
       - Адаптивные под режим рынка
       """
   ```

4. **AdaptiveRSI** (`adaptive_rsi.py`)
   - Адаптивный RSI
   - Режимы (soft/strict)
   - Предупреждения

   **Детали:**

   ```python
   class AdaptiveRSI:
       """
       Адаптивный фильтр RSI

       Режимы:
       - Soft: RSI < 20 (перепроданность) или > 80 (перекупленность)
       - Strict: RSI < 15 или > 85

       Предупреждения:
       - RSI в опасной зоне блокирует сигнал
       - LONG блокируется при RSI > 70
       - SHORT блокируется при RSI < 30

       Адаптация:
       - Учет волатильности
       - Корректировка порогов под тренд
       """
   ```

5. **InterestZoneFilter** (`interest_zone.py`)
   - Зоны интереса
   - Поддержка/сопротивление

   **Детали:**

   ```python
   class InterestZoneFilter:
       """
       Фильтр зон интереса (поддержка/сопротивление)

       Определение зон:
       - Локальные максимумы/минимумы
       - Кластеры объемов
       - Исторические уровни

       Логика:
       - LONG: Вход в зоне поддержки
       - SHORT: Вход в зоне сопротивления
       - Блокировка при пробое в неправильном направлении
       """
   ```

6. **FibonacciZoneFilter** (`fibonacci_zone.py`)
   - Фибоначчи уровни
   - Зоны входа

   **Детали:**

   ```python
   class FibonacciZoneFilter:
       """
       Фильтр зон Фибоначчи

       Уровни:
       - 0.236, 0.382, 0.5, 0.618, 0.786

       Логика:
       - Определение swing high/low
       - Расчет уровней Фибоначчи
       - Вход в зоне коррекции
       """
   ```

---

### 🤖 AI/ML Система

**Компоненты:**

1. **ml_filter_optimizer.py**
   - Оптимизация параметров фильтров
   - Адаптация к рыночным условиям
   - Обучение на исторических данных

2. **lightgbm_predictor.py**
   - LightGBM модели
   - Предсказание успешности сигналов
   - Классификация и регрессия

3. **ai_signal_generator.py**
   - AI генерация сигналов
   - Анализ паттернов
   - Обучение на обратной связи

4. **adaptive_parameter_controller.py**
   - Адаптивное управление параметрами
   - Оптимизация на основе метрик
   - Динамическая настройка

**Детальная структура:**

**ML Filter Optimizer:**

```python
class MLFilterOptimizer:
    """
    ML оптимизация параметров фильтров

    Оптимизируемые параметры:
    1. Volume Imbalance Filter
       - min_volume_ratio (адаптивный порог)
       - require_volume_confirmation (требование подтверждения)

    2. False Breakout Detector
       - false_breakout_threshold (порог детекции)
       - false_breakout_weights (веса факторов)
       - volume_weight, momentum_weight, level_weight

    Рыночные условия:
    - regime: LOW_VOL_RANGE, MEDIUM_VOL, HIGH_VOL, TREND
    - volatility: процент волатильности
    - trend_strength: сила тренда

    Адаптация:
    - Релаксация порогов для интрадей торговли
    - Учет времени суток
    - Анализ исторических паттернов

    Методы:
    - optimize_filter_parameters() - оптимизация параметров
    - get_optimal_weights() - оптимальные веса для false_breakout
    """
```

**LightGBM Predictor:**

```python
class LightGBMPredictor:
    """
    LightGBM модели для предсказания

    Модели:
    1. Классификация (успешность сигнала)
       - Вход: технические индикаторы, рыночные условия
       - Выход: вероятность успеха (0-1)

    2. Регрессия (прибыльность)
       - Вход: те же признаки
       - Выход: ожидаемая прибыль (%)

    Признаки (features):
    - Технические индикаторы (RSI, MACD, EMA, etc.)
    - Объемные метрики
    - Волатильность (ATR)
    - Рыночный режим
    - Корреляция с BTC/ETH/SOL

    Обучение:
    - Исторические данные из signals_log
    - Минимум 1000 примеров для обучения
    - Автоматическое переобучение (еженедельно)
    """
```

**AI Signal Generator:**

```python
class AISignalGenerator:
    """
    AI генератор сигналов

    Компоненты:
    - AILearningSystem: обучение на паттернах
    - AIIntegration: интеграция с торговой системой
    - AIMonitor: мониторинг производительности

    Процесс генерации:
    1. Анализ символа
       - Получение OHLC данных
       - Расчет индикаторов
       - Анализ паттернов

    2. AI рекомендации
       - Анализ исторических паттернов
       - Предсказание успешности
       - Оценка рисков

    3. Генерация сигнала
       - Определение типа (LONG/SHORT)
       - Расчет уровней (TP1, TP2, SL)
       - Формирование сообщения

    4. Отправка
       - Фильтрация по настройкам пользователя
       - Отправка в Telegram
       - Сохранение в БД
    """
```

**Adaptive Parameter Controller:**

```python
class AdaptiveParameterController:
    """
    Адаптивное управление параметрами

    Оптимизируемые параметры:
    - Risk % (размер позиции)
    - Leverage (плечо)
    - TP1/TP2 уровни
    - Stop Loss
    - Preferred Symbols (лучшие монеты)
    - Trading Hours (лучшие часы)

    Метрики для оптимизации:
    - Win Rate (процент прибыльных сделок)
    - Profit Factor (отношение прибыли к убыткам)
    - Sharpe Ratio
    - Max Drawdown

    Процесс:
    1. Сбор метрик за период
    2. Анализ производительности
    3. Оптимизация параметров
    4. Сохранение в ai_learning_data/optimized_parameters.json
    5. Применение в следующем цикле

    Обновление:
    - При каждой сделке
    - Еженедельный полный анализ
    """
```

---

### 💾 Система базы данных

**Основные таблицы:**

1. **signals_log**
   - История всех сигналов
   - Параметры входа/выхода
   - Результаты сделок

2. **accepted_signals**
   - Принятые сигналы
   - Статусы (pending/accepted/closed)
   - PnL

3. **active_positions**
   - Активные позиции
   - Синхронизация с биржей
   - SL/TP уровни

4. **users_data**
   - Настройки пользователей
   - Балансы
   - Режимы торговли

5. **risk_signal_history**
   - История рисков
   - Корреляционный анализ
   - Группы активов

**Модули:**

- `db.py` — Основной модуль БД
- `acceptance_database.py` — Управление принятием сигналов
- `database_initialization.py` — Инициализация схемы

**Детальная структура:**

**signals_log:**

```sql
CREATE TABLE signals_log (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    entry REAL,                    -- Цена входа
    stop REAL,                     -- Stop Loss
    tp1 REAL,                      -- Take Profit 1
    tp2 REAL,                      -- Take Profit 2
    entry_time TEXT,               -- Время входа (ISO)
    exit_time TEXT,                -- Время выхода
    result TEXT,                   -- PENDING/OPEN/CLOSED/WIN/LOSS
    net_profit REAL,               -- Чистая прибыль
    user_id INTEGER,               -- ID пользователя
    created_at DATETIME,           -- Время создания записи
    -- Дополнительные поля
    trade_mode TEXT,               -- spot/futures
    leverage_used INTEGER,
    risk_pct_used REAL,
    quality_score REAL,            -- Оценка качества сигнала
    confidence REAL                 -- Уверенность в сигнале
);
```

**accepted_signals:**

```sql
CREATE TABLE accepted_signals (
    signal_key TEXT PRIMARY KEY,   -- Уникальный ключ сигнала
    symbol TEXT NOT NULL,
    direction TEXT,                -- LONG/SHORT
    entry_price REAL,
    signal_time DATETIME,
    user_id INTEGER,
    chat_id INTEGER,
    message_id INTEGER,            -- ID сообщения в Telegram
    status TEXT,                  -- pending/accepted/closed
    accepted_time DATETIME,
    closed_time DATETIME,
    close_price REAL,
    pnl REAL,                     -- Прибыль/убыток
    pnl_pct REAL,                 -- Прибыль/убыток в %
    created_at DATETIME,
    accepted_by TEXT              -- manual/auto
);
```

**active_positions:**

```sql
CREATE TABLE active_positions (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    direction TEXT,               -- BUY/SELL
    entry_price REAL,
    user_id INTEGER,
    signal_key TEXT,              -- Связь с accepted_signals
    status TEXT,                  -- open/closed
    sl_price REAL,
    tp1_price REAL,
    tp2_price REAL,
    created_at DATETIME,
    updated_at DATETIME
);
```

**users_data:**

```sql
CREATE TABLE users_data (
    user_id INTEGER PRIMARY KEY,
    deposit REAL,                 -- Депозит
    balance REAL,                 -- Текущий баланс
    trade_mode TEXT,              -- spot/futures
    leverage INTEGER,             -- Плечо
    risk_pct REAL,                -- Процент риска
    filter_mode TEXT,             -- soft/strict
    settings TEXT,                -- JSON с дополнительными настройками
    created_at DATETIME,
    updated_at DATETIME
);
```

**risk_signal_history:**

```sql
CREATE TABLE risk_signal_history (
    id INTEGER PRIMARY KEY,
    signal_key TEXT,
    symbol TEXT,
    group_name TEXT,              -- BTC_HIGH/ETH_HIGH/SOL_HIGH/OTHER
    correlation REAL,             -- Корреляция с основной монетой
    risk_level TEXT,              -- LOW/MEDIUM/HIGH
    created_at DATETIME
);
```

**Дополнительные таблицы:**

- `order_audit_log` — Аудит всех ордеров
- `filter_checks` — История проверок фильтров
- `false_breakout_events` — События ложных пробоев
- `position_sizing_events` — События расчета размера позиции
- `backtest_results` — Результаты бэктестов

**Модули работы с БД:**

**db.py:**

```python
class Database:
    """
    Основной класс для работы с БД

    Методы:
    - get_user_data() - получение данных пользователя
    - save_user_data() - сохранение данных пользователя
    - get_signals() - получение сигналов
    - save_signal() - сохранение сигнала
    """
```

**acceptance_database.py:**

```python
class AcceptanceDatabase:
    """
    Управление принятием сигналов

    Методы:
    - accept_signal() - принятие сигнала
    - get_signal_data() - получение данных сигнала
    - create_active_position() - создание активной позиции
    - update_signal_status() - обновление статуса
    - get_user_positions() - получение позиций пользователя
    """
```

**Особенности:**

- **WAL mode**: Write-Ahead Logging для конкурентного доступа
- **READONLY mode**: Для dashboard и мониторинга
- **Backup**: Автоматические бэкапы в `backups/`
- **Миграции**: Через `database_initialization.py`

---

### 📱 Telegram интеграция

**Компоненты:**

1. **telegram_handlers.py**
   - Обработка команд
   - Кнопки принятия сигналов
   - Управление позициями

2. **enhanced_telegram_delivery.py**
   - Улучшенная доставка сообщений
   - Rate limiting
   - Retry логика
   - Отправка в оба бота (DEV/PROD)

3. **src/telegram/bot.py**
   - Основной класс бота
   - Инициализация
   - Обработка обновлений

4. **messaging_service.py**
   - Форматирование сообщений
   - Шаблоны сигналов
   - Уведомления

---

### 🔄 Система синхронизации

**Компоненты:**

1. **scripts/sync_positions_with_exchange.py**
   - Синхронизация позиций с биржей
   - Проверка направлений
   - Обновление статусов

2. **main.py** — `_sync_positions_periodically()`
   - Периодическая синхронизация
   - Trailing stop management
   - Мониторинг TP1/TP2

---

### 🛡️ Риск-менеджмент

**Компоненты:**

1. **correlation_risk_manager.py**
   - Анализ корреляций
   - Группировка активов
   - Лимиты на группу

2. **portfolio_risk_manager.py**
   - Управление портфелем
   - Анализ экспозиции
   - Предупреждения

3. **risk_monitor/**
   - Мониторинг рисков
   - Расчеты метрик
   - Уведомления

**Детальная структура:**

**Correlation Risk Manager:**

```python
class CorrelationRiskManager:
    """
    Управление корреляционными рисками

    Группировка активов:
    - BTC_HIGH: correlation > 0.75 к BTC
    - ETH_HIGH: correlation > 0.75 к ETH
    - SOL_HIGH: correlation > 0.75 к SOL
    - OTHER: остальные активы

    Лимиты на группу:
    - SECTOR_MAX_PER_GROUP = 2 (максимум 2 сигнала в группе)
    - CORRELATION_LOOKBACK_HOURS = 24 (анализ за 24 часа)
    - CORRELATION_COOLDOWN_SEC = 3600 (кулдаун 1 час)

    Процесс:
    1. Расчет корреляции с BTC/ETH/SOL
    2. Определение группы актива
    3. Проверка активных сигналов в группе
    4. Блокировка если лимит превышен

    Сохранение истории:
    - risk_signal_history таблица
    - Для анализа и мониторинга
    """
```

**Portfolio Risk Manager:**

```python
class PortfolioRiskManager:
    """
    Управление портфельными рисками

    Анализ:
    1. Общая экспозиция портфеля
    2. Концентрация по секторам
    3. Корреляция между позициями
    4. Максимальный drawdown

    Предупреждения:
    - Высокая концентрация в одном секторе
    - Превышение максимальной экспозиции
    - Высокая корреляция позиций

    Действия:
    - Блокировка новых сигналов при рисках
    - Рекомендации по закрытию позиций
    - Уведомления администраторам
    """
```

**Risk Monitor:**

```python
# risk_monitor/calculations.py
def calculate_portfolio_risk(positions):
    """
    Расчет портфельных рисков

    Метрики:
    - Total Exposure: сумма всех позиций
    - Sector Concentration: концентрация по секторам
    - Correlation Matrix: корреляция между позициями
    - Max Drawdown: максимальная просадка

    Возвращает:
    - Dict с метриками риска
    - Уровень риска (LOW/MEDIUM/HIGH/CRITICAL)
    """
```

**Интеграция в send_signal:**

```python
# Проверка корреляционных рисков
correlation_result = await correlation_manager.check_correlation_risk_async(
    symbol=symbol,
    direction=signal_type,
    user_id=user_id
)

if not correlation_result.get('allowed'):
    logger.warning("🚫 Корреляционный риск: %s", correlation_result.get('reason'))
    return False

# Проверка портфельных рисков
portfolio_risk = await portfolio_manager.check_portfolio_risk(
    user_id=user_id,
    new_symbol=symbol,
    new_direction=signal_type
)

if portfolio_risk.get('risk_level') == 'CRITICAL':
    logger.warning("🚫 Портфельный риск: %s", portfolio_risk.get('reason'))
    return False
```

---

### 📈 Trailing Stop система

**Компоненты:**

1. **trailing_stop_manager.py**
   - Управление trailing stop
   - Перенос SL в безубыток
   - Адаптивная логика

2. **AdvancedTrailingStopManager**
   - Адаптивные коэффициенты
   - Учет волатильности
   - Анализ тренда

**Детальная структура:**

**Основная логика:**

```python
class TrailingStopManager:
    """
    Управление трейлинг-стопами

    Настройки:
    - tp1_activation_progress = 0.5 (50% пути к TP1)
    - tp1_sl_progress_ratio = 1.0 (SL движется на такое же расстояние)
    - tp1_min_atr_multiplier = 2.0 (минимум ATR * 2.0)

    Процесс:
    1. Отслеживание прогресса к TP1
    2. При достижении 50% пути к TP1:
       - Расчет нового SL
       - Перенос SL на такое же расстояние
    3. При достижении TP1:
       - Перенос SL в безубыток + offset
    """
```

**Адаптивная система:**

```python
class AdvancedTrailingStopManager:
    """
    Продвинутая адаптивная система trailing stop

    Факторы адаптации:

    1. Волатильность (ATR, стандартное отклонение)
       - LOW: ratio = 1.0 (максимальное движение SL)
       - MEDIUM: ratio = 0.8
       - HIGH: ratio = 0.6
       - EXTREME: ratio = 0.4 (консервативно)

    2. Сила тренда (ADX, наклон MA)
       - STRONG: +30% к ratio
       - MEDIUM: +10%
       - WEAK: без изменений
       - RANGING: -30%
       - REVERSAL: -50%

    3. Рыночный режим
       - Тренд: более агрессивно
       - Боковик: более консервативно

    4. Время суток
       - Высокая волатильность (9-10, 16-17): -20%
       - Низкая волатильность: +20%
       - Ночные часы: -30%

    Ограничения:
    - min_ratio = 0.15 (минимум)
    - max_ratio = 1.2 (максимум)
    - min_safe_distance_atr = 1.5 (безопасное расстояние)
    """
```

**Интеграция:**

```python
# В main.py, функция _sync_positions_periodically()

# Инициализация для новой позиции
trailing_mgr.setup_position(
    symbol=symbol,
    entry_price=entry_price,
    initial_sl=sl_price,
    side=direction,
    tp1_price=tp1_price
)

# Проверка и перенос SL
trailing_result = trailing_mgr.calculate_tp1_trailing_stop(
    symbol=symbol,
    current_price=current_price,
    df=df_for_trailing,  # OHLC данные для адаптивной логики
    direction=direction,
    entry_price=entry_price,
    tp1_price=tp1_price
)

if trailing_result and trailing_result.get('stop_moved'):
    new_sl_price = trailing_result.get('new_stop')
    # Обновление SL на бирже
    await adapter.place_stop_loss_order(...)
```

---

### 🧪 Agent Gym — Система оффлайн симуляций

**Назначение:** Тестирование и анализ производительности компонентов системы в оффлайн режиме

**Расположение:** `agent_gym/`

**Основные компоненты:**

1. **scenarios.py**
   - Определение сценариев тестирования
   - Базовый класс `Scenario`
   - Реализованные сценарии:
     - `SignalThroughputScenario` — анализ пропускной способности сигналов
     - `ExecutionFallbackScenario` — анализ fallback механизмов исполнения

2. **configs/**
   - JSON конфигурации сценариев
   - Параметры тестирования
   - Пример: `sample_scenarios.json`

3. **reports/**
   - Отчеты о результатах симуляций
   - JSON форматы для анализа
   - Сравнение с baseline

**Использование:**

```bash
# Запуск симуляций
python3 scripts/run_agent_gym.py --scenarios agent_gym/configs/sample_scenarios.json

# Ночной запуск (автоматический)
python3 scripts/run_agent_gym_nightly.py
```

**Что анализируется:**

- **Пропускная способность сигналов:**
  - Количество сигналов за период
  - Уникальные символы
  - Среднее качество и уверенность

- **Fallback механизмы:**
  - Успешность limit/market ордеров
  - Соотношение заполненных/незаполненных
  - Анализ таймаутов

**Преимущества:**

- ✅ Оффлайн тестирование без влияния на production
- ✅ Анализ исторических данных
- ✅ Выявление проблем производительности
- ✅ Сравнение с baseline метриками

---

## 🔄 ПОТОКИ ДАННЫХ

### Генерация сигнала:

```
1. Получение данных
   └─> exchange_api.get_klines()
       └─> Fallback: Binance → Bybit → OKX

2. Расчет индикаторов
   └─> add_technical_indicators()
       ├─> RSI, MACD, EMA
       ├─> Bollinger Bands
       └─> ATR, ADX

3. Генерация candidate
   └─> _generate_signal_impl()
       ├─> Классические паттерны
       ├─> Pullback entry
       └─> Zone-based

4. Фильтрация
   └─> Применение фильтров
       ├─> Trend (BTC/ETH/SOL)
       ├─> Volume imbalance
       ├─> False breakout
       ├─> RSI warning
       └─> ML optimization

5. Проверка рисков
   └─> correlation_risk_manager
       └─> portfolio_risk_manager

6. Отправка
   └─> send_signal()
       ├─> notify_user_enhanced()
       │   ├─> PROD бот
       │   └─> DEV бот
       └─> Сохранение в БД

7. Автоисполнение (если включено)
   └─> auto_execution.execute_and_open()
       ├─> Открытие позиции
       ├─> Установка SL
       └─> Установка TP1/TP2
```

**Детальная схема с примерами:**

**1. Получение данных (пример для BTCUSDT):**

```python
# Запрос к API
df = await get_klines("BTCUSDT", timeframe="1h", limit=300)

# Результат:
# timestamp    open      high      low       close     volume
# 1698768000   35000.0   35100.0   34900.0   35050.0   1234.56
# 1698771600   35050.0   35200.0   35000.0   35150.0   1456.78
# ...

# Fallback механизм:
# Попытка 1: Binance API → успех ✅
# Если ошибка: Попытка 2: Bybit API
# Если ошибка: Попытка 3: OKX API
# Если ошибка: Использование кэша (если доступен)
```

**2. Расчет индикаторов:**

```python
df = add_technical_indicators(df)

# Добавленные колонки:
# rsi: 45.2 (нейтральная зона)
# macd: 12.5 (бычий сигнал)
# ema_fast: 35025.0
# ema_slow: 34980.0 (EMA Fast > EMA Slow → бычий тренд)
# bb_upper: 35200.0
# bb_lower: 34800.0
# atr: 150.0
# adx: 28.5 (средний тренд)
```

**3. Генерация сигнала:**

```python
# Обнаружен паттерн: EMA Fast пересек EMA Slow снизу вверх
# → Классический бычий сигнал (LONG)

signal_data = {
    "symbol": "BTCUSDT",
    "direction": "LONG",
    "entry_price": 35050.0,
    "confidence": 0.75,
    "pattern": "ema_crossover"
}
```

**4. Фильтрация (последовательно):**

```python
# Фильтр 1: BTC Trend
btc_trend_result = smart_trend_filter.filter_signal(...)
# ✅ ПРОШЕЛ: BTC в бычьем тренде

# Фильтр 2: Volume Imbalance
volume_result = volume_filter.filter_signal(...)
# ✅ ПРОШЕЛ: Объем на 25% выше среднего

# Фильтр 3: False Breakout
false_breakout_result = false_breakout_detector.analyze(...)
# ✅ ПРОШЕЛ: Не ложный пробой (confidence = 0.65)

# Фильтр 4: RSI Warning
rsi_check = check_rsi_warning(...)
# ✅ ПРОШЕЛ: RSI = 45.2 (не в опасной зоне)

# Фильтр 5: ML Optimization
ml_result = ml_optimizer.optimize_filter_parameters(...)
# ✅ ПРОШЕЛ: ML рекомендует разрешить сигнал
```

**5. Проверка рисков:**

```python
# Корреляционный риск
correlation_check = await correlation_manager.check_correlation_risk_async(
    symbol="BTCUSDT",
    direction="LONG",
    user_id=958930260
)
# Результат: {"allowed": True, "group": "BTC_HIGH", "active_in_group": 1}

# Портфельный риск
portfolio_check = await portfolio_manager.check_portfolio_risk(
    user_id=958930260,
    new_symbol="BTCUSDT",
    new_direction="LONG"
)
# Результат: {"risk_level": "LOW", "total_exposure": 15.5}
```

**6. Отправка сигнала:**

```python
# Формирование сообщения
message = """
🟢 НОВЫЙ ТОРГОВЫЙ СИГНАЛ

📊 Символ: BTCUSDT
📈 Сторона: LONG
💰 Цена входа: 35050.0
🎯 TP1: 35751.0 (+2.0%)
🎯 TP2: 36452.0 (+4.0%)
🛡️ SL: 34349.0 (-2.0%)
💵 Сумма входа: 50 USDT
🔢 Плечо: 3x
"""

# Отправка в оба бота
success = await notify_user_enhanced(
    user_id=958930260,
    message=message,
    reply_markup=keyboard,
    _send_to_both_bots=True  # Отправка в DEV и PROD
)

# Результат:
# ✅ PROD бот: message_id = 27469
# ✅ DEV бот: message_id = 12345
```

**7. Автоисполнение (PROD режим):**

```python
if ATRA_ENV == "prod" and success:
    # Открытие позиции
    execution_result = await auto_exec.execute_and_open(
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=35050.0,
        quantity_usdt=50.0,  # Маржа
        leverage=3,
        sl_price=34349.0,
        tp1_price=35751.0,
        tp2_price=36452.0
    )

    # Результат:
    # ✅ Позиция открыта: order_id = "12345678"
    # ✅ SL установлен: order_id = "12345679"
    # ✅ TP1 установлен: order_id = "12345680"
    # ✅ TP2 установлен: order_id = "12345681"
```

---

### Принятие сигнала:

```
1. Пользователь нажимает кнопку
   └─> telegram_handlers.button_callback()

2. Валидация
   └─> Проверка параметров
       ├─> Символ
       ├─> Цена
       └─> Время

3. Сохранение
   └─> acceptance_database.accept_signal()
       └─> Обновление статуса

4. Открытие позиции (если ручной режим)
   └─> telegram_handlers.handle_accept()
       └─> exchange_adapter.place_order()
```

**Детальная схема с примерами:**

**1. Пользователь нажимает кнопку "Принять":**

```python
# callback_data: "accept|BTCUSDT|1763581081|35050.0|0.0014|LONG|2.0|3.0"

# Парсинг
parts = callback_data.split("|")
# parts[0] = "accept"
# parts[1] = "BTCUSDT"
# parts[2] = "1763581081" (timestamp)
# parts[3] = "35050.0" (цена)
# parts[4] = "0.0014" (количество)
# parts[5] = "LONG"
# parts[6] = "2.0" (риск %)
# parts[7] = "3.0" (плечо)
```

**2. Валидация:**

```python
# Проверка времени (TTL кнопки)
current_time = time.time()
signal_time = float(parts[2])
if current_time - signal_time > 300:  # 5 минут
    # Кнопка истекла
    await update.message.answer("⏰ Время действия кнопки истекло")
    return

# Проверка цены (изменение не более 1%)
current_price = await get_current_price("BTCUSDT")
signal_price = float(parts[3])
price_diff = abs(current_price - signal_price) / signal_price
if price_diff > 0.01:
    # Цена изменилась слишком сильно
    await update.message.answer("⚠️ Цена изменилась. Получите новый сигнал.")
    return
```

**3. Сохранение:**

```python
# Обновление статуса в БД
await acceptance_db.accept_signal(
    signal_key="BTCUSDT_1763581081.666965",
    user_id=958930260,
    accepted_time=datetime.now(),
    accepted_by="manual"  # или "auto"
)

# Результат в БД:
# accepted_signals:
#   status: "pending" → "accepted"
#   accepted_time: "2025-11-19 23:05:00"
```

**4. Открытие позиции (ручной режим):**

```python
# Если trade_mode = "manual"
if user_data.get("trade_mode") == "manual":
    # Пользователь сам открывает позицию на бирже
    # Бот только сохраняет информацию
    await update.message.answer(
        "✅ Сигнал принят! Откройте позицию на бирже:\n"
        f"Символ: BTCUSDT\n"
        f"Направление: LONG\n"
        f"Цена входа: 35050.0\n"
        f"Количество: 0.0014 BTC"
    )
else:
    # Автоматическое открытие (если включено)
    await auto_exec.execute_and_open(...)
```

---

### Синхронизация позиций:

```
1. Периодическая проверка (каждые 60 сек)
   └─> main._sync_positions_periodically()

2. Получение позиций с биржи
   └─> exchange_adapter.get_positions()

3. Сравнение с БД
   ├─> Проверка наличия сигнала
   ├─> Проверка направления
   └─> Обновление/добавление

4. Trailing Stop
   └─> trailing_stop_manager
       ├─> Проверка прогресса к TP1
       └─> Перенос SL при 50%
```

**Детальная схема с примерами:**

**1. Периодическая проверка:**

```python
# Каждые 60 секунд
async def _sync_positions_periodically():
    while True:
        await asyncio.sleep(60)

        # Для каждого пользователя
        for user_id in active_users:
            await sync_user_positions(user_id)
```

**2. Получение позиций с биржи:**

```python
# Запрос к бирже
positions = await adapter.get_positions(user_id=958930260)

# Результат:
# [
#   {
#     "symbol": "BTCUSDT",
#     "side": "long",
#     "size": 0.0014,
#     "entry_price": 35050.0,
#     "unrealized_pnl": 2.5
#   },
#   {
#     "symbol": "ETHUSDT",
#     "side": "short",
#     "size": 0.05,
#     "entry_price": 2500.0,
#     "unrealized_pnl": -1.2
#   }
# ]
```

**3. Сравнение с БД:**

```python
# Для каждой позиции с биржи
for position in positions:
    symbol = position["symbol"]
    direction = "BUY" if position["side"] == "long" else "SELL"

    # Проверка наличия сигнала
    signal_data = await adb.get_signal_data(user_id, symbol)

    if not signal_data:
        # Ручная позиция (открыта не через бота)
        logger.info("📝 Ручная позиция: %s", symbol)
        await adb.upsert_active_position(
            user_id, symbol, direction, entry_price, "open",
            signal_key=None  # None = manual
        )
    else:
        # Проверка направления
        signal_direction = signal_data.get("direction")
        if signal_direction != direction:
            # Несоответствие направления - возможна ошибка
            logger.warning("🚫 Несоответствие направления: %s", symbol)
            continue  # Пропускаем

        # Автоматическая позиция
        await adb.upsert_active_position(
            user_id, symbol, direction, entry_price, "open",
            signal_key=signal_data.get("signal_key")
        )
```

**4. Trailing Stop:**

```python
# Для каждой активной позиции
for position in active_positions:
    symbol = position["symbol"]
    entry_price = position["entry_price"]
    tp1_price = position["tp1_price"]
    current_price = await get_current_price(symbol)

    # Расчет прогресса к TP1
    if direction == "LONG":
        progress = (current_price - entry_price) / (tp1_price - entry_price)
    else:  # SHORT
        progress = (entry_price - current_price) / (entry_price - tp1_price)

    # Если достигли 50% пути к TP1
    if progress >= 0.5:
        # Расчет нового SL
        trailing_result = trailing_mgr.calculate_tp1_trailing_stop(
            symbol=symbol,
            current_price=current_price,
            df=df,  # OHLC данные для адаптивной логики
            direction=direction,
            entry_price=entry_price,
            tp1_price=tp1_price
        )

        if trailing_result.get("stop_moved"):
            new_sl = trailing_result.get("new_stop")

            # Обновление SL на бирже
            await adapter.place_stop_loss_order(
                symbol, direction, size, new_sl
            )

            logger.info(
                "🎯 SL перенесен в безубыток: %s @ %.8f "
                "(прогресс к TP1: %.1f%%)",
                symbol, new_sl, progress * 100
            )
```

---

## ⚙️ КОНФИГУРАЦИЯ

### Файлы конфигурации:

1. **config.py**
   - Основные настройки
   - Фильтры
   - Риск-менеджмент

2. **env.prod** / **env.dev**
   - Переменные окружения
   - API ключи
   - Токены Telegram

3. **hybrid_config.py**
   - Гибридные настройки
   - Адаптивные параметры

### Основные настройки:

```python
# Режим работы
ATRA_ENV = "prod"  # или "dev"

# Telegram
TELEGRAM_TOKEN = "..."      # PROD токен
TELEGRAM_TOKEN_DEV = "..."  # DEV токен

# Торговля
DEFAULT_RISK_PCT = 2.0
DEFAULT_LEVERAGE = 1.0
TRADING_MODE = "futures"    # или "spot"

# Фильтры
USE_BTC_TREND_FILTER = True
USE_ETH_TREND_FILTER = True
USE_SOL_TREND_FILTER = True

# ML
USE_ML_OPTIMIZATION = True
LIGHTGBM_ENABLED = True
```

**Детальная структура конфигурации:**

**Фильтры:**

```python
# BTC Trend Filter
BTC_TREND_EMA_SOFT = 50              # EMA период для soft режима
BTC_TREND_EMA_STRICT = 200           # EMA период для strict режима
BTC_TREND_LOOKBACK = 50               # Количество свечей для анализа
BTC_TREND_MAX_DROP_PCT = 8.0         # Максимальное падение для блокировки
BTC_TREND_USE_MULTITF = True          # Multi-timeframe подтверждение

# Volume Imbalance Filter
VOLUME_IMBALANCE_FILTER_CONFIG = {
    'enabled': True,
    'min_volume_ratio': 1.2,          # Минимальное соотношение объемов
    'require_volume_confirmation': True,  # Требование подтверждения
    'use_ml_optimization': True,      # Использование ML оптимизации
    'lookback_periods': 20            # Период для расчета среднего
}

# False Breakout Detector
FALSE_BREAKOUT_CONFIG = {
    'enabled': True,
    'min_total_confidence': 0.20,     # Минимальная уверенность
    'volume_weight': 0.40,             # Вес фактора объема
    'momentum_weight': 0.30,           # Вес фактора momentum
    'level_weight': 0.30               # Вес фактора уровня
}

# RSI Filter
RSI_OVERSOLD = 20                     # Уровень перепроданности
RSI_OVERBOUGHT = 80                   # Уровень перекупленности
RSI_WARNING_OVERSOLD = 15             # Предупреждение (строгий)
RSI_WARNING_OVERBOUGHT = 85           # Предупреждение (строгий)
```

**Риск-менеджмент:**

```python
# Размер позиции
DEFAULT_RISK_PCT = 2.0                # Процент риска по умолчанию
MIN_RISK_PCT = 0.1                    # Минимальный риск
MAX_RISK_PCT = 10.0                   # Максимальный риск

# Плечо
DEFAULT_LEVERAGE = 1.0                # Плечо по умолчанию
MIN_LEVERAGE = 1                      # Минимальное плечо
MAX_LEVERAGE = 20                     # Максимальное плечо (зависит от биржи)

# Корреляционные риски
CORRELATION_COOLDOWN_ENABLED = True
CORRELATION_LOOKBACK_HOURS = 24       # Анализ за 24 часа
SECTOR_MAX_PER_GROUP = 2              # Максимум сигналов в группе
CORRELATION_COOLDOWN_SEC = 3600       # Кулдаун 1 час
```

**Trailing Stop:**

```python
ADAPTIVE_TRAILING_CONFIG = {
    'enabled': True,
    'volatility_regimes': {
        'LOW': {'max_ratio': 1.0, 'min_ratio': 0.8, 'atr_threshold': 0.01},
        'MEDIUM': {'max_ratio': 0.8, 'min_ratio': 0.5, 'atr_threshold': 0.025},
        'HIGH': {'max_ratio': 0.6, 'min_ratio': 0.3, 'atr_threshold': 0.05},
        'EXTREME': {'max_ratio': 0.4, 'min_ratio': 0.2, 'atr_threshold': 0.1}
    },
    'trend_strength': {
        'STRONG': 1.3,                 # +30% при сильном тренде
        'MEDIUM': 1.1,                 # +10% при среднем тренде
        'WEAK': 1.0,                   # Без изменений
        'RANGING': 0.7,                # -30% при боковике
        'REVERSAL': 0.5                # -50% при развороте
    },
    'time_factors': {
        'HIGH_VOLATILITY_HOURS': [9, 10, 16, 17],
        'high_vol_multiplier': 0.8,
        'low_vol_multiplier': 1.2
    },
    'min_safe_distance_atr': 1.5,     # Минимальное расстояние в ATR
    'max_ratio': 1.2,
    'min_ratio': 0.15
}
```

**Список монет:**

```python
# Автоматический подбор монет
AUTO_FETCH_COINS = True               # Включить авто-подбор

# Или фиксированный список
COINS = [
    "BONKUSDT", "NEIROUSDT", "SUIUSDT",
    "POLUSDT", "WIFUSDT", "ADAUSDT",
    # ... и т.д.
]

# Параметры авто-подбора
TOP_N = 500                            # Топ N пар для анализа
FINAL_LIMIT = 200                     # Финальный список
MIN_24H_VOLUME = 1000000              # Минимальный объем 24h ($)
```

**Telegram:**

```python
# Выбор токена в зависимости от окружения
TOKEN = (
    TELEGRAM_TOKEN if ATRA_ENV == "prod" else (
        TELEGRAM_TOKEN_DEV or TELEGRAM_TOKEN
    )
)

# Отправка в оба бота
# В signal_live.py используется параметр _send_to_both_bots=True
```

**База данных:**

```python
DATABASE = "trading.db"               # Путь к БД
BACKUP_DIR = "backups/"               # Директория бэкапов
BACKUP_INTERVAL_HOURS = 24            # Интервал бэкапов
```

**ML/AI:**

```python
# LightGBM
LIGHTGBM_ENABLED = True
LIGHTGBM_MODEL_PATH = "models/lightgbm_model.pkl"
LIGHTGBM_RETRAIN_INTERVAL_DAYS = 7    # Переобучение раз в неделю

# ML Filter Optimizer
USE_ML_OPTIMIZATION = True
ML_OPTIMIZATION_INTERVAL_HOURS = 6    # Обновление параметров каждые 6 часов
```

---

## 💾 БАЗА ДАННЫХ

### Схема основных таблиц:

**signals_log:**

- `id`, `symbol`, `entry`, `stop`, `tp1`, `tp2`
- `entry_time`, `exit_time`, `result`
- `net_profit`, `user_id`, `created_at`

**accepted_signals:**

- `signal_key`, `symbol`, `direction`
- `entry_price`, `signal_time`
- `user_id`, `chat_id`, `message_id`
- `status`, `accepted_time`, `pnl`

**active_positions:**

- `symbol`, `direction`, `entry_price`
- `user_id`, `signal_key`
- `status`, `sl_price`, `tp1_price`, `tp2_price`

**users_data:**

- `user_id`, `deposit`, `balance`
- `trade_mode`, `leverage`, `risk_pct`
- `filter_mode`, `settings`

**risk_signal_history:**

- `signal_key`, `symbol`, `group`
- `correlation`, `risk_level`
- `created_at`

---

## 🚀 РАЗВЕРТЫВАНИЕ

### Серверная инфраструктура:

**Сервер:** `185.177.216.15`  
**Пользователь:** `root`  
**Директория:** `/root/atra`  
**Пароль SSH:** `u44Ww9NmtQj,XG`

### Процесс развертывания:

1. **Подготовка:**

   ```bash
   ssh root@185.177.216.15
   cd /root/atra
   ```

2. **Обновление кода:**

   ```bash
   # Через git (если доступен)
   git stash                    # Сохранить локальные изменения
   git pull origin main
   git stash pop               # Восстановить изменения

   # Или через scp (если git недоступен)
   scp config.py signal_live.py root@185.177.216.15:/root/atra/
   ```

3. **Установка зависимостей:**

   ```bash
   pip3 install -r requirements.txt

   # Установка конкретных библиотек
   pip3 install lightgbm scikit-learn
   ```

4. **Проверка конфигурации:**

   ```bash
   # Проверка env.prod
   cat env.prod | grep ATRA_ENV
   cat env.prod | grep TELEGRAM_TOKEN

   # Проверка переменных окружения процесса
   ps aux | grep "python3 main.py"
   cat /proc/PID/environ | tr "\0" "\n" | grep ATRA_ENV
   ```

5. **Перезапуск:**

   ```bash
   # Остановка текущего процесса
   pkill -f "python3 main.py"
   sleep 2

   # Запуск нового процесса
   nohup python3 main.py > main.log 2>&1 &

   # Проверка запуска
   sleep 3
   ps aux | grep "python3 main.py" | grep -v grep
   ```

### Скрипты развертывания:

**deploy_to_production.sh:**

```bash
#!/bin/bash
# Автоматическое развертывание на продакшен сервер

SERVER="root@185.177.216.15"
PASSWORD="u44Ww9NmtQj,XG"
REMOTE_DIR="/root/atra"

# Загрузка файлов
sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no \
    config.py signal_live.py telegram_handlers.py \
    "$SERVER:$REMOTE_DIR/"

# Перезапуск
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER" \
    "cd $REMOTE_DIR && pkill -f 'python3 main.py' && \
     sleep 2 && nohup python3 main.py > main.log 2>&1 &"
```

**restart_bot_on_server.sh:**

```bash
#!/bin/bash
# Перезапуск бота на сервере

sshpass -p 'u44Ww9NmtQj,XG' ssh -o StrictHostKeyChecking=no \
    root@185.177.216.15 \
    'cd /root/atra && pkill -f "python3 main.py" && \
     sleep 2 && nohup python3 main.py > main.log 2>&1 &'
```

**update_and_restart.sh:**

```bash
#!/bin/bash
# Обновление и перезапуск

# 1. Обновление кода
git pull origin main

# 2. Загрузка на сервер
./deploy_to_production.sh

# 3. Проверка статуса
sshpass -p 'u44Ww9NmtQj,XG' ssh -o StrictHostKeyChecking=no \
    root@185.177.216.15 'ps aux | grep "python3 main.py"'
```

### Автоматизация через sshpass:

**Использование sshpass для автоматизации:**

```bash
# Установка sshpass (если не установлен)
# Ubuntu/Debian: sudo apt-get install sshpass
# macOS: brew install sshpass

# Пример команды с sshpass
sshpass -p 'u44Ww9NmtQj,XG' ssh -o StrictHostKeyChecking=no \
    root@185.177.216.15 'command'
```

### Проверка после развертывания:

```bash
# 1. Проверка процесса
ps aux | grep "python3 main.py" | grep -v grep

# 2. Проверка логов
tail -f /root/atra/main.log

# 3. Проверка токена
python3 -c "import config; print(config.TOKEN[:20])"

# 4. Проверка окружения
python3 -c "import config; print(config.ATRA_ENV)"

# 5. Проверка базы данных
sqlite3 trading.db "SELECT COUNT(*) FROM signals_log;"
```

### Откат изменений:

```bash
# Если что-то пошло не так
cd /root/atra
git stash                    # Сохранить текущие изменения
git checkout HEAD~1          # Вернуться на предыдущий коммит
# или
git reset --hard origin/main # Жесткий сброс к последнему коммиту
pkill -f "python3 main.py"
nohup python3 main.py > main.log 2>&1 &
```

---

## 📊 МОНИТОРИНГ

### Логи:

- `main.log` — Основной лог
- `bot.log` — Лог Telegram бота
- `atra.log` — Общий лог системы

### Метрики:

- **Observability система** (`observability/`)
  - Трассировка сигналов
  - Метрики производительности
  - Обратная связь

- **Monitoring система** (`monitoring/`)
  - Инфраструктурные метрики
  - Здоровье системы

### Проверка статуса:

```bash
# Процесс
ps aux | grep "python3 main.py"

# Логи
tail -f main.log

# База данных
sqlite3 trading.db "SELECT COUNT(*) FROM signals_log;"
```

**Детальная структура мониторинга:**

**Логирование:**

```python
# Уровни логирования
logging.INFO      # Информационные сообщения
logging.WARNING   # Предупреждения
logging.ERROR     # Ошибки
logging.DEBUG     # Отладочная информация

# Ротация логов
RotatingFileHandler(
    filename='main.log',
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5            # 5 файлов бэкапа
)

# Формат логов
'%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'
```

**Ключевые метрики для мониторинга:**

1. **Производительность сигналов:**

   ```python
   # Статистика из PipelineMonitor
   - Обработано символов за цикл
   - Отправлено сигналов
   - Заблокировано фильтрами
   - Время выполнения цикла
   - Success rate фильтров
   ```

2. **Telegram доставка:**

   ```python
   # Статистика из EnhancedTelegramDelivery
   - Всего попыток отправки
   - Успешных отправок
   - Success rate (%)
   - Flood control блокировки
   - Таймауты
   - API ошибки
   ```

3. **Торговые метрики:**

   ```python
   # Из базы данных
   - Количество активных позиций
   - Общая экспозиция
   - PnL за период
   - Win Rate
   - Profit Factor
   - Max Drawdown
   ```

4. **Системные метрики:**
   ```python
   # Из monitoring/infra_metrics.py
   - Использование CPU
   - Использование памяти
   - Размер базы данных
   - Количество API запросов
   - Latency API запросов
   ```

**Проверка здоровья системы:**

```bash
# 1. Процесс запущен
ps aux | grep "python3 main.py" | grep -v grep

# 2. Нет ошибок в логах
tail -100 main.log | grep -i "error\|exception\|traceback" | tail -10

# 3. Сигналы генерируются
tail -200 main.log | grep -E "(сигнал|signal|SEND)" | tail -5

# 4. Telegram работает
tail -100 main.log | grep -E "(Telegram|bot)" | tail -5

# 5. База данных доступна
sqlite3 trading.db "SELECT COUNT(*) FROM signals_log WHERE created_at > datetime('now', '-1 hour');"

# 6. Позиции синхронизируются
sqlite3 trading.db "SELECT COUNT(*) FROM active_positions WHERE status='open';"
```

**Алерты и уведомления:**

```python
# Критические события отправляются в Telegram
- Ошибки открытия позиций
- Превышение лимитов риска
- Проблемы с API биржи
- Критические ошибки системы

# Через alert_system.py
await alert_system.send_critical_alert(
    message="Критическая ошибка",
    severity="HIGH"
)
```

**Dashboard (если включен):**

```python
# Web Dashboard на FastAPI
# Доступен по адресу: http://server:8000/dashboard

# Метрики:
- Активные позиции
- История сигналов
- Производительность
- Графики PnL
- Статистика фильтров
```

---

## 🔐 БЕЗОПАСНОСТЬ

### Шифрование:

- **API ключи:** Шифрование через `key_encryption.py`
- **Токены:** Хранение в `env.prod` / `env.dev`
- **База данных:** SQLite с WAL mode

### Доступ:

- **SSH:** Только для администраторов
- **Telegram:** Аутентификация через user_id
- **REST API:** (если включен) требует токен

**Детальная структура безопасности:**

**Шифрование API ключей:**

```python
# key_encryption.py
from cryptography.fernet import Fernet

class KeyEncryption:
    """
    Шифрование API ключей биржи

    Процесс:
    1. Генерация ключа шифрования (один раз)
    2. Шифрование API ключей при сохранении
    3. Расшифровка при использовании

    Хранение:
    - Ключ шифрования: ATRA_ENCRYPTION_KEY (в env файле)
    - Зашифрованные ключи: в базе данных (user_exchange_keys)
    """

    def encrypt_key(self, api_key: str) -> str:
        """Шифрование API ключа"""
        # Использует Fernet (симметричное шифрование)
        return encrypted_key

    def decrypt_key(self, encrypted_key: str) -> str:
        """Расшифровка API ключа"""
        return decrypted_key
```

**Защита токенов:**

```python
# Токены НИКОГДА не коммитятся в git
# .gitignore включает:
# - env.prod
# - env.dev
# - .env
# - *.key
# - *.pem

# Хранение:
# - env.prod: PROD токен
# - env.dev: DEV токен
# - Переменные окружения: приоритет над файлами
```

**Аутентификация пользователей:**

```python
# Telegram аутентификация
def is_authorized_user(user_id: int) -> bool:
    """
    Проверка авторизации пользователя

    Проверки:
    1. Пользователь существует в users_data
    2. Пользователь не заблокирован
    3. Проверка прав доступа (если есть)

    Возвращает:
    - True если пользователь авторизован
    - False если нет
    """
    user_data = db.get_user_data(user_id)
    if not user_data:
        return False

    # Дополнительные проверки
    if user_data.get('blocked', False):
        return False

    return True
```

**Защита от автоматического исполнения:**

```python
# В auto_execution.py
if ATRA_ENV != "prod":
    # КРИТИЧНО: DEV/TEST окружения НИКОГДА не открывают позиции
    logger.error("🚫 АВТО-ИСПОЛНЕНИЕ ЗАБЛОКИРОВАНО в %s окружении", ATRA_ENV)
    return False
```

**Валидация размера позиции:**

```python
# position_size_validator.py
class PositionSizeValidator:
    """
    Валидация размера позиции

    Проверки:
    1. Минимальный размер (0.0001)
    2. Максимальный размер (баланс * leverage)
    3. Риск не превышает лимит
    4. Общая экспозиция в пределах лимита

    Блокировка при:
    - Превышении максимального риска
    - Недостаточном балансе
    - Превышении лимита экспозиции
    """
```

**Аудит операций:**

```python
# order_audit_log.py
# Все операции логируются:
# - Открытие позиций
# - Закрытие позиций
# - Установка SL/TP
# - Изменение параметров

# Логирование:
await audit_log.log_order(
    order_type='market',
    symbol='BTCUSDT',
    side='BUY',
    amount=0.001,
    price=35050.0,
    status='filled',
    user_id=958930260,
    timestamp=datetime.now()
)
```

**Защита базы данных:**

```python
# WAL mode для конкурентного доступа
conn.execute("PRAGMA journal_mode=WAL")

# READONLY mode для dashboard
conn.execute("PRAGMA query_only=ON")

# Регулярные бэкапы
# Автоматические бэкапы каждые 24 часа
# Хранение в backups/ директории
```

**Ограничение доступа:**

```python
# SSH доступ только для администраторов
# Использование ключей SSH (рекомендуется)
# Ограничение IP адресов (если возможно)

# Telegram:
# - Проверка user_id перед выполнением команд
# - Ограничение команд по правам доступа

# REST API (если включен):
# - Требует токен аутентификации
# - Rate limiting
# - HTTPS только
```

---

## 📚 ДОПОЛНИТЕЛЬНАЯ ДОКУМЕНТАЦИЯ

- `docs/ARCHITECTURE_AUDIT_REPORT.md` — Аудит архитектуры
- `docs/COMPLETE_INTEGRATION_CHECKLIST.md` — Чеклист интеграции
- `docs/DEPLOYMENT_QUICK_START.md` — Быстрый старт
- `docs/FILTERS_LOGIC_AND_PARAMETERS.md` — Логика фильтров
- `docs/ML_LIGHTGBM_INTEGRATION_COMPLETE.md` — ML интеграция

---

## 🛠️ РАЗРАБОТКА

### Добавление нового фильтра:

1. Создать файл в `src/filters/`
2. Наследовать от `BaseFilter`
3. Реализовать метод `filter_signal()`
4. Добавить в `signal_live.py`

**Пример создания фильтра:**

```python
# src/filters/my_custom_filter.py
from src.filters.base import BaseFilter
from typing import Dict, Any, Optional
import pandas as pd

class MyCustomFilter(BaseFilter):
    """Мой кастомный фильтр"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.threshold = config.get('threshold', 0.5)

    async def filter_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        direction: str,
        **kwargs
    ) -> Optional[FilterResult]:
        """
        Фильтрация сигнала

        Args:
            df: DataFrame с данными
            symbol: Торговый символ
            direction: Направление (LONG/SHORT)

        Returns:
            FilterResult(passed=True) если сигнал проходит
            FilterResult(passed=False, reason="...") если блокирует
            None если фильтр не применим
        """
        # Ваша логика фильтрации
        if some_condition:
            return FilterResult(
                passed=True,
                reason="Custom filter passed"
            )
        else:
            return FilterResult(
                passed=False,
                reason="Custom filter blocked: condition not met"
            )
```

**Интеграция в signal_live.py:**

```python
# В функции _generate_signal_impl()

# Импорт фильтра
from src.filters.my_custom_filter import MyCustomFilter

# Инициализация
my_filter = MyCustomFilter(config.get('MY_CUSTOM_FILTER_CONFIG', {}))

# Применение фильтра
custom_result = await my_filter.filter_signal(
    df=df,
    symbol=symbol,
    direction=signal_type
)

if custom_result is None or not custom_result.passed:
    logger.debug("🚫 %s: MyCustomFilter заблокировал", symbol)
    return None, custom_result.reason if custom_result else "Custom filter failed"
```

### Добавление новой стратегии:

1. Создать файл в `src/strategies/`
2. Реализовать логику генерации
3. Интегрировать в `signal_live.py`

**Пример создания стратегии:**

```python
# src/strategies/my_strategy.py
from typing import Dict, Any, Optional, Tuple
import pandas as pd

async def generate_my_strategy_signal(
    df: pd.DataFrame,
    symbol: str,
    user_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Генерация сигнала по моей стратегии

    Returns:
        Dict с данными сигнала или None
    """
    # Ваша логика генерации
    if condition_for_long:
        return {
            "direction": "LONG",
            "entry_price": current_price,
            "confidence": 0.75,
            "pattern": "my_pattern"
        }
    elif condition_for_short:
        return {
            "direction": "SHORT",
            "entry_price": current_price,
            "confidence": 0.70,
            "pattern": "my_pattern"
        }
    return None
```

**Интеграция:**

```python
# В signal_live.py, функция _generate_signal_impl()

# Попытка генерации по новой стратегии
from src.strategies.my_strategy import generate_my_strategy_signal

my_signal = await generate_my_strategy_signal(df, symbol, user_data)
if my_signal:
    # Обработка сигнала
    signal_type = my_signal["direction"]
    signal_price = my_signal["entry_price"]
    # ... дальнейшая обработка
```

### Тестирование:

**Юнит-тесты:**

```bash
# Запуск всех юнит-тестов
pytest tests/unit/ -v

# Запуск конкретного теста
pytest tests/unit/test_filters.py::test_volume_filter -v

# С покрытием
pytest tests/unit/ --cov=src/filters --cov-report=html
```

**Интеграционные тесты:**

```bash
# Тесты интеграции с биржей (используют mock)
pytest tests/integration/ -v

# Тесты базы данных
pytest tests/integration/test_database.py -v
```

**Бэктест:**

```bash
# Бэктест одного символа
python3 backtest_cli.py --symbol BTCUSDT --days 30

# Бэктест портфеля
python3 backtest_cli.py --portfolio --days 90

# Бэктест с параметрами
python3 backtest_cli.py \
    --symbol ETHUSDT \
    --days 60 \
    --risk 2.0 \
    --leverage 3
```

**Smoke тесты:**

```bash
# Тест открытия/закрытия позиций (на тестовой бирже)
python3 scripts/live_smoke_test_tp_sl.py

# Тест фильтров
python3 scripts/diagnostic_test_filters.py
```

**Пример юнит-теста:**

```python
# tests/unit/test_volume_filter.py
import pytest
from src.filters.volume_imbalance import VolumeImbalanceFilter
import pandas as pd

def test_volume_filter_passes():
    """Тест прохождения фильтра"""
    filter_instance = VolumeImbalanceFilter({
        'min_volume_ratio': 1.2,
        'require_volume_confirmation': True
    })

    # Создаем тестовые данные
    df = pd.DataFrame({
        'volume': [100, 150, 200, 180],  # Объем выше среднего
        'close': [100, 101, 102, 103]
    })

    result = await filter_instance.filter_signal(
        df=df,
        symbol="BTCUSDT",
        direction="LONG"
    )

    assert result is not None
    assert result.passed == True
```

### Отладка:

**Логирование:**

```python
# Включение DEBUG логирования
import logging
logging.basicConfig(level=logging.DEBUG)

# Логирование конкретного модуля
logger = logging.getLogger('signal_live')
logger.setLevel(logging.DEBUG)
```

**Трассировка:**

```python
# Использование tracer для отладки
from observability.tracing import get_tracer

tracer = get_tracer()
trace = tracer.start(
    agent="my_module",
    mission="debug_signal",
    metadata={"symbol": "BTCUSDT"}
)

trace.record(step="think", name="analysis", metadata={"result": "..."})
trace.record(step="act", name="action", status="success")
```

**Проверка состояния:**

```python
# Проверка данных пользователя
from db import Database
db = Database()
user_data = db.get_user_data(user_id=958930260)
print(user_data)

# Проверка сигналов
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.execute(
    "SELECT * FROM signals_log ORDER BY created_at DESC LIMIT 5"
)
for row in cursor.fetchall():
    print(row)
```

---

## 📝 ЗАМЕТКИ

- Система поддерживает **два режима**: DEV (ручной) и PROD (автоматический)
- Сигналы отправляются в **оба бота** одновременно
- Используется **адаптивная система** фильтров с ML оптимизацией
- Поддерживается **множество бирж** с fallback механизмом
- Система **масштабируема** для множественных пользователей

**Важные особенности:**

1. **Два режима работы:**
   - **DEV**: Ручной режим, сигналы только для информации
   - **PROD**: Автоматический режим, позиции открываются автоматически
   - Сигналы приходят в оба бота одновременно

2. **Адаптивная система:**
   - ML оптимизация параметров фильтров
   - Адаптация под рыночные условия
   - Непрерывное обучение на исторических данных

3. **Надежность:**
   - Fallback механизмы для всех критических компонентов
   - Graceful degradation при сбоях
   - Автоматическое восстановление

4. **Масштабируемость:**
   - Поддержка множественных пользователей
   - Параллельная обработка символов
   - Эффективное использование ресурсов

---

## 🔧 TROUBLESHOOTING

### Частые проблемы и решения:

**1. Сигналы не генерируются:**

**Диагностика:**

```bash
# Проверка логов
tail -200 main.log | grep -E "(NO SIGNAL|блокирован|BLOCK)"

# Проверка фильтров
tail -200 main.log | grep -E "(фильтр|filter)" | tail -20

# Проверка данных
python3 -c "
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.execute('SELECT COUNT(*) FROM signals_log WHERE created_at > datetime(\"now\", \"-1 hour\")')
print(f'Сигналов за последний час: {cursor.fetchone()[0]}')
"
```

**Возможные причины:**

- Фильтры слишком строгие (RSI, Volume, Trend)
- Рынок в боковике (нет четкого тренда)
- Проблемы с получением данных (API недоступен)

**Решение:**

- Проверить настройки фильтров в `config.py`
- Временно ослабить фильтры для тестирования
- Проверить доступность API бирж

---

**2. Сигналы не отправляются в Telegram:**

**Диагностика:**

```bash
# Проверка токена
python3 -c "import config; print(f'TOKEN: {config.TOKEN[:20] if config.TOKEN else None}...')"

# Проверка логов отправки
tail -200 main.log | grep -E "(отправлен|SEND|Telegram)" | tail -20

# Проверка процесса
ps aux | grep "python3 main.py" | grep -v grep
```

**Возможные причины:**

- Неправильный токен (DEV вместо PROD)
- Telegram API недоступен
- Flood Control блокировка
- Ошибка в коде отправки

**Решение:**

- Проверить `env.prod` и `env.dev` файлы
- Проверить переменную `ATRA_ENV`
- Подождать снятия Flood Control (обычно 1-10 минут)
- Проверить логи на ошибки

---

**3. Позиции не открываются автоматически:**

**Диагностика:**

```bash
# Проверка окружения
python3 -c "import config; print(f'ATRA_ENV: {config.ATRA_ENV}')"

# Проверка логов автоисполнения
tail -200 main.log | grep -E "(AUTO|auto_exec)" | tail -20

# Проверка статуса сигналов
sqlite3 trading.db "SELECT symbol, status FROM accepted_signals WHERE status='pending' LIMIT 5;"
```

**Возможные причины:**

- `ATRA_ENV != "prod"` (автоисполнение только в PROD)
- Сигнал не был отправлен в Telegram
- Ошибка при открытии позиции на бирже
- Недостаточный баланс

**Решение:**

- Убедиться что `ATRA_ENV=prod` в `env.prod`
- Проверить что сигнал успешно отправлен
- Проверить баланс пользователя
- Проверить логи `auto_execution.py`

---

**4. SL не переносится в безубыток:**

**Диагностика:**

```bash
# Проверка активных позиций
sqlite3 trading.db "SELECT symbol, entry_price, tp1_price, sl_price FROM active_positions WHERE status='open';"

# Проверка логов trailing stop
tail -200 main.log | grep -E "(TRAILING|SL→BE)" | tail -20
```

**Возможные причины:**

- Позиция не достигла 50% пути к TP1
- Trailing stop не инициализирован
- Ошибка при обновлении SL на бирже
- Нет данных OHLC для адаптивной логики

**Решение:**

- Проверить прогресс позиции к TP1
- Убедиться что trailing stop инициализирован
- Проверить доступность API биржи
- Проверить логи на ошибки

---

**5. База данных заблокирована:**

**Диагностика:**

```bash
# Проверка блокировок
sqlite3 trading.db "PRAGMA database_list;"

# Проверка процессов
lsof trading.db 2>/dev/null
```

**Возможные причины:**

- Несколько процессов используют БД одновременно
- WAL файл поврежден
- БД в режиме exclusive lock

**Решение:**

```bash
# Остановка всех процессов
pkill -f "python3 main.py"

# Проверка WAL файла
ls -la trading.db-wal

# Восстановление (если нужно)
sqlite3 trading.db "PRAGMA integrity_check;"
```

---

**6. Высокое использование памяти:**

**Диагностика:**

```bash
# Проверка использования памяти
ps aux | grep "python3 main.py" | awk '{print $6/1024 " MB"}'

# Проверка утечек памяти
# (требует профилирования)
```

**Возможные причины:**

- Накопление данных в кэше
- Утечки памяти в циклах
- Большое количество открытых соединений

**Решение:**

- Очистка кэша
- Перезапуск процесса
- Оптимизация кода (освобождение ресурсов)

---

**7. API биржи недоступен:**

**Диагностика:**

```bash
# Проверка доступности API
curl -s https://api.binance.com/api/v3/ping

# Проверка rate limits
tail -200 main.log | grep -E "(rate limit|429)" | tail -10
```

**Возможные причины:**

- Превышение rate limits
- Временная недоступность API
- Проблемы с сетью

**Решение:**

- Использование fallback бирж (автоматически)
- Ожидание снятия rate limit
- Проверка сетевого соединения

---

## 📚 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ

### Полезные команды:

```bash
# Проверка статуса системы
ps aux | grep "python3 main.py"
tail -50 main.log

# Проверка последних сигналов
sqlite3 trading.db "SELECT symbol, direction, created_at FROM signals_log ORDER BY created_at DESC LIMIT 10;"

# Проверка активных позиций
sqlite3 trading.db "SELECT symbol, direction, entry_price, status FROM active_positions WHERE status='open';"

# Проверка пользователей
sqlite3 trading.db "SELECT user_id, trade_mode, leverage, risk_pct FROM users_data;"

# Очистка старых логов
find logs/ -name "*.log" -mtime +7 -delete

# Бэкап базы данных
cp trading.db backups/trading.db_$(date +%Y%m%d_%H%M%S)
```

### Контакты и поддержка:

- **Сервер:** `185.177.216.15`
- **Логи:** `/root/atra/main.log`
- **База данных:** `/root/atra/trading.db`

---

**Последнее обновление:** 2025-11-19  
**Версия документа:** 2.0  
**Автор:** ATRA Development Team
