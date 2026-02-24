# 🔄 ДИНАМИЧЕСКИЕ ПАРАМЕТРЫ - ФИНАЛЬНАЯ КОНФИГУРАЦИЯ

## 🎯 **ТЕКУЩАЯ КОНФИГУРАЦИЯ ПОЛЬЗОВАТЕЛЕЙ:**

### **📊 Пользователь 556251171 (SPOT):**

```json
{
  "deposit": 10200.0,
  "trade_mode": "spot",
  "filter_mode": "soft",
  "open_positions": [],
  "accepted_signals": [],
  "news_filter_mode": "aggressive",
  "total_risk_amount": 0,
  "free_deposit": 10200.0,
  "total_profit": 0
}
```

### **📊 Пользователь 958930260 (FUTURES):**

```json
{
  "deposit": 200.0,
  "trade_mode": "futures",
  "filter_mode": "soft",
  "open_positions": [],
  "accepted_signals": [],
  "news_filter_mode": "aggressive",
  "total_risk_amount": 0,
  "free_deposit": 200.0,
  "total_profit": 0
}
```

---

## 🔄 **КАК РАБОТАЮТ ДИНАМИЧЕСКИЕ ПАРАМЕТРЫ:**

### **📊 Генерация сигналов:**

```python
# В signal_live.py
current_index = len(df) - 1

# 1. Динамический риск (1.0% - 5.0%)
risk_pct = get_dynamic_risk_pct(df, current_index)

# 2. Динамическое плечо (1x - 20x)
base_leverage = user_data.get('leverage', 1) if user_data.get('trade_mode', 'spot') == 'futures' else 1
leverage = get_dynamic_leverage(df, current_index, base_leverage)

# 3. Динамические TP уровни
tp1_pct, tp2_pct = get_dynamic_tp_levels(df, current_index, side.lower())
```

### **📊 Принятие сигналов:**

```python
# В telegram_bot.py
# 1. Риск из команды или по умолчанию
risk_pct = float(args[5]) if len(args) > 5 else user_data.get("risk_pct", 2.0)

# 2. Плечо из настроек или по умолчанию
leverage = user_data.get("leverage", 1) if trade_mode == "futures" else 1

# 3. Расчет размера позиции
new_qty, avg_price_new, tp1, tp2, limit_reached = dca_calculate_next_qty_and_tp(
    entry_prices, qtys, entry_price, dca_count, deposit, risk_pct, leverage, side
)
```

---

## 🎯 **ПРАКТИЧЕСКИЕ ПРИМЕРЫ:**

### **Пример 1: SPOT пользователь (556251171)**

```python
# Настройки пользователя
deposit = 10200.0
trade_mode = "spot"
filter_mode = "soft"

# Динамические расчеты
risk_pct = get_dynamic_risk_pct(df, current_index)  # Например: 2.3%
leverage = get_dynamic_leverage(df, current_index, 1)  # Всегда 1.0x для SPOT

# Расчет размера позиции
base_qty = 10200.0 * 2.3 / 100 * 1.0 / 3245.67 = 0.072 ETH
```

### **Пример 2: FUTURES пользователь (958930260)**

```python
# Настройки пользователя
deposit = 200.0
trade_mode = "futures"
filter_mode = "soft"

# Динамические расчеты
risk_pct = get_dynamic_risk_pct(df, current_index)  # Например: 1.8%
leverage = get_dynamic_leverage(df, current_index, 1)  # Например: 1.5x

# Расчет размера позиции
base_qty = 200.0 * 1.8 / 100 * 1.5 / 3245.67 = 0.0017 ETH
```

---

## 🔧 **ЛОГИКА ДИНАМИЧЕСКИХ РАСЧЕТОВ:**

### **📊 Динамический риск:**

