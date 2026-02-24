# ПЛАН ЗАВЕРШЕНИЯ СИСТЕМЫ

## 🎯 **ПРОБЛЕМА**

Система неполная - многие функции созданы, но не интегрированы в основной поток работы.

**Найдено 9 пустых таблиц из 24 - это критично!**

## 📊 **ТЕКУЩИЙ СТАТУС**

### ✅ **Что работает:**

- **`quotes`: 11 записей** (исправлено!)
- **`signals_log`: 36 записей** (основные сигналы)
- **`active_signals`: 28 записей** (активные сигналы)
- **`telemetry_api`: 7204 записей** (телеметрия)

### ❌ **Что НЕ работает (9 таблиц):**

1. **`signals: 0 записей`** - КРИТИЧНО!
2. **`arbitrage_events: 0 записей`** - упущенная прибыль
3. **`manual_trades: 0 записей`** - нет ручной торговли
4. **`signal_accum_events: 0 записей`** - нет анализа трендов
5. **`market_cap_blacklist: 0 записей`** - нет фильтрации
6. **`backtest_results: 0 записей`** - нет тестирования
7. **`pending_check: 0 записей`** - нет мониторинга
8. **`audit_strategy_pauses: 0 записей`** - нет аудита
9. **`audit_soft_blocklist: 0 записей`** - нет фильтрации
10. **`audit_active_coins: 0 записей`** - нет мониторинга

## 🔧 **ПЛАН ИСПРАВЛЕНИЯ**

### **ЭТАП 1: КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ**

#### **1.1 Исправить сохранение торговых сигналов**

**Файл:** `signal_live.py` (после строки 9645)
**Действие:** Добавить код сохранения в таблицу `signals`

```python
# Сохраняем сигнал в таблицу signals с техническими индикаторами
try:
    # Вычисляем RSI и EMA индикаторы
    import ta
    import pandas as pd

    if len(df) >= 14:  # Минимум для RSI
        # RSI
        rsi_indicator = ta.momentum.RSIIndicator(df['close'], window=14)
        rsi_value = rsi_indicator.rsi().iloc[-1]

        # EMA Fast (7 периодов)
        ema_fast_indicator = ta.trend.EMAIndicator(df['close'], window=7)
        ema_fast_value = ema_fast_indicator.ema_indicator().iloc[-1]

        # EMA Slow (25 периодов)
        ema_slow_indicator = ta.trend.EMAIndicator(df['close'], window=25)
        ema_slow_value = ema_slow_indicator.ema_indicator().iloc[-1]

        # Сохраняем в таблицу signals
        signal_data = {
            "exchange": "binance",
            "symbol": symbol,
            "rsi": float(rsi_value) if not pd.isna(rsi_value) else 50.0,
            "ema_fast": float(ema_fast_value) if not pd.isna(ema_fast_value) else float(signal_price),
            "ema_slow": float(ema_slow_value) if not pd.isna(ema_slow_value) else float(signal_price),
            "price": float(signal_price)
        }

        db.insert_signal(signal_data)
        logging.info(f"✅ Сигнал сохранен в БД: {symbol} (RSI: {rsi_value:.2f})")
    else:
        logging.warning(f"⚠️ Недостаточно данных для расчета индикаторов: {symbol}")

except Exception as e:
    logging.error(f"❌ Ошибка сохранения сигнала в БД: {e}")
```

#### **1.2 Включить систему арбитража**

**Файл:** `signal_live.py` (добавить новую функцию)
**Действие:** Создать функцию проверки арбитража

