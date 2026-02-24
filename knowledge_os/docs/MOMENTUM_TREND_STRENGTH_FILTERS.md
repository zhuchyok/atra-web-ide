# 📊 ФИЛЬТРЫ MOMENTUM И TREND STRENGTH

## ✅ СТАТУС: ВКЛЮЧЕНЫ И РАБОТАЮТ

### 📊 MOMENTUM FILTER

**Файл:** `src/filters/momentum_filter.py`

**Используемые индикаторы:**

- **Money Flow Index (MFI)** - комбинация цены и объема
- **Stochastic RSI (Stoch RSI)** - более чувствительная версия RSI

**Логика фильтрации:**

#### LONG сигналы:

- **Строгий режим:** Требуются оба подтверждения
  - MFI < 30.0 (перепроданность)
  - Stoch RSI < 20.0 (перепроданность)
- **Мягкий режим:** Достаточно одного подтверждения
  - MFI < 40.0 ИЛИ Stoch RSI < 30.0

#### SHORT сигналы:

- **Строгий режим:** Требуются оба подтверждения
  - MFI > 70.0 (перекупленность)
  - Stoch RSI > 80.0 (перекупленность)
- **Мягкий режим:** Достаточно одного подтверждения
  - MFI > 60.0 ИЛИ Stoch RSI > 70.0

**Применение:** В `soft_entry_signal` используется **мягкий режим** (`strict_mode=False`)

---

### 📊 TREND STRENGTH FILTER

**Файл:** `src/filters/trend_strength_filter.py`

**Используемые индикаторы:**

- **ADX (Average Directional Index)** - сила тренда
- **TSI (True Strength Index)** - направление и сила тренда

**Логика фильтрации:**

#### Общие требования:

- **Строгий режим:** ADX > 25.0 (сильный тренд)
- **Мягкий режим:** ADX > 20.0 (умеренный тренд)

#### LONG сигналы:

- **Строгий режим:** Требуются оба подтверждения
  - ADX направление = 'up' (восходящий)
  - TSI > 0 (восходящий тренд)
- **Мягкий режим:** Достаточно одного подтверждения
  - ADX направление = 'up' ИЛИ TSI > 0

#### SHORT сигналы:

- **Строгий режим:** Требуются оба подтверждения
  - ADX направление = 'down' (нисходящий)
  - TSI < 0 (нисходящий тренд)
- **Мягкий режим:** Достаточно одного подтверждения
  - ADX направление = 'down' ИЛИ TSI < 0

**Применение:** В `soft_entry_signal` используется **мягкий режим** (`strict_mode=False`)

---

## 🔧 КОНФИГУРАЦИЯ

**Файл:** `config.py`

```python
# Включение/отключение Momentum фильтра
USE_MOMENTUM_FILTER = os.getenv("USE_MOMENTUM_FILTER", "true").lower() in ("1", "true", "yes")

# Включение/отключение Trend Strength фильтра
USE_TREND_STRENGTH_FILTER = os.getenv("USE_TREND_STRENGTH_FILTER", "true").lower() in ("1", "true", "yes")
```

**По умолчанию:** Оба фильтра **ВКЛЮЧЕНЫ** (`True`)

---

## 📍 МЕСТО ПРИМЕНЕНИЯ

**Файл:** `src/signals/core.py`

Фильтры применяются **ПОСЛЕ baseline** в функции `soft_entry_signal`:

```python
# Momentum фильтр (в мягком режиме)
if MOMENTUM_FILTER_AVAILABLE and USE_MOMENTUM_FILTER and long_base_ok:
    mom_ok, mom_reason = check_momentum_filter(df, i, "long", strict_mode=False)
    if not mom_ok:
        logger.debug("LONG (soft) отклонен Momentum фильтром: %s", mom_reason)
        long_base_ok = False

# Trend Strength фильтр (в мягком режиме)
if TREND_STRENGTH_FILTER_AVAILABLE and USE_TREND_STRENGTH_FILTER and long_base_ok:
    trend_ok, trend_reason = check_trend_strength_filter(df, i, "long", strict_mode=False)
    if not trend_ok:
        logger.debug("LONG (soft) отклонен Trend Strength фильтром: %s", trend_reason)
        long_base_ok = False
```

---

## 🎯 ПОРЯДОК ПРИМЕНЕНИЯ ФИЛЬТРОВ

1. **Volume Profile** (VP) - проверяется независимо
2. **VWAP** - проверяется независимо
3. **Baseline** (ослабленный, 70% условий)
4. **Order Flow** - ПОСЛЕ baseline
5. **Microstructure** - ПОСЛЕ baseline
6. **Momentum** - ПОСЛЕ baseline ⬅️
7. **Trend Strength** - ПОСЛЕ baseline ⬅️
8. **AMT** - ПОСЛЕ baseline

---

## 💡 ОСОБЕННОСТИ

- Оба фильтра работают в **мягком режиме** для `soft_entry_signal`
- Фильтры применяются **последовательно** - если один блокирует, остальные не проверяются
- В случае ошибки фильтр **пропускает** сигнал (не блокирует)
- Логирование отключенных сигналов на уровне DEBUG

---

## 🔄 ВОЗМОЖНЫЕ УЛУЧШЕНИЯ

1. **Оптимизация параметров** - подбор оптимальных порогов для MFI, Stoch RSI, ADX
2. **Адаптивные пороги** - динамическая настройка в зависимости от волатильности
3. **Комбинированная логика** - взвешенная оценка вместо простого OR/AND