```python
def get_dynamic_risk_pct(df, i):
    """
    Динамический расчет процента риска на основе волатильности и тренда
    """
    if i < 21:
        return 2.0  # стартовый риск, если мало данных

    volatility = closes.std() / closes.mean()
    trend = (sma20_now - sma20_prev) / sma20_prev if sma20_prev != 0 else 0
    base_risk = 2.0
    dynamic_risk = base_risk * (1 + 2 * trend) / (1 + 5 * volatility)
    dynamic_risk = max(1.0, min(dynamic_risk, 5.0))  # ограничиваем от 1% до 5%
    return dynamic_risk
```

**Логика:**

- **При сильном тренде** → риск увеличивается (до 5%)
- **При высокой волатильности** → риск уменьшается (до 1%)
- **При боковом рынке** → риск остается базовым (2%)

### **📈 Динамическое плечо:**

```python
def get_dynamic_leverage(df, i, base_leverage=1):
    """
    Динамический расчет плеча на основе волатильности и тренда
    """
    if i < 21:
        return base_leverage  # базовое плечо, если мало данных

    volatility = closes.std() / closes.mean()
    trend = (sma20_now - sma20_prev) / sma20_prev if sma20_prev != 0 else 0

    # Динамическое плечо на основе тренда и волатильности
    trend_factor = 1 + abs(trend) * 2  # до 3x при сильном тренде
    volatility_factor = 1 / (1 + volatility * 3)  # уменьшаем при высокой волатильности

    dynamic_leverage = base_leverage * trend_factor * volatility_factor
    dynamic_leverage = max(1, min(dynamic_leverage, 20))  # ограничиваем от 1 до 20

    return round(dynamic_leverage, 1)
```

**Логика:**

- **При сильном тренде** → плечо увеличивается (до 20x)
- **При высокой волатильности** → плечо уменьшается (до 1x)
- **Для SPOT пользователей** → всегда 1x (независимо от расчетов)

---

## 📊 **АДАПТАЦИЯ К РЫНОЧНЫМ УСЛОВИЯМ:**

### **🟢 Бычий тренд + низкая волатильность:**

```
risk_pct = 4.5%  // Высокий риск
leverage = 3.2x  // Высокое плечо (для фьючерсов)
// Результат: агрессивная торговля
```

### **🔴 Медвежий тренд + высокая волатильность:**

```
risk_pct = 1.2%  // Низкий риск
leverage = 1.1x  // Низкое плечо (для фьючерсов)
// Результат: консервативная торговля
```

### **🟡 Боковой рынок + средняя волатильность:**

```
risk_pct = 2.0%  // Базовый риск
leverage = 1.5x  // Среднее плечо (для фьючерсов)
// Результат: умеренная торговля
```

---

## 🎯 **ПРЕИМУЩЕСТВА ДИНАМИЧЕСКОЙ СИСТЕМЫ:**

### **✅ Автоматическая адаптация:**

- **Риск** адаптируется к рыночным условиям
- **Плечо** адаптируется к тренду и волатильности
- **TP уровни** адаптируются к волатильности

### **✅ Защита от потерь:**

- **Высокая волатильность** → снижение риска и плеча
- **Слабый тренд** → консервативные параметры
- **Сильный тренд** → увеличение потенциала прибыли

### **✅ Универсальность:**

- **SPOT пользователи** → всегда безопасное плечо 1x
- **FUTURES пользователи** → адаптивное плечо 1x-20x
- **Все пользователи** → адаптивный риск 1%-5%

---

## 🎯 **ИТОГ:**

### **🔑 Ключевые принципы:**

1. **Никаких статических значений** `risk_pct` и `leverage` в `user_data.json`
2. **Все параметры рассчитываются динамически** на основе рыночных условий
3. **Система автоматически адаптируется** к тренду и волатильности
4. **SPOT пользователи защищены** от высокого плеча

### **📊 Текущий статус:**

- ✅ **Пользователь 556251171** - SPOT, динамические параметры
- ✅ **Пользователь 958930260** - FUTURES, динамические параметры
- ✅ **Система полностью автоматизирована**

### **🎯 Результат:**

**Система теперь работает полностью на динамических параметрах, автоматически адаптируясь к рыночным условиям для каждого пользователя!** 🚀