```python
async def check_arbitrage_opportunities():
    """Проверяет арбитражные возможности между биржами"""
    try:
        from exchanges.binance_api import BinanceAPI
        from exchanges.mexc_api import MEXCAPI

        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT"]

        binance_prices = await BinanceAPI.get_prices(symbols)
        mexc_prices = await MEXCAPI.get_prices(symbols)

        for symbol in symbols:
            if symbol in binance_prices and symbol in mexc_prices:
                binance_bid = binance_prices[symbol]["bid"]
                binance_ask = binance_prices[symbol]["ask"]
                mexc_bid = mexc_prices[symbol]["bid"]
                mexc_ask = mexc_prices[symbol]["ask"]

                # Проверяем арбитражные возможности
                profit_binance_mexc = (mexc_bid - binance_ask) / binance_ask * 100
                profit_mexc_binance = (binance_bid - mexc_ask) / mexc_ask * 100

                min_profit = 0.5  # Минимальная прибыль 0.5%

                if profit_binance_mexc > min_profit:
                    db.save_arbitrage_event(
                        symbol=symbol,
                        buy_exchange="binance",
                        sell_exchange="mexc",
                        buy_price=binance_ask,
                        sell_price=mexc_bid,
                        amount=1000,
                        net_profit=profit_binance_mexc,
                        net_profit_pct=profit_binance_mexc
                    )
                    logging.info(f"💰 Арбитраж найден: {symbol} - прибыль {profit_binance_mexc:.2f}%")

    except Exception as e:
        logging.error(f"❌ Ошибка проверки арбитража: {e}")
```

### **ЭТАП 2: СИСТЕМЫ ТОРГОВЛИ**

#### **2.1 Создать систему ручной торговли**

**Файл:** `manual_trading.py` (создать новый)
**Действие:** Создать интерфейс ручной торговли

```python
def save_manual_trade(trade_data):
    """Сохраняет ручную сделку"""
    try:
        db.cursor.execute("""
            INSERT INTO manual_trades (
                ts, symbol, buy_exchange, sell_exchange, buy_price, sell_price,
                amount, notified_profit, notified_profit_pct, withdraw_fee,
                final_profit, final_profit_pct, status, real_buy_price,
                real_sell_price, real_amount, real_profit, real_profit_pct,
                trade_completed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_data.get('timestamp', datetime.utcnow().isoformat()),
            trade_data.get('symbol'),
            trade_data.get('buy_exchange'),
            trade_data.get('sell_exchange'),
            trade_data.get('buy_price'),
            trade_data.get('sell_price'),
            trade_data.get('amount'),
            trade_data.get('notified_profit'),
            trade_data.get('notified_profit_pct'),
            trade_data.get('withdraw_fee'),
            trade_data.get('final_profit'),
            trade_data.get('final_profit_pct'),
            trade_data.get('status', 'pending'),
            trade_data.get('real_buy_price'),
            trade_data.get('real_sell_price'),
            trade_data.get('real_amount'),
            trade_data.get('real_profit'),
            trade_data.get('real_profit_pct'),
            trade_data.get('trade_completed', 0)
        ))
        db.conn.commit()
        logging.info(f"✅ Ручная сделка сохранена: {trade_data.get('symbol')}")
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения ручной сделки: {e}")
```

### **ЭТАП 3: СИСТЕМЫ АУДИТА И МОНИТОРИНГА**

#### **3.1 Включить все системы аудита**

**Файл:** `audit_systems.py` (создать новый)
**Действие:** Создать все функции аудита

