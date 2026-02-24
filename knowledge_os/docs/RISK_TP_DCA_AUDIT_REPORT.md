# АУДИТ РИСКОВ, TP/SL И DCA

## 📊 Анализ систем риска и управления позициями

### Основные компоненты:

#### 1. **Расчет рисков:**

- **`get_dynamic_risk_pct(df, i)`** - Динамический расчет процента риска
- **`calculate_position_size_from_risk()`** - Расчет размера позиции на основе риска
- **`calculate_anomaly_based_risk()`** - Корректировка риска на основе аномалий

#### 2. **Take Profit / Stop Loss:**

- **`get_dynamic_tp_levels(df, i, side)`** - Динамический расчет TP уровней
- **`get_dynamic_sl_level(df, i, side)`** - Динамический расчет SL уровней

#### 3. **DCA (Dollar-Cost Averaging):**

- **`dca_calculate_next_qty_and_tp()`** - Расчет DCA позиции и TP
- **`should_dca(side, last_close, stop_loss, dca_pct)`** - Проверка необходимости DCA

### 🔧 Анализ логики расчета рисков:

#### **Динамический риск (`get_dynamic_risk_pct`):**

```python
def get_dynamic_risk_pct(df, i):
    if i < 21:
        return 2.0  # стартовый риск

    closes = df["close"].iloc[i - 20 : i]
    volatility = closes.std() / closes.mean()
    trend = (sma20_now - sma20_prev) / sma20_prev

    dynamic_risk = base_risk * (1 + 2 * trend) / (1 + 5 * volatility)
    dynamic_risk = max(1.0, min(dynamic_risk, 5.0))  # 1% - 5%
    return dynamic_risk
```

- **Плюсы**: Адаптивный к волатильности и тренду
- **Минусы**: Ограничен жесткими рамками (1-5%)

#### **Расчет размера позиции:**

```python
def calculate_position_size_from_risk(entry_price, stop_price, deposit_usdt, risk_pct, leverage=1.0):
    risk_usdt = deposit_usdt * risk_pct / 100.0
    distance = abs(entry_price - stop_price)
    qty = risk_usdt / distance  # Основная формула
    notional = qty * entry_price
    return qty, notional_with_leverage, risk_usdt
```

- **Плюсы**: Прозрачная формула, учитывает плечо
- **Минусы**: Не учитывает минимальные лоты биржи

### 📈 Анализ TP/SL систем:

#### **Динамические TP уровни (`get_dynamic_tp_levels`):**

```python
# 1. Волатильность
volatility = closes.std() / closes.mean()
volatility_factor = 1 + volatility * 2
vol_tp1 = base_tp1_pct * volatility_factor  # 2% * 1.2 = 2.4%

# 2. Bollinger Bands
if side == "long":
    bb_tp1_pct = ((bb_middle * 1.015) / current_price - 1) * 100
else:  # short
    bb_tp1_pct = (1 - (bb_middle * 0.985) / current_price) * 100

# 3. Комбинированный
final_tp1 = max(vol_tp1, bb_tp1) if side == "long" else min(vol_tp1, bb_tp1)
```

- **Плюсы**: Учитывает несколько факторов
- **Минусы**: Сложная логика, может быть противоречивой

#### **DCA система:**

```python
def dca_calculate_next_qty_and_tp(...):
    # Базовый расчет
    base_qty = deposit * risk_pct / 100 * leverage / price

    # Корректировка на просадку
    drawdown = abs((avg_price - price) / avg_price)
    new_qty = base_qty * (1 + ALPHA * drawdown) / (1 + dca_count)

    # Ограничения
    if used_risk > max_risk or dca_count >= MAX_DCA:
        return 0, avg_price, None, None, True
```

- **Плюсы**: Увеличивает позицию при просадке
- **Минусы**: Может привести к большим убыткам

### 🚨 Выявленные проблемы:

#### **Проблема 1: Сложность DCA логики**

- **MAX_DCA = 3** - слишком мало для реальной торговли
- **ALPHA** параметр не определен в коде
- Нет проверки минимального расстояния между DCA

#### **Проблема 2: Ограничения риска**

- Фиксированные рамки 1-5% могут быть неоптимальными
- Нет учета разных стилей торговли (агрессивный/консервативный)

#### **Проблема 3: TP/SL не согласованы**

```python
# В DCA LONG:
tp1 = avg_price_new * (1 + dynamic_tp1_pct / 100)
# SL рассчитывается отдельно в другом месте
stop_loss_price = avg_price_new * (1 - abs(tp1_pct) / 100 * 0.5)
```

- **Проблема**: TP и SL рассчитываются независимо, могут не соответствовать друг другу

#### **Проблема 4: Отсутствие валидации**

- Нет проверки на разумные значения TP/SL
- Нет защиты от экстремальных значений волатильности

#### **Проблема 5: Разные константы**

```python
# В разных местах разные константы:
MAX_DCA = 3  # в одном файле
MAX_DCA = 2  # в другом? (нужно проверить)
```

### 🔧 Рекомендации по улучшению:

#### **1. Унификация констант:**

```python
# Создать файл constants.py
class TradingConstants:
    MIN_RISK_PCT = 0.5
    MAX_RISK_PCT = 5.0
    DEFAULT_RISK_PCT = 2.0
    MAX_DCA_COUNT = 5  # Увеличить
    DCA_ALPHA = 2.0    # Добавить
    MIN_TP_PCT = 0.5
    MAX_TP_PCT = 10.0
```

