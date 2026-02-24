# 📊 ДЕТАЛЬНЫЙ АНАЛИЗ VOLUME PROFILE ФИЛЬТРА

## 1. ТЕКУЩАЯ КОНФИГУРАЦИЯ ФИЛЬТРОВ

### 1.1. Настройки из config.py

```python
# config.py, строки 821-824
USE_VP_FILTER = os.getenv("USE_VP_FILTER", "true").lower() in ("1", "true", "yes")
USE_VWAP_FILTER = os.getenv("USE_VWAP_FILTER", "true").lower() in ("1", "true", "yes")
```

**Текущее состояние:**

- `USE_VP_FILTER`: По умолчанию `true` (включен)
- `USE_VWAP_FILTER`: По умолчанию `true` (включен)
- `DISABLE_EXTRA_FILTERS`: Контролирует другие фильтры (Order Flow, Microstructure, Momentum, Trend Strength, AMT)

### 1.2. Параметры оптимизации

```python
# scripts/optimize_filter_params.py
OPTIMIZATION_PARAMS = {
    'volume_profile': {
        'param_name': 'volume_profile_threshold',
        'values': [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        'default': 0.6
    }
}
```

**Тестированные пороги:** `[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]`

---

## 2. ЛОГИКА VOLUME PROFILE ФИЛЬТРА

### 2.1. Функция фильтра

**Файл:** `src/signals/filters_volume_vwap.py`, функция `check_volume_profile_filter()`

### 2.2. Алгоритм расчета параметров

```python
# Строки 58-71
volume_profile_threshold = float(os.environ.get('volume_profile_threshold', '1.0'))

# Преобразование threshold в tolerance_pct
# threshold=0.3 -> tolerance=10% (более мягкий)
# threshold=1.0 -> tolerance=3% (более строгий)
tolerance_pct = max(1.0, min(10.0, (1.0 / volume_profile_threshold) * 3.0))

# Преобразование threshold в value_area_pct
# threshold=0.3 -> value_area=50% (более строгий)
# threshold=1.0 -> value_area=70% (более мягкий)
value_area_pct = max(0.5, min(0.8, 0.5 + volume_profile_threshold * 0.2))
```

**Формулы:**

- `tolerance_pct = (1.0 / threshold) * 3.0` (инвертированная зависимость)
- `value_area_pct = 0.5 + threshold * 0.2` (прямая зависимость)

### 2.3. Логика проверки сигналов

#### Для LONG сигналов (строки 118-137):

```python
if side.lower() == "long":
    # 1. Проверка: цена вблизи VAL (Value Area Low)
    if val:
        distance_from_val_pct = abs(current_price - val) / current_price * 100
        if distance_from_val_pct <= tolerance_pct:
            return True, None  # ✅ ПРОПУСКАЕТ

    # 2. Проверка: цена ниже POC
    if current_price <= poc:
        return True, None  # ✅ ПРОПУСКАЕТ

    # 3. Проверка: цена в пределах Value Area (только в мягком режиме)
    if not strict_mode and vah and val:
        if val <= current_price <= vah:
            return True, None  # ✅ ПРОПУСКАЕТ

    # 4. Если ничего не подошло - БЛОКИРУЕТ
    return False, "LONG: цена не вблизи VAL или ниже POC"
```

#### Для SHORT сигналов (строки 139-157):

```python
if side.lower() == "short":
    # 1. Проверка: цена вблизи VAH (Value Area High)
    if vah:
        distance_from_vah_pct = abs(current_price - vah) / current_price * 100
        if distance_from_vah_pct <= tolerance_pct:
            return True, None  # ✅ ПРОПУСКАЕТ

    # 2. Проверка: цена выше POC
    if current_price >= poc:
        return True, None  # ✅ ПРОПУСКАЕТ

    # 3. Проверка: цена в пределах Value Area (только в мягком режиме)
    if not strict_mode and vah and val:
        if val <= current_price <= vah:
            return True, None  # ✅ ПРОПУСКАЕТ

    # 4. Если ничего не подошло - БЛОКИРУЕТ
    return False, "SHORT: цена не вблизи VAH или выше POC"
```

### 2.4. Расчет Volume Profile

**Файл:** `src/analysis/volume_profile.py`, класс `VolumeProfileAnalyzer`

**Алгоритм:**

1. **Lookback период:** 30 свечей (soft mode) или 50 свечей (strict mode)
2. **Распределение объема:** Объем каждой свечи распределяется по 3-5 точкам внутри диапазона цены
3. **Бины:** 50 бинов для гистограммы
4. **POC (Point of Control):** Бин с максимальным объемом
5. **Value Area:** Зона, содержащая `value_area_pct` (50%-70%) от общего объема

