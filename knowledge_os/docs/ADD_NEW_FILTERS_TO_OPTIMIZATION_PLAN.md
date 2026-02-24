# 🎯 ПЛАН: ДОБАВЛЕНИЕ НОВЫХ ФИЛЬТРОВ В ОПТИМИЗАЦИЮ

**Дата:** 2024-12-XX  
**Статус:** 🚀 **В РАБОТЕ**

---

## 📊 ФИЛЬТРЫ ДЛЯ ДОБАВЛЕНИЯ

### ✅ **УЖЕ ОПТИМИЗИРОВАНЫ (9 фильтров):**

1. Volume Profile
2. VWAP
3. Market Profile
4. Order Flow
5. Microstructure
6. Momentum
7. Trend Strength
8. AMT
9. Institutional Patterns

### ❌ **НУЖНО ДОБАВИТЬ (9 фильтров):**

#### **1. BTC Trend Filter** 📊

- **Параметры для оптимизации:**
  - `ema_soft`: [50, 100, 200]
  - `ema_strict`: [200]
  - `lookback`: [50, 100]
  - `use_multitf`: [True, False]
- **Текущие параметры:** EMA_SOFT=50, EMA_STRICT=200, LOOKBACK=50
- **Файл:** `src/filters/btc_trend.py`

#### **2. ETH Trend Filter** 📈

- **Параметры для оптимизации:**
  - `ema_soft`: [50, 100, 200]
  - `ema_strict`: [200]
- **Текущие параметры:** EMA_SOFT=50, EMA_STRICT=200
- **Использование:** Вычисляется напрямую в `signal_live.py`

#### **3. SOL Trend Filter** 📈

- **Параметры для оптимизации:**
  - `ema_soft`: [50, 100, 200]
  - `ema_strict`: [200]
- **Текущие параметры:** EMA_SOFT=50, EMA_STRICT=200
- **Использование:** Вычисляется напрямую в `signal_live.py`

#### **4. Dominance Trend Filter** 📉

- **Параметры для оптимизации:**
  - `dominance_threshold_pct`: [0.5, 1.0, 1.5]
  - `min_days_for_trend`: [1, 3, 7]
  - `block_long_on_rising`: [True, False]
  - `block_short_on_falling`: [True, False]
- **Текущие параметры:** threshold=1.0, min_days=1
- **Файл:** `src/filters/dominance_trend.py`

#### **5. Interest Zone Filter** 🎯

- **Параметры для оптимизации:**
  - `lookback_periods`: [50, 100, 200]
  - `min_volume_cluster`: [1.0, 1.5, 2.0]
  - `zone_width_pct`: [0.3, 0.5, 0.7]
  - `min_zone_strength`: [0.5, 0.6, 0.7]
- **Текущие параметры:** lookback=100, cluster=1.5, width=0.5, strength=0.6
- **Файл:** `src/filters/interest_zone.py`

#### **6. Fibonacci Zone Filter** 📐

- **Параметры для оптимизации:**
  - `lookback_periods`: [50, 100, 200]
  - `tolerance_pct`: [0.3, 0.5, 0.7]
  - `require_strong_levels`: [True, False]
- **Текущие параметры:** lookback=100, tolerance=0.5, require_strong=False
- **Файл:** `src/filters/fibonacci_zone.py`

#### **7. Volume Imbalance Filter** 📊

- **Параметры для оптимизации:**
  - `lookback_periods`: [10, 20, 30]
  - `volume_spike_threshold`: [1.5, 2.0, 2.5]
  - `min_volume_ratio`: [1.0, 1.2, 1.5]
  - `require_volume_confirmation`: [True, False]
- **Текущие параметры:** lookback=20, spike=2.0, ratio=1.2, require=True
- **Файл:** `src/filters/volume_imbalance.py`

#### **8. News Filter** 📰

- **Параметры для оптимизации:**
  - `min_sentiment_score`: [0.1, 0.2, 0.3]
  - `block_long_on_negative`: [True, False]
  - `block_short_on_positive`: [True, False]
- **Текущие параметры:** sentiment=0.3, block_long=True, block_short=True
- **Файл:** `src/filters/news.py`

#### **9. Whale Filter** 🐋

- **Параметры для оптимизации:**
  - `min_whale_size_usdt`: [500000, 1000000, 2000000]
  - `activity_threshold`: [0.3, 0.5, 0.7]
  - `time_window_minutes`: [30, 60, 120]
- **Текущие параметры:** size=1M, activity=0.5, window=60
- **Файл:** `src/filters/whale.py`

---

## 🔧 ПЛАН РЕАЛИЗАЦИИ

### **ШАГ 1: Создать функции-обертки для core.py**

Нужно создать синхронные функции для использования в `core.py`:

1. `check_btc_trend_filter(df, i, side, strict_mode=False)` - синхронная версия
2. `check_eth_trend_filter(df, i, side, strict_mode=False)` - синхронная версия
3. `check_sol_trend_filter(df, i, side, strict_mode=False)` - синхронная версия
4. `check_dominance_trend_filter(df, i, side, strict_mode=False)` - синхронная версия
5. `check_interest_zone_filter(df, i, side, strict_mode=False)` - синхронная версия
6. `check_fibonacci_zone_filter(df, i, side, strict_mode=False)` - синхронная версия
7. `check_volume_imbalance_filter(df, i, side, strict_mode=False)` - синхронная версия
8. `check_news_filter(symbol, side, strict_mode=False)` - синхронная версия
9. `check_whale_filter(symbol, side, strict_mode=False)` - синхронная версия

### **ШАГ 2: Добавить фильтры в core.py**

Добавить проверки новых фильтров в `soft_entry_signal` и `strict_entry_signal`:

```python
# После остальных фильтров
if BTC_TREND_FILTER_AVAILABLE and USE_BTC_TREND_FILTER and long_base_ok:
    btc_ok, btc_reason = check_btc_trend_filter(df, i, "long", strict_mode=False)
    if not btc_ok:
        long_base_ok = False
```

### **ШАГ 3: Обновить скрипт оптимизации**

Добавить новые фильтры в `scripts/optimize_all_filters_comprehensive.py`:

- Добавить параметры для оптимизации
- Добавить функции проверки с параметрами
- Добавить в цикл оптимизации

### **ШАГ 4: Запустить оптимизацию**

- Период: 30 дней
- Символы: 5-10 монет
- Потоки: 20 (Rust ускорение)
- Время: ~3-5 часов

---

## 📊 ОЖИДАЕМОЕ КОЛИЧЕСТВО КОМБИНАЦИЙ

### **Упрощенный вариант (сокращенные параметры):**

- BTC Trend: 3 × 2 = 6 комбинаций
- ETH Trend: 3 комбинации
- SOL Trend: 3 комбинации
- Dominance: 3 × 3 × 2 × 2 = 36 комбинаций
- Interest Zone: 3 × 3 × 3 × 3 = 81 комбинация
- Fibonacci: 3 × 3 × 2 = 18 комбинаций
- Volume Imbalance: 3 × 3 × 3 × 2 = 54 комбинации
- News: 3 × 2 × 2 = 12 комбинаций
- Whale: 3 × 3 × 3 = 27 комбинаций

**Итого:** 6 × 3 × 3 × 36 × 81 × 18 × 54 × 12 × 27 = **~2.5 триллиона комбинаций** ❌

### **Оптимизированный вариант (поэтапная оптимизация):**

**Этап 1:** Оптимизировать по одному фильтру (используя уже оптимизированные параметры для остальных)

- Каждый фильтр: 10-50 комбинаций
- 9 фильтров × 30 комбинаций = 270 тестов ✅

**Этап 2:** Финальная оптимизация всех фильтров вместе (сокращенный набор параметров)

- 3-5 параметров на фильтр
- Итого: ~1000-5000 комбинаций ✅

---

## 🎯 РЕКОМЕНДУЕМЫЙ ПОДХОД

### **Вариант 1: Поэтапная оптимизация (рекомендуется)**

1. Оптимизировать каждый фильтр отдельно
2. Использовать оптимальные параметры для остальных
3. Финальная проверка всех вместе

**Преимущества:**

- ✅ Быстрее (270 тестов вместо триллионов)
- ✅ Легче анализировать результаты
- ✅ Можно пропустить неэффективные фильтры

### **Вариант 2: Групповая оптимизация**

1. Группа 1: Trend фильтры (BTC, ETH, SOL)
2. Группа 2: Zone фильтры (Interest, Fibonacci)
3. Группа 3: Market фильтры (Dominance, Volume Imbalance)
4. Группа 4: External фильтры (News, Whale)

**Преимущества:**

- ✅ Учитывает взаимодействие фильтров в группе
- ✅ Быстрее чем полная оптимизация

---

## ✅ СЛЕДУЮЩИЕ ШАГИ

1. ✅ Создать функции-обертки для core.py
2. ✅ Добавить фильтры в core.py
3. ✅ Обновить скрипт оптимизации
4. ✅ Запустить поэтапную оптимизацию
5. ✅ Применить оптимальные параметры

---

## 📁 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ

1. `src/signals/core.py` - добавить проверки новых фильтров
2. `scripts/optimize_all_filters_comprehensive.py` - добавить оптимизацию новых фильтров
3. `config.py` - добавить конфигурацию новых фильтров
4. Создать новые файлы-обертки для синхронных версий фильтров