```python
def log_strategy_pause(action, reason, window_hours=24, sl_count=0, net_profit_sum=0.0):
    """Логирует паузы стратегии"""
    try:
        db.cursor.execute("""
            INSERT INTO audit_strategy_pauses (ts, action, reason, window_hours, sl_count, net_profit_sum)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            action,
            reason,
            window_hours,
            sl_count,
            net_profit_sum
        ))
        db.conn.commit()
        logging.info(f"📊 Аудит паузы стратегии: {action} - {reason}")
    except Exception as e:
        logging.error(f"❌ Ошибка аудита паузы стратегии: {e}")

def log_soft_blocklist(action, symbol, votes=0, reason=""):
    """Логирует мягкий блэклист"""
    try:
        db.cursor.execute("""
            INSERT INTO audit_soft_blocklist (ts, action, symbol, votes, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            action,
            symbol,
            votes,
            reason
        ))
        db.conn.commit()
        logging.info(f"📊 Аудит мягкого блэклиста: {action} - {symbol}")
    except Exception as e:
        logging.error(f"❌ Ошибка аудита мягкого блэклиста: {e}")

def log_active_coin(action, symbol, note=""):
    """Логирует активные монеты"""
    try:
        db.cursor.execute("""
            INSERT INTO audit_active_coins (ts, action, symbol, note)
            VALUES (?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            action,
            symbol,
            note
        ))
        db.conn.commit()
        logging.info(f"📊 Аудит активных монет: {action} - {symbol}")
    except Exception as e:
        logging.error(f"❌ Ошибка аудита активных монет: {e}")

def add_to_market_cap_blacklist(symbol, market_cap, reason=""):
    """Добавляет в черный список по капитализации"""
    try:
        db.cursor.execute("""
            INSERT INTO market_cap_blacklist (symbol, market_cap, blacklisted_at, reason)
            VALUES (?, ?, ?, ?)
        """, (
            symbol,
            market_cap,
            datetime.utcnow().isoformat(),
            reason
        ))
        db.conn.commit()
        logging.info(f"📊 Добавлено в черный список по капитализации: {symbol}")
    except Exception as e:
        logging.error(f"❌ Ошибка добавления в черный список: {e}")
```

### **ЭТАП 4: ИНТЕГРАЦИЯ В ОСНОВНОЙ ЦИКЛ**

#### **4.1 Интегрировать в main.py**

**Файл:** `main.py`
**Действие:** Добавить вызовы всех систем в основной цикл

```python
# В основной цикл добавить:
async def main():
    # ... существующий код ...

    # Добавляем проверку арбитража
    arbitrage_task = asyncio.create_task(check_arbitrage_opportunities())
    tasks.append(arbitrage_task)

    # Добавляем системы аудита
    audit_task = asyncio.create_task(run_audit_systems())
    tasks.append(audit_task)

    # ... остальной код ...
```

## 🎯 **ПРИОРИТЕТЫ ИСПРАВЛЕНИЯ**

### **КРИТИЧНО (сделать в первую очередь):**

1. **Исправить сохранение сигналов** - добавить код в signal_live.py
2. **Включить систему арбитража** - создать функцию проверки
3. **Создать систему ручной торговли** - интерфейс для пользователей

### **ВАЖНО (сделать во вторую очередь):**

4. **Включить все системы аудита** - мониторинг и логирование
5. **Создать систему накопления событий** - анализ трендов
6. **Включить фильтрацию по капитализации** - улучшение качества сигналов

### **ЖЕЛАТЕЛЬНО (сделать в третью очередь):**

7. **Включить систему бэктестов** - тестирование стратегий
8. **Создать систему проверок** - мониторинг состояния
9. **Интегрировать все в основной цикл** - автоматизация

## 📈 **ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ**

После исправления:

- **`signals`** - будет заполняться торговыми сигналами с техническими индикаторами
- **`arbitrage_events`** - будет отслеживать арбитражные возможности
- **`manual_trades`** - будет сохранять ручные сделки пользователей
- **Все системы аудита** - будут работать и мониторить систему
- **Полная интеграция** - все компоненты будут работать вместе

## 🎯 **ЗАКЛЮЧЕНИЕ**

**СИСТЕМА НЕПОЛНАЯ И ТРЕБУЕТ ЗАВЕРШЕНИЯ!**

Нужно:

1. **Исправить критические проблемы** (signals, arbitrage)
2. **Создать недостающие системы** (manual trading, audit)
3. **Интегрировать все компоненты** в основной поток
4. **Протестировать все функции**

**После исправления система станет полноценной и будет работать на 100%!**