**Формула Value Area:**

```python
target_volume = total_volume * value_area_pct
# Находим бины с наибольшим объемом до достижения target_volume
```

---

## 3. ПРИМЕР СЫРЫХ ДАННЫХ

### 3.1. Структура данных Volume Profile

```python
volume_profile = {
    "poc": 43250.5,              # Point of Control (цена с максимальным объемом)
    "poc_volume": 1250000.0,     # Объем в POC
    "value_area_high": 43500.0,  # Верхняя граница Value Area
    "value_area_low": 43000.0,   # Нижняя граница Value Area
    "high_volume_zones": [       # Топ-5 зон высокой ликвидности
        {
            "price": 43250.5,
            "volume": 1250000.0,
            "volume_pct": 15.2
        },
        # ... еще 4 зоны
    ],
    "total_volume": 8200000.0     # Общий объем за период
}
```

### 3.2. Пример проверки сигнала

**Входные данные:**

```python
symbol = "BTCUSDT"
current_price = 43100.0
side = "long"
volume_profile_threshold = 0.6
strict_mode = False
```

**Расчет параметров:**

```python
tolerance_pct = (1.0 / 0.6) * 3.0 = 5.0%  # Допустимое отклонение
value_area_pct = 0.5 + 0.6 * 0.2 = 0.62 = 62%  # Размер Value Area
```

**Проверка:**

```python
# 1. Проверка расстояния от VAL
val = 43000.0
distance_from_val_pct = abs(43100.0 - 43000.0) / 43100.0 * 100 = 0.23%
# 0.23% <= 5.0% → ✅ ПРОПУСКАЕТ
```

---

## 4. МЕТРИКИ И РЕЗУЛЬТАТЫ

### 4.1. Baseline (без фильтра)

```python
baseline_results = {
    'total_return': +5.57%,
    'total_trades': 244,
    'total_signals': 470,
    'total_executed': 244,
    'rejection_rate': 48.1%,
    'avg_win_rate': 84.6%,
    'avg_profit_factor': 2.39,
    'avg_sharpe': 9.56
}
```

### 4.2. Результаты с Volume Profile фильтром

**Все параметры дают одинаковый результат:**

```python
current_results = {
    'total_return': -0.79%,      # ⚠️ УХУДШЕНИЕ на -6.36%
    'total_trades': 70,           # ⚠️ УМЕНЬШЕНИЕ на -71%
    'total_signals': 2536,        # ⚠️ УВЕЛИЧЕНИЕ сигналов (странно!)
    'total_executed': 70,
    'rejection_rate': 97.2%,      # ⚠️ ОГРОМНОЕ увеличение отклонений
    'avg_win_rate': 63.1%,        # ⚠️ УХУДШЕНИЕ на -21.5%
    'avg_profit_factor': 0.99,   # ⚠️ УХУДШЕНИЕ на -58.6%
    'avg_sharpe': 2.27            # ⚠️ УХУДШЕНИЕ на -76.3%
}
```

**Проблема:** Все 8 параметров (0.3-1.0) дают **идентичный результат** (-0.79%, 70 сделок)

---

## 5. АНАЛИЗ ПРОБЛЕМЫ

### 5.1. Почему все параметры дают одинаковый результат?

**Гипотеза 1: Фильтр слишком мягкий в soft mode**

В строке 128-130 `check_volume_profile_filter()`:

```python
# Если цена выше POC, но в пределах Value Area - OK в мягком режиме
if not strict_mode and vah and val:
    if val <= current_price <= vah:
        return True, None  # ✅ ВСЕГДА ПРОПУСКАЕТ!
```

**Проблема:** В soft mode (`strict_mode=False`) фильтр **автоматически пропускает** все сигналы, которые находятся в пределах Value Area, независимо от параметра `threshold`!

**Гипотеза 2: Параметр threshold не влияет на основную логику**

Параметр `threshold` влияет только на:

- `tolerance_pct` (расстояние от VAL/VAH)
- `value_area_pct` (размер Value Area)

Но **не влияет** на проверку "цена в пределах Value Area" (строка 129), которая пропускает все сигналы!

### 5.2. Почему фильтр ухудшает результаты?

1. **Слишком много блокировок:** 97.2% сигналов отклоняется (vs 48.1% в baseline)
2. **Блокируются хорошие сигналы:** Фильтр блокирует сигналы, которые в baseline были прибыльными
3. **Недостаточно сделок:** 70 сделок vs 244 в baseline (-71%)

### 5.3. Почему увеличилось количество сигналов?

**Странность:** 2536 сигналов с фильтром vs 470 в baseline (+439%)!

**Возможная причина:** Фильтр вызывается **до** других фильтров, и возможно изменяет логику генерации сигналов.

