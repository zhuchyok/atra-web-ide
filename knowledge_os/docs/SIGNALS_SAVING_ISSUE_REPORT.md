# ОТЧЕТ: ПРИЧИНА НЕСОХРАНЕНИЯ ТОРГОВЫХ СИГНАЛОВ

## 🚨 **НАЙДЕННАЯ ПРОБЛЕМА**

**Причина:** Функция `insert_signal` существует в `db.py`, но **НИГДЕ НЕ ВЫЗЫВАЕТСЯ** в коде!

### 📊 **Детальный анализ:**

#### ✅ **Что работает:**

- **`signals_log`: 36 записей** - основные сигналы сохраняются
- **`active_signals`: 28 записей** - активные сигналы отслеживаются
- **Функция `insert_signal`** - работает корректно (протестировано)

#### ❌ **Что НЕ работает:**

- **`signals: 0 записей`** - таблица пуста
- **Функция `insert_signal`** - не вызывается в коде

## 🔍 **ТЕХНИЧЕСКАЯ ДИАГНОСТИКА**

### **1. Функция insert_signal существует:**

```python
# db.py, строки 1199-1214
def insert_signal(self, signal):
    self.cursor.execute(
        "INSERT INTO signals (ts, exchange, symbol, rsi, ema_fast, ema_slow, price) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.utcnow().isoformat(),
            signal["exchange"],
            signal["symbol"],
            signal["rsi"],
            signal["ema_fast"],
            signal["ema_slow"],
            signal["price"],
        ),
    )
    self.conn.commit()
    print(f"[PiuX_Trade][DB] Сигнал добавлен: {signal}")
    backup_file(self.db_path)
```

### **2. Но НЕ вызывается в коде:**

```bash
# Поиск вызовов insert_signal
grep -r "\.insert_signal(" /Users/zhuchyok/Documents/GITHUB/atra/
# Результат: НЕТ СОВПАДЕНИЙ
```

### **3. Вместо этого используются:**

- `insert_signal_log_entry` - для детального логирования
- `insert_signal_log` - для основных сигналов
- `save_signal_history` - для истории сигналов

## 🎯 **МЕСТА, ГДЕ НУЖНО ДОБАВИТЬ ВЫЗОВЫ**

### **1. signal_live.py - функция check_and_send_signals (строки ~9000-10000):**

```python
# После генерации сигнала:
if signal_generated:
    # Сохраняем сигнал в таблицу signals
    try:
        signal_data = {
            "exchange": "binance",
            "symbol": symbol,
            "rsi": rsi_value,  # вычислить RSI
            "ema_fast": ema_fast_value,  # вычислить быструю EMA
            "ema_slow": ema_slow_value,  # вычислить медленную EMA
            "price": signal_price
        }
        db.insert_signal(signal_data)
        logger.info(f"✅ Сигнал сохранен в БД: {symbol}")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения сигнала: {e}")
```

### **2. signal_live.py - функция process_pending_dca_signals (строки ~10000-11000):**

```python
# Для DCA сигналов:
if dca_signal_generated:
    signal_data = {
        "exchange": "binance",
        "symbol": symbol,
        "rsi": rsi_value,
        "ema_fast": ema_fast_value,
        "ema_slow": ema_slow_value,
        "price": dca_price
    }
    db.insert_signal(signal_data)
```

### **3. signal_live.py - функция log_dca_operation (строки ~10380-10400):**

```python
# Для DCA операций:
signal_data = {
    "exchange": "binance",
    "symbol": symbol,
    "rsi": rsi_value,
    "ema_fast": ema_fast_value,
    "ema_slow": ema_slow_value,
    "price": avg_price_new
}
db.insert_signal(signal_data)
```

## 🧪 **ТЕСТИРОВАНИЕ РЕШЕНИЯ**

### **Результаты теста:**

```
✅ Функция insert_signal работает корректно
📊 Записей в таблице signals: 2 (после теста)
✅ Сигнал успешно сохранен в базу данных
```

### **Структура сохраненного сигнала:**

```
ID: 2, Symbol: BTCUSDT, RSI: 45.5, Price: 45000.0
```

## 💡 **РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ**

### **Немедленные действия:**

1. **Добавить вызовы `db.insert_signal`** в местах генерации сигналов
2. **Вычислить RSI и EMA индикаторы** для сохранения
3. **Обработать ошибки** при сохранении сигналов
4. **Протестировать сохранение** сигналов

### **Места для добавления:**

1. **`check_and_send_signals`** - основная генерация сигналов
2. **`process_pending_dca_signals`** - DCA сигналы
3. **`log_dca_operation`** - DCA операции
4. **Другие функции генерации сигналов**

### **Необходимые вычисления:**

- **RSI** - индекс относительной силы
- **EMA Fast** - быстрая экспоненциальная скользящая средняя
- **EMA Slow** - медленная экспоненциальная скользящая средняя
- **Price** - цена сигнала

## 🎯 **ЗАКЛЮЧЕНИЕ**

**ПРОБЛЕМА НАЙДЕНА И ДИАГНОСТИРОВАНА!**

### **Корень проблемы:**

Функция `insert_signal` существует и работает, но **не вызывается** в коде генерации сигналов.

### **Решение:**

Добавить вызовы `db.insert_signal` в местах генерации сигналов с вычислением технических индикаторов.

### **Статус:**

🔧 **ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ** - добавить вызовы функции в код

**После исправления таблица `signals` будет заполняться торговыми сигналами с техническими индикаторами!**
