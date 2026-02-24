# План интеграции улучшенной системы управления рисками

## 🎯 **ЦЕЛЬ**

Заменить текущую систему расчета плеч и рисков на профессиональную, основанную на размере депозита и принципах риск-менеджмента.

## 📊 **ТЕКУЩИЕ ПРОБЛЕМЫ**

### 1. **Плечи слишком высокие**

- Текущее: до 20x для всех депозитов
- Проблема: $100 с плечом 20x = $2000 позиция (2000% от депозита!)
- Решение: Прогрессивные лимиты по депозитам

### 2. **Нет учета размера депозита**

- Текущее: одинаковые плечи для $100 и $10000
- Проблема: малые депозиты получают непропорционально высокие риски
- Решение: Адаптивные лимиты по тирам депозитов

### 3. **Спот vs Фьючерсы**

- Текущее: одинаковая логика
- Проблема: спот не должен использовать плечи
- Решение: Разные стратегии для разных режимов

## 🔧 **ПЛАН ИНТЕГРАЦИИ**

### **Этап 1: Замена функций расчета плеч**

#### 1.1 Заменить `get_dynamic_leverage()` в `signal_live.py`

```python
# СТАРОЕ (строки 3853-3920):
def get_dynamic_leverage(df, i, base_leverage=1):
    # Сложная логика без учета депозита
    return max(1, int(round(dynamic_leverage)))

# НОВОЕ:
def get_improved_dynamic_leverage(deposit, trade_mode, volatility, trend_strength, market_regime="neutral"):
    from risk_management_improvements import get_improved_dynamic_leverage
    return get_improved_dynamic_leverage(deposit, trade_mode, volatility, trend_strength, market_regime)
```

#### 1.2 Заменить `get_dynamic_risk_pct()` в `signal_live.py`

```python
# СТАРОЕ (строки 7904-7934):
def get_dynamic_risk_pct(df, i):
    # Простая логика без учета депозита
    return max(1.0, min(dynamic_risk, 5.0))

# НОВОЕ:
def get_improved_dynamic_risk_pct(deposit, trade_mode, volatility, trend_strength, market_regime="neutral"):
    from risk_management_improvements import get_improved_dynamic_risk_pct
    return get_improved_dynamic_risk_pct(deposit, trade_mode, volatility, trend_strength, market_regime)
```

### **Этап 2: Обновление вызовов функций**

#### 2.1 В `check_and_send_signals()` (строки 4729, 5406, 6558)

```python
# СТАРОЕ:
risk_pct = get_dynamic_risk_pct(df, current_index)

# НОВОЕ:
deposit = float(user_data.get("deposit", START_BALANCE))
trade_mode = user_data.get("trade_mode", "spot")
volatility = df["volatility"].iloc[current_index] if "volatility" in df.columns else 0.02
trend_strength = calculate_trend_strength(df, current_index)
market_regime = get_market_regime_from_cache() or "neutral"

risk_pct = get_improved_dynamic_risk_pct(deposit, trade_mode, volatility, trend_strength, market_regime)
```

#### 2.2 В расчете плеч (строки 4795, 4883)

```python
# СТАРОЕ:
dyn_market = get_dynamic_leverage(df, current_index, 5)

# НОВОЕ:
deposit = float(user_data.get("deposit", START_BALANCE))
trade_mode = user_data.get("trade_mode", "spot")
volatility = df["volatility"].iloc[current_index] if "volatility" in df.columns else 0.02
trend_strength = calculate_trend_strength(df, current_index)
market_regime = get_market_regime_from_cache() or "neutral"

dyn_market = get_improved_dynamic_leverage(deposit, trade_mode, volatility, trend_strength, market_regime)
```

### **Этап 3: Добавление валидации рисков**

#### 3.1 Новая функция валидации в `signal_live.py`

```python
def validate_position_risk(deposit, position_size_usd, leverage, trade_mode):
    """Проверяет, не превышает ли позиция допустимые лимиты риска."""
    from risk_management_improvements import validate_position_risk
    return validate_position_risk(deposit, position_size_usd, leverage, trade_mode)
```

#### 3.2 Интеграция валидации в DCA логику

```python
# В функциях DCA (строки 4850, 4926):
if not validate_position_risk(deposit_val, base_new_risk_usd, leverage, trade_mode):
    logger.warning(f"Position risk too high for deposit {deposit_val}")
    continue  # Пропускаем эту позицию
```

### **Этап 4: Обновление профилей риска**

#### 4.1 Заменить `risk_profile_for_user()` в `shared_utils.py`

```python
# СТАРОЕ (строки 278-353):
def risk_profile_for_user(deposit: float, trade_mode: str = "spot") -> dict:
    # Простая логика без прогрессивного масштабирования

# НОВОЕ:
def risk_profile_for_user(deposit: float, trade_mode: str = "spot") -> dict:
    from risk_management_improvements import get_improved_risk_profile
    return get_improved_risk_profile(deposit, trade_mode)
```

## 📈 **ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ**

### **Для малых депозитов ($100-500)**

- **Было**: Плечо до 20x, риск 2-5%
- **Стало**: Плечо 1-3x, риск 0.5-1.5%
- **Результат**: Защита от полной потери депозита

### **Для средних депозитов ($1000-5000)**

- **Было**: Плечо до 20x, риск 2-5%
- **Стало**: Плечо 5-8x, риск 1-2.5%
- **Результат**: Сбалансированный риск/доходность

### **Для больших депозитов ($10000+)**

- **Было**: Плечо до 20x, риск 2-5%
- **Стало**: Плечо 10-20x, риск 1.5-3%
- **Результат**: Максимальная эффективность при контролируемом риске

## 🚀 **ПРЕИМУЩЕСТВА НОВОЙ СИСТЕМЫ**

1. **Защита малых депозитов**: Невозможно потерять весь депозит за одну сделку
2. **Прогрессивное масштабирование**: Большие депозиты получают больше возможностей
3. **Адаптивность**: Учет волатильности, тренда и режима рынка
4. **Профессиональный подход**: Основан на принципах институционального трейдинга
5. **Гибкость**: Разные стратегии для спот и фьючерсов

## ⚠️ **РИСКИ И МИТИГАЦИЯ**

### **Риск**: Снижение доходности для малых депозитов

**Митигация**: Фокус на качестве сигналов, а не на размере позиций

### **Риск**: Сложность интеграции

**Митигация**: Поэтапная замена с сохранением обратной совместимости

### **Риск**: Сопротивление пользователей

**Митигация**: Объяснение преимуществ и постепенное внедрение

## 📋 **ПЛАН ВНЕДРЕНИЯ**

1. **Неделя 1**: Создание новых функций и тестирование
2. **Неделя 2**: Интеграция в существующий код
3. **Неделя 3**: Тестирование на исторических данных
4. **Неделя 4**: Постепенное внедрение для новых пользователей
5. **Неделя 5**: Полный переход на новую систему

## 🎯 **КРИТЕРИИ УСПЕХА**

- Снижение количества полных потерь депозитов на 80%
- Сохранение или улучшение общей доходности
- Увеличение времени жизни аккаунтов
- Положительная обратная связь от пользователей