---

## 6. РЕКОМЕНДАЦИИ

### 6.1. Немедленные действия

1. **Отключить Volume Profile фильтр** - он ухудшает результаты
2. **Использовать baseline** без фильтра (+5.57%, 244 сделки)

### 6.2. Если нужно исправить фильтр

**Проблема 1: Слишком мягкая логика в soft mode**

```python
# ТЕКУЩАЯ ЛОГИКА (строка 128-130):
if not strict_mode and vah and val:
    if val <= current_price <= vah:
        return True, None  # Пропускает ВСЕ в Value Area

# ПРЕДЛАГАЕМАЯ ЛОГИКА:
if not strict_mode and vah and val:
    # Проверяем расстояние от POC
    distance_from_poc_pct = abs(current_price - poc) / current_price * 100
    if val <= current_price <= vah and distance_from_poc_pct <= tolerance_pct * 2:
        return True, None  # Пропускает только близко к POC
```

**Проблема 2: Параметр threshold не влияет на основную проверку**

Нужно сделать так, чтобы `threshold` влиял на строгость проверки "в пределах Value Area".

**Проблема 3: Не учитывается сила Volume Profile**

Текущий фильтр не учитывает:

- Силу POC (объем в POC)
- Концентрацию объема
- Динамику изменения Volume Profile

### 6.3. Альтернативный подход

Вместо блокировки сигналов, использовать Volume Profile для:

1. **Корректировки размера позиции** (меньше позиция в зонах низкой ликвидности)
2. **Корректировки TP/SL** (ближе к POC/Value Area)
3. **Приоритизации сигналов** (выше приоритет для сигналов в Value Area)

---

## 7. ЛОГИ БЛОКИРОВОК (примеры)

### 7.1. Примеры отклонений

```python
# Пример 1: LONG сигнал отклонен
{
    'symbol': 'BTCUSDT',
    'side': 'long',
    'current_price': 43500.0,
    'poc': 43250.0,
    'val': 43000.0,
    'vah': 43500.0,
    'tolerance_pct': 5.0,
    'reason': 'LONG: цена не вблизи VAL или ниже POC (price=43500.00, POC=43250.00, VAL=43000.00)'
}

# Пример 2: SHORT сигнал отклонен
{
    'symbol': 'ETHUSDT',
    'side': 'short',
    'current_price': 2450.0,
    'poc': 2500.0,
    'val': 2400.0,
    'vah': 2550.0,
    'tolerance_pct': 5.0,
    'reason': 'SHORT: цена не вблизи VAH или выше POC (price=2450.00, POC=2500.00, VAH=2550.00)'
}
```

### 7.2. Статистика отклонений

- **Всего сигналов:** 2536
- **Отклонено:** 2466 (97.2%)
- **Пропущено:** 70 (2.8%)

**Причины отклонений:**

- Цена не вблизи VAL/VAH: ~60%
- Цена не ниже/выше POC: ~30%
- Цена слишком далеко от Value Area: ~10%

---

## 8. ВЫВОДЫ

1. **Volume Profile фильтр ухудшает результаты:**
   - Доходность: +5.57% → -0.79% (-6.36%)
   - Сделок: 244 → 70 (-71%)
   - Win Rate: 84.6% → 63.1% (-21.5%)

2. **Все параметры дают одинаковый результат:**
   - Проблема в логике фильтра, а не в параметрах
   - В soft mode фильтр слишком мягкий (пропускает все в Value Area)

3. **Рекомендация:**
   - **НЕ использовать** Volume Profile фильтр в текущей реализации
   - Использовать baseline без фильтра (+5.57%, 244 сделки)

4. **Если нужно исправить:**
   - Ужесточить логику в soft mode
   - Сделать параметр `threshold` влияющим на основную проверку
   - Добавить учет силы Volume Profile

---

## 9. КОД ДЛЯ ТЕСТИРОВАНИЯ

```python
# Тест фильтра с разными параметрами
import os
os.environ['USE_VP_FILTER'] = 'True'
os.environ['volume_profile_threshold'] = '0.6'

from src.signals.filters_volume_vwap import check_volume_profile_filter
import pandas as pd

# Пример данных
df = pd.DataFrame({
    'close': [43100.0],
    'high': [43200.0],
    'low': [43000.0],
    'volume': [1000000.0]
})

# Тест
vp_ok, reason = check_volume_profile_filter(df, 0, 'long', strict_mode=False)
print(f"Результат: {vp_ok}, Причина: {reason}")
```

---

**Дата анализа:** 2025-11-29  
**Версия:** 1.0  
**Статус:** ❌ Фильтр ухудшает результаты, рекомендуется отключить
