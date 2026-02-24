# ⚠️ Отсутствующие фильтры в бектесте

**Дата:** 2025-11-13  
**Проблема:** В бектесте не учитываются важные фильтры из реальной системы

## 🔍 Обнаруженные проблемы

### 1. ❌ **Correlation Risk Manager НЕ используется**

**В реальной системе:**

- `CorrelationRiskManager` проверяет корреляцию к BTC/ETH/SOL
- Сегментация по группам (HIGH/MEDIUM/LOW/INDEPENDENT)
- Лимиты по группам (BTC_HIGH: 2 сигнала, BTC_MEDIUM: 3, и т.д.)
- Блокирует сигналы с высокой корреляцией к открытым позициям

**В бектесте:**

- ❌ CorrelationRiskManager отсутствует
- ❌ Корреляция не рассчитывается
- ❌ Сегментация не применяется
- ❌ Лимиты по группам не учитываются

**Влияние:**

- Бектест может открывать слишком много позиций в одной группе
- Не учитывается риск концентрации
- Результаты могут быть завышены

### 2. ⚠️ **Bollinger Bands используется частично**

**В реальной системе:**

- BB используется как блокирующий фильтр в некоторых стратегиях
- Проверка позиции цены относительно полос (нижние 10-20% для LONG, верхние 10-20% для SHORT)
- Учитывается ширина полос (слишком узкие = плохо)

**В бектесте:**

- ✅ BB рассчитывается (bb_upper, bb_lower, bb_middle)
- ⚠️ Используется только как дополнительный фильтр (+10 к confidence)
- ❌ НЕ блокирует сигналы (не является обязательным)
- ❌ Не проверяется ширина полос

**Влияние:**

- Бектест может генерировать сигналы, которые реальная система заблокировала бы
- Результаты могут быть завышены

## 📋 Что нужно добавить

### 1. Correlation Risk Manager

```python
# В __init__:
from correlation_risk_manager import CorrelationRiskManager
self.correlation_manager = CorrelationRiskManager()

# В generate_signal:
correlation_check = await self.correlation_manager.check_correlation_risk_async(
    symbol=symbol,
    signal_type=direction,
    df=df
)
if not correlation_check['allowed']:
    return None  # Блокируем сигнал
```

### 2. Bollinger Bands (блокирующий фильтр)

```python
# Проверка позиции цены
bb_position = (row["close"] - row["bb_lower"]) / (row["bb_upper"] - row["bb_lower"])
bb_width = (row["bb_upper"] - row["bb_lower"]) / row["bb_middle"]

# Для LONG: цена должна быть в нижних 20% BB
if direction == "LONG":
    if bb_position > 0.2:  # Не в нижних 20%
        return None
    if bb_width < 0.02:  # Слишком узкие полосы
        return None

# Для SHORT: цена должна быть в верхних 20% BB
elif direction == "SHORT":
    if bb_position < 0.8:  # Не в верхних 20%
        return None
    if bb_width < 0.02:  # Слишком узкие полосы
        return None
```

## 🎯 Приоритет

1. **Высокий:** Добавить Correlation Risk Manager
2. **Средний:** Улучшить Bollinger Bands фильтр

## 📊 Ожидаемое влияние

- **Количество сигналов:** Уменьшится (более реалистично)
- **Win Rate:** Может улучшиться (лучше фильтрация)
- **Profit Factor:** Может улучшиться (меньше риска концентрации)
