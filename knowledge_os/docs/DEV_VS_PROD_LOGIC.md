# 📊 СРАВНЕНИЕ: Логика работы DEV vs PROD

## ✅ ОДИНАКОВАЯ ЛОГИКА

DEV и PROD боты используют **одинаковую логику** для:

### 1. Генерация сигналов

- ✅ Одинаковые условия входа (EMA crossover, Bollinger Bands, etc.)
- ✅ Одинаковые фильтры (BTC trend, RSI, Volume, Anomaly, etc.)
- ✅ Одинаковые параметры стратегии (TP/SL, leverage, risk)
- ✅ Одинаковые технические индикаторы
- ✅ Одинаковая логика выхода (TP1, TP2, SL, trailing stop)

### 2. Фильтры и проверки

- ✅ BTC/ETH/SOL trend filters
- ✅ RSI фильтры
- ✅ Volume фильтры
- ✅ Anomaly detection
- ✅ Новые фильтры (Dominance, Interest Zone, Fibonacci, Volume Imbalance)
- ✅ Pullback Entry Logic
- ✅ Adaptive Strategy

### 3. Параметры стратегии

- ✅ TP1/TP2/SL проценты
- ✅ Leverage настройки
- ✅ Risk management
- ✅ Position sizing
- ✅ Trailing stop логика

### 4. База данных

- ✅ Одинаковая структура БД
- ✅ Одинаковые таблицы (signals_log, accepted_signals, active_positions)
- ⚠️ **НО**: Могут использовать разные файлы БД (если настроено)

## ❌ РАЗЛИЧИЯ

### 1. Telegram токен

**DEV:**

```python
ATRA_ENV = "dev"
TOKEN = TELEGRAM_TOKEN_DEV  # 8141444679 (@piu_piu_dev_bot)
```

**PROD:**

```python
ATRA_ENV = "prod"
TOKEN = TELEGRAM_TOKEN  # 8156844481 (@PiuX_Trade_bot)
```

**Код:** `config.py` (строки 166-173)

### 2. Уровень логирования

**DEV:**

```python
logging.DEBUG  # Подробные логи, все сообщения
```

**PROD:**

```python
logging.INFO  # Только важные сообщения
```

**Код:** `main.py` (строки 233, 243)

### 3. Авто-исполнение

**DEV:**

- ❌ **ВСЕГДА manual** (блокируется независимо от настроек пользователя)
- Сигналы отправляются, но позиции НЕ открываются автоматически
- Пользователь должен нажать `/accept` для открытия позиции

**PROD:**

- ✅ Зависит от настроек пользователя в БД (`trade_mode: auto/manual`)
- Если `auto` → позиция открывается автоматически
- Если `manual` → пользователь должен нажать `/accept`

**Код:**

- `signal_live.py` (строка 4220): `if ATRA_ENV != "prod": return`
- `auto_execution.py` (строка 52): `if ATRA_ENV != "prod": return False`

## 📋 ПРОВЕРКА В КОДЕ

### Выбор токена

```python
# config.py
ATRA_ENV = os.getenv("ATRA_ENV", "dev").lower().strip()
TOKEN = (
    TELEGRAM_TOKEN if ATRA_ENV == "prod" else (
        TELEGRAM_TOKEN_DEV or TELEGRAM_TOKEN
    )
)
```

### Уровень логирования

```python
# main.py
_root_logger.setLevel(logging.DEBUG if ATRA_ENV != "prod" else logging.INFO)
_stream_handler.setLevel(logging.DEBUG if ATRA_ENV != "prod" else logging.INFO)
```

### Блокировка авто-исполнения в DEV

```python
# signal_live.py (строка 4220)
if ATRA_ENV != "prod":
    logger.info("⏭️ [AUTO] %s: окружение=%s, авто-исполнение отключено", symbol, ATRA_ENV)
    return

# auto_execution.py (строка 52)
if ATRA_ENV != "prod":
    logger.error("🚫 [AUTO BLOCKED] %s: АВТО-ИСПОЛНЕНИЕ ЗАБЛОКИРОВАНО!", symbol)
    return False
```

## 🎯 ВЫВОД

**Логика генерации сигналов полностью одинаковая** для DEV и PROD.

**Различия только в:**

1. Telegram токен (куда отправляются сигналы)
2. Уровень логирования (детальность логов)
3. Авто-исполнение (DEV всегда manual, PROD зависит от настроек)

Это означает, что:

- ✅ Сигналы в DEV и PROD будут **одинакового качества**
- ✅ Фильтры работают **одинаково**
- ✅ Параметры стратегии **одинаковые**
- ⚠️ Но сигналы идут в **разные Telegram боты**
- ⚠️ DEV бот **не открывает позиции автоматически**

## 🔍 ПРОВЕРКА НА СЕРВЕРЕ

Чтобы убедиться, что логика одинаковая:

```bash
# Проверить, что используется один и тот же код
cd /root/atra
git log --oneline -1

# Проверить, что нет различий в параметрах
grep -E "TP1|TP2|SL|leverage" config.py | head -10
```

## ⚠️ ВАЖНО

Если на сервере запущены оба бота (DEV и PROD), они должны:

- ✅ Использовать **один и тот же код** (из одного репозитория)
- ✅ Иметь **разные ATRA_ENV** (dev vs prod)
- ✅ Использовать **разные токены** (DEV vs PROD)
- ✅ Использовать **разные базы данных** (если настроено)

Но **логика генерации сигналов будет одинаковой** для обоих.
