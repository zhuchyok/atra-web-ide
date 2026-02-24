# 🔍 АНАЛИЗ ПРОБЛЕМЫ: Volume Imbalance Filter блокирует все сигналы

## ❌ ПРОБЛЕМА

**Volume Imbalance Filter блокирует все сигналы с причиной `LOW_VOLUME`**

### 📊 Что происходит:

1. Бот генерирует сигналы (ETHUSDT LONG и др.)
2. Volume Imbalance фильтр проверяет `volume_ratio`
3. **Если `volume_ratio < min_volume_ratio` (1.0) → блокирует сигнал**
4. Сигналы не доходят до пользователей

### 🔍 Логика фильтра:

```python
# В src/filters/volume_imbalance.py:257
if volume_ratio < self.min_volume_ratio:
    return FilterResult(passed=False, reason="LOW_VOLUME")
```

**Где:**

- `volume_ratio = current_volume / avg_volume` (строка 124)
- `min_volume_ratio = 1.0` (из config.py)

**Это означает:**

- Если текущий объем < среднего объема → `volume_ratio < 1.0`
- Фильтр блокирует сигнал

## 📋 ТЕКУЩИЕ ПАРАМЕТРЫ:

```python
VOLUME_IMBALANCE_FILTER_CONFIG = {
    'lookback_periods': 10,
    'volume_spike_threshold': 1.5,
    'min_volume_ratio': 1.0,  # ⚠️ Требует текущий объем >= средний
    'require_volume_confirmation': True  # ⚠️ Обязательное требование
}
```

## 💡 РЕШЕНИЯ:

### Вариант 1: Снизить min_volume_ratio

```python
'min_volume_ratio': 0.8,  # Разрешить если объем >= 80% от среднего
```

### Вариант 2: Отключить require_volume_confirmation

```python
'require_volume_confirmation': False,  # Не требовать подтверждение объемом
```

### Вариант 3: Временно отключить фильтр

```python
USE_VOLUME_IMBALANCE_FILTER = False
```

## 🔧 РЕКОМЕНДАЦИЯ:

**Снизить `min_volume_ratio` до 0.8** - это позволит пропускать сигналы даже если текущий объем немного ниже среднего, но не слишком низкий.