#### **2. Улучшение DCA системы:**

```python
def improved_dca_calculator(entry_prices, qtys, current_price, dca_count, deposit, risk_pct, leverage, side):
    # 1. Проверка лимитов
    if dca_count >= MAX_DCA_COUNT:
        return 0, avg_price, None, None, True

    # 2. Расчет просадки
    avg_price = sum(p * q for p, q in zip(entry_prices, qtys)) / sum(qtys)
    drawdown_pct = abs((avg_price - current_price) / avg_price)

    # 3. Умное определение необходимости DCA
    min_drawdown_for_dca = 0.05  # 5% минимум
    if drawdown_pct < min_drawdown_for_dca:
        return 0, avg_price, None, None, False

    # 4. Расчет размера DCA
    base_risk = deposit * risk_pct / 100
    # Уменьшаем риск для поздних DCA
    risk_multiplier = max(0.3, 1.0 - (dca_count * 0.2))
    adjusted_risk = base_risk * risk_multiplier

    distance_to_sl = abs(avg_price - sl_price)
    new_qty = adjusted_risk / distance_to_sl
```

#### **3. Согласование TP/SL:**

```python
def calculate_coordinated_tp_sl(entry_price, current_volatility, trend_strength, side="long"):
    # 1. Определяем базовые уровни
    base_risk_pct = 2.0
    base_tp1_pct = 2.0
    base_tp2_pct = 4.0

    # 2. Корректируем на волатильность
    volatility_adjustment = current_volatility * 2
    risk_pct = min(base_risk_pct + volatility_adjustment, MAX_RISK_PCT)
    tp1_pct = max(base_tp1_pct + volatility_adjustment, MIN_TP_PCT)
    tp2_pct = max(base_tp2_pct + volatility_adjustment * 1.5, MIN_TP_PCT)

    # 3. Рассчитываем абсолютные уровни
    if side == "long":
        sl_price = entry_price * (1 - risk_pct / 100)
        tp1_price = entry_price * (1 + tp1_pct / 100)
        tp2_price = entry_price * (1 + tp2_pct / 100)
    else:  # short
        sl_price = entry_price * (1 + risk_pct / 100)
        tp1_price = entry_price * (1 - tp1_pct / 100)
        tp2_price = entry_price * (1 - tp2_pct / 100)

    # 4. Проверяем что TP > SL для LONG, TP < SL для SHORT
    if side == "long" and tp1_price <= sl_price:
        # Корректируем TP вверх
        tp1_price = sl_price * 1.01  # Минимум 1% выше SL
        tp2_price = max(tp2_price, sl_price * 1.02)

    return {
        'sl_price': sl_price,
        'tp1_price': tp1_price,
        'tp2_price': tp2_price,
        'risk_pct': risk_pct,
        'tp1_pct': tp1_pct,
        'tp2_pct': tp2_pct
    }
```

#### **4. Добавление валидации:**

```python
def validate_trading_parameters(entry_price, sl_price, tp1_price, tp2_price, side):
    errors = []

    if entry_price <= 0:
        errors.append("Цена входа должна быть положительной")

    if side == "long":
        if sl_price >= entry_price:
            errors.append("SL должен быть ниже цены входа для LONG")
        if tp1_price <= entry_price:
            errors.append("TP1 должен быть выше цены входа для LONG")
        if tp2_price <= tp1_price:
            errors.append("TP2 должен быть выше TP1")
    else:  # short
        if sl_price <= entry_price:
            errors.append("SL должен быть выше цены входа для SHORT")
        if tp1_price >= entry_price:
            errors.append("TP1 должен быть ниже цены входа для SHORT")
        if tp2_price >= tp1_price:
            errors.append("TP2 должен быть ниже TP1")

    # Проверяем разумные проценты
    risk_pct = abs(sl_price - entry_price) / entry_price * 100
    if risk_pct > 20:
        errors.append(f"Слишком высокий риск: {risk_pct:.1f}%")

    tp1_pct = abs(tp1_price - entry_price) / entry_price * 100
    if tp1_pct < 0.1:
        errors.append(f"Слишком близкий TP1: {tp1_pct:.2f}%")

    return errors
```

### 📋 План улучшений:

#### **Фаза 1: Исправление критических ошибок**

1. Исправить несогласованность TP/SL
2. Добавить валидацию параметров
3. Унифицировать константы

#### **Фаза 2: Улучшение DCA**

1. Увеличить MAX_DCA_COUNT до 5
2. Добавить умную логику DCA
3. Реализовать прогрессивное уменьшение риска

#### **Фаза 3: Оптимизация рисков**

1. Добавить адаптивный риск на основе волатильности
2. Реализовать разные профили риска
3. Добавить защиту от экстремальных значений

#### **Фаза 4: Тестирование**

1. Добавить unit тесты для функций риска
2. Создать интеграционные тесты DCA
3. Провести бэктестирование улучшенной системы

### 🎯 Приоритеты:

#### **Высокий приоритет:**

1. Исправить несогласованность TP/SL
2. Добавить валидацию параметров
3. Улучшить DCA логику

#### **Средний приоритет:**

1. Унифицировать константы
2. Добавить разные профили риска
3. Оптимизировать производительность

#### **Низкий приоритет:**

1. Добавить расширенную статистику
2. Реализовать адаптивные стратегии
3. Интегрировать ML для предсказания риска

---

_Аудит рисков, TP/SL и DCA завершен. Система имеет хорошую базу, но требует доработки для надежности и эффективности._
