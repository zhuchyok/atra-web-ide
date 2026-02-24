# АУДИТ РАСЧЕТА ПЛЕЧА И ДИНАМИЧЕСКИХ МУЛЬТИПЛИКАТОРОВ

## 📊 Анализ систем расчета плеча

### Основные компоненты:

#### 1. **Функции расчета плеча:**

- **`get_dynamic_leverage(df, i, base_leverage)`** - Динамический расчет плеча
- **`calculate_risk_based_leverage(deposit, risk_tolerance)`** - Плечо на основе риска
- **`calculate_base_leverage(deposit)`** - Базовое плечо от депозита
- **`calculate_user_leverage(deposit, trade_mode, filter_mode)`** - Пользовательское плечо

#### 2. **Интеграция с торговлей:**

- Учитывается в `calculate_position_size_from_risk()`
- Применяется только для `trade_mode = 'futures'`
- Отображается в сообщениях сигналов

### 🔧 Анализ логики расчета плеча:

#### **Динамическое плечо (`get_dynamic_leverage`):**

```python
def get_dynamic_leverage(df, i, base_leverage=1):
    if i < 21:
        return max(1, base_leverage)

    closes = df["close"].iloc[i - 20 : i]
    volatility = closes.std() / closes.mean()
    trend = (sma20_now - sma20_prev) / sma20_prev

    trend_factor = 1 + min(abs(trend) * 10, 1.0)
    volatility_factor = max(0.5, 1 / (1 + volatility * 2))
    base_factor = 1 + (base_leverage - 1) * 0.3

    dynamic_leverage = base_leverage * trend_factor * volatility_factor * base_factor
    dynamic_leverage = max(0.5, min(dynamic_leverage, 20))
    return round(dynamic_leverage, 1)
```

- **Плюсы**: Адаптивно к волатильности и тренду
- **Минусы**: Сложная формула, может быть нестабильной

#### **Базовое плечо (`calculate_base_leverage`):**

```python
def calculate_base_leverage(deposit):
    if deposit < 100:
        return 1      # $0-100
    elif deposit < 500:
        return 2      # $100-500
    elif deposit < 1000:
        return 3      # $500-1000
    elif deposit < 5000:
        return 5      # $1000-5000
    elif deposit < 10000:
        return 8      # $5000-10000
    else:
        return 10     # $10000+
```

- **Плюсы**: Простая и понятная логика
- **Минусы**: Ступеньки могут быть слишком резкими

#### **Плечо на основе риска:**

```python
def calculate_risk_based_leverage(deposit, risk_tolerance="moderate"):
    base_leverage = calculate_base_leverage(deposit)

    risk_multipliers = {
        "conservative": 0.5,    # Уменьшаем плечо
        "moderate": 1.0,        # Оставляем как есть
        "aggressive": 1.5       # Увеличиваем плечо
    }

    multiplier = risk_multipliers.get(risk_tolerance, 1.0)
    leverage = base_leverage * multiplier
    leverage = int(max(1, min(leverage, 20)))
    return leverage
```

- **Плюсы**: Учитывает толерантность к риску
- **Минусы**: Смешивает размер депозита и риск-профиль

### 🚨 Выявленные проблемы:

#### **Проблема 1: Несогласованность расчетов**

- **`get_dynamic_leverage`** - рассчитывает динамическое плечо на основе рынка
- **`calculate_risk_based_leverage`** - рассчитывает статическое плечо на основе депозита
- **Проблема**: Две разные системы работают независимо друг от друга

#### **Проблема 2: Резкие переходы**

```python
# В calculate_base_leverage:
if deposit < 100: return 1
elif deposit < 500: return 2    # Резкий скачок с 1x на 2x
elif deposit < 1000: return 3   # +50%
```

- **Проблема**: Плечо меняется слишком резко при небольших изменениях депозита

#### **Проблема 3: Отсутствие защиты от экстремальных значений**

```python
# В get_dynamic_leverage:
dynamic_leverage = max(0.5, min(dynamic_leverage, 20))
# Хорошо: ограничено диапазоном 0.5-20

# В calculate_risk_based_leverage:
leverage = int(max(1, min(leverage, 20)))
# Хорошо: ограничено диапазоном 1-20
```

- **Плюс**: Есть защита от экстремальных значений

#### **Проблема 4: Разные диапазоны**

- `get_dynamic_leverage`: может вернуть 0.5x (для очень волатильных рынков)
- `calculate_risk_based_leverage`: минимум 1x
- **Проблема**: Несогласованность в минимальных значениях

#### **Проблема 5: Отсутствие корреляции с рынком**

```python
# calculate_base_leverage учитывает только депозит:
if deposit < 100: return 1
# Не учитывает текущую волатильность BTCUSDT!
```

- **Проблема**: Плечо не адаптируется к текущим рыночным условиям

### 🔧 Рекомендации по улучшению:

#### **1. Унификация систем расчета плеча:**

```python
class LeverageCalculator:
    def __init__(self, market_conditions=None):
        self.market_conditions = market_conditions or {}

    def calculate_optimal_leverage(self, deposit, risk_tolerance, df=None, current_index=None):
        # 1. Базовое плечо на основе депозита
        base_leverage = self._calculate_deposit_based_leverage(deposit)

        # 2. Корректировка на риск-профиль
        risk_adjusted_leverage = self._apply_risk_tolerance(base_leverage, risk_tolerance)

        # 3. Динамическая корректировка на основе рынка (если есть данные)
        if df is not None and current_index is not None:
            market_adjusted_leverage = self._apply_market_conditions(risk_adjusted_leverage, df, current_index)
            return market_adjusted_leverage

        return risk_adjusted_leverage

    def _calculate_deposit_based_leverage(self, deposit):
        # Плавная кривая вместо ступенек
        if deposit <= 0:
            return 1.0

        # Используем логарифмическую шкалу для плавности
        import math
        leverage = 1 + math.log(deposit + 1) * 0.5
        return max(1.0, min(leverage, 10.0))

    def _apply_risk_tolerance(self, leverage, risk_tolerance):
        multipliers = {
            "conservative": 0.6,
            "moderate": 1.0,
            "aggressive": 1.4
        }
        multiplier = multipliers.get(risk_tolerance, 1.0)
        return leverage * multiplier

    def _apply_market_conditions(self, leverage, df, current_index):
        if current_index < 21:
            return leverage

        # Анализ волатильности рынка
        closes = df["close"].iloc[current_index - 20 : current_index]
        volatility = closes.std() / closes.mean()

        # Корректировка на волатильность
        if volatility > 0.05:  # Высокая волатильность
            leverage *= 0.7
        elif volatility < 0.01:  # Низкая волатильность
            leverage *= 1.2

        # Анализ тренда
        if "sma20" in df.columns:
            sma20_now = df["sma20"].iloc[current_index]
            sma20_prev = df["sma20"].iloc[current_index - 10] if current_index >= 30 else df["sma20"].iloc[current_index - 1]
            trend = (sma20_now - sma20_prev) / sma20_prev if sma20_prev != 0 else 0

            if abs(trend) > 0.02:  # Сильный тренд
                leverage *= 1.1
            elif abs(trend) < 0.005:  # Боковик
                leverage *= 0.9

        return max(1.0, min(leverage, 20.0))
```

#### **2. Улучшенная система ограничений:**

```python
def validate_leverage(leverage, trade_mode, market_conditions=None):
    """
    Валидация и корректировка плеча с учетом всех факторов
    """
    errors = []

    # Базовые ограничения
    if leverage < 1.0:
        errors.append("Плечо не может быть меньше 1x")
        leverage = 1.0

    if leverage > 20.0:
        errors.append("Плечо не может превышать 20x")
        leverage = 20.0

    # Ограничения для SPOT режима
    if trade_mode == "spot" and leverage != 1.0:
        errors.append("Для SPOT режима плечо должно быть 1x")
        leverage = 1.0

    # Дополнительные ограничения для волатильных рынков
    if market_conditions:
        volatility = market_conditions.get('volatility', 0)
        if volatility > 0.1 and leverage > 5.0:  # Очень высокая волатильность
            errors.append("Высокая волатильность: снижаем плечо до 5x")
            leverage = 5.0

    return leverage, errors
```

#### **3. Интеграция с системой риска:**

```python
def calculate_leverage_with_risk_management(entry_price, stop_loss_price, deposit, risk_tolerance, df=None, current_index=None):
    """
    Расчет плеча с учетом риск-менеджмента
    """
    # 1. Расчет максимально допустимого плеча на основе риска
    distance = abs(entry_price - stop_loss_price)
    risk_amount = deposit * 0.02  # 2% риска
    max_qty_without_leverage = risk_amount / distance

    # 2. Определяем необходимое плечо для достижения целевого размера позиции
    target_position_size = deposit * 0.1  # 10% от депозита
    required_leverage = target_position_size / (max_qty_without_leverage * entry_price)

    # 3. Ограничиваем плечо разумными рамками
    max_leverage = 10 if risk_tolerance == "conservative" else 20 if risk_tolerance == "aggressive" else 15
    leverage = min(required_leverage, max_leverage)

    # 4. Применяем рыночные корректировки
    if df is not None and current_index is not None:
        leverage = apply_market_adjustments(leverage, df, current_index)

    return max(1.0, leverage)
```

### 📋 План улучшений:

#### **Фаза 1: Консолидация систем**

1. Создать единую систему расчета плеча
2. Убрать дублирование между `get_dynamic_leverage` и `calculate_risk_based_leverage`
3. Объединить статический и динамический подходы

#### **Фаза 2: Улучшение адаптивности**

1. Добавить плавные переходы вместо ступенек
2. Интегрировать рыночные условия в расчет плеча
3. Улучшить корреляцию с волатильностью

#### **Фаза 3: Интеграция с риском**

1. Связать расчет плеча с системой риск-менеджмента
2. Автоматически корректировать плечо при изменении условий
3. Добавить валидацию совместимости параметров

#### **Фаза 4: Тестирование**

1. Добавить unit тесты для функций плеча
2. Провести бэктестирование разных стратегий плеча
3. Оптимизировать параметры на исторических данных

### 🎯 Приоритеты:

#### **Высокий приоритет:**

1. Унифицировать системы расчета плеча
2. Исправить резкие переходы в базовом плече
3. Добавить валидацию и защиту от экстремальных значений

#### **Средний приоритет:**

1. Интегрировать рыночные условия
2. Улучшить адаптивность к волатильности
3. Связать с системой риск-менеджмента

#### **Низкий приоритет:**

1. Добавить профили плеча для разных стратегий
2. Реализовать динамическое обновление плеча
3. Добавить расширенную аналитику

---

_Аудит расчета плеча завершен. Система имеет две параллельные системы расчета, которые требуют консолидации и улучшения адаптивности к рыночным условиям._
