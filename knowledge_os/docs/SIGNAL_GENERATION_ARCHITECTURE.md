# 🏗️ АРХИТЕКТУРА ГЕНЕРАЦИИ СИГНАЛОВ

**Автор:** Мария (Technical Writer) - Priority 2  
**Дата:** November 23, 2025  
**Версия:** 1.0

---

## 📋 ОБЗОР

Система генерации торговых сигналов ATRA представляет собой многоуровневую архитектуру с множеством фильтров и проверок для обеспечения качества сигналов.

---

## 🔄 ОСНОВНОЙ ПОТОК ГЕНЕРАЦИИ СИГНАЛА

```
┌─────────────────────────────────────────────────────────────┐
│                    check_and_send_signals()                 │
│              (Основной цикл обработки символов)             │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              process_symbol_signals()                        │
│         (Обработка сигналов для каждого символа)             │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│            _generate_signal_impl()                          │
│         (Основная логика генерации сигнала)                  │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌──────────────────┐          ┌──────────────────┐
│  Валидация      │          │  Фильтры         │
│  данных         │          │  качества        │
└────────┬─────────┘          └────────┬─────────┘
         │                             │
         └───────────────┬───────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Паттерны сигналов   │
              │  (classic, alt_1-3)   │
              └──────────┬────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  ML фильтр           │
              │  (LightGBM)          │
              └──────────┬────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Отправка сигнала    │
              │  (Telegram)          │
              └──────────────────────┘
```

---

## 🧩 КОМПОНЕНТЫ СИСТЕМЫ

### **1. Валидация данных**

**Класс:** `SignalQualityValidator`

**Функции:**

- `calculate_quality_score()` - расчёт общего score качества
- `is_signal_valid()` - проверка валидности сигнала

**Проверки:**

- Качество данных (30%)
- Сила тренда (25%)
- Объём (20%)
- Волатильность (15%)
- RSI (10%)

---

### **2. Фильтры качества**

**Классы:**

- `PatternConfidenceScorer` - оценка надёжности паттернов
- `DynamicSymbolBlocker` - динамическая блокировка символов
- `SmartRSIFilter` - умный RSI фильтр
- `PipelineMonitor` - мониторинг pipeline

**Функции:**

- `check_ai_volume_filter()` - фильтр объёма
- `check_ai_volatility_filter()` - фильтр волатильности
- `check_all_trend_alignments()` - проверка выравнивания трендов
- `check_new_filters()` - новые фильтры (Dominance, Fibonacci, etc.)

---

### **3. Паттерны сигналов**

**Типы паттернов:**

1. **Classic EMA** - классический EMA кроссовер
   - Высокая надёжность (0.8)
   - EMA fast > EMA slow для LONG
   - EMA fast < EMA slow для SHORT

2. **Alternative 1** - EMA близко + бычий/медвежий бар + объём
   - Средняя надёжность (0.7)
   - Дополнительные проверки объёма

3. **Alternative 2** - Цена + тренд + RSI
   - Средняя надёжность (0.65)
   - Проверка RSI

4. **Alternative 3** - Отскок от уровня + объём + BB
   - Низкая надёжность (0.6)

---

### **4. ML фильтр**

**Функция:** `check_ml_filter()`

**Процесс:**

1. Сбор индикаторов (RSI, MACD, EMA, BB, ATR, ADX)
2. Сбор рыночных условий (BTC trend, volume ratio, volatility)
3. Подготовка параметров сигнала (entry, TP1, TP2, risk, leverage)
4. Предсказание через LightGBM
5. Проверка порогов (probability, expected profit)

**Пороги:**

- `ML_MIN_WIN_PROBABILITY` = 0.40 (40%)
- `ML_MIN_EXPECTED_PROFIT` = 0.5% (0.5%)

---

### **5. MTF Confirmation**

**Функция:** `_run_mtf_confirmation_with_logging()`

**Процесс:**

1. Попытка гибридной MTF (H4 + H1)
2. Fallback на стандартную MTF (H4)
3. Проверка подтверждения на старшем таймфрейме

---

## 🔍 ПОСЛЕДОВАТЕЛЬНОСТЬ ПРОВЕРОК

```
1. Валидация данных
   ├─ Проверка наличия данных
   ├─ Проверка минимального количества баров (50)
   └─ Интерполяция NaN значений

2. AI Score проверка
   ├─ Расчёт AI score
   └─ Проверка порога (15.0 для soft, 25.0 для strict)

3. Volume фильтр
   └─ check_ai_volume_filter()

4. Volatility фильтр
   └─ check_ai_volatility_filter()

5. Anomaly detection
   └─ calculate_anomaly_circles_with_fallback()

6. MTF Confirmation
   └─ _run_mtf_confirmation_with_logging()

7. Паттерн сигнала
   ├─ Classic EMA
   ├─ Alternative 1
   ├─ Alternative 2
   └─ Alternative 3

8. Quality и Confidence проверки
   ├─ SignalQualityValidator
   └─ PatternConfidenceScorer

9. Trend alignments
   └─ check_all_trend_alignments()

10. ML фильтр
    └─ check_ml_filter()

11. Отправка сигнала
    └─ send_signal()
```

---

## 📊 МЕТРИКИ И МОНИТОРИНГ

**PipelineMonitor** отслеживает:

- Общее количество попыток
- Прохождение каждого этапа
- Финальные сигналы
- Распределение паттернов

**Prometheus метрики:**

- `signal_generated` - сгенерированные сигналы
- `signal_accepted` - принятые сигналы
- `signal_rejected` - отклонённые сигналы
- `ml_prediction` - ML предсказания

---

## 🔧 КОНФИГУРАЦИЯ

**Основные параметры:**

- `filter_mode` - режим фильтров ("soft" или "strict")
- `ai_score_threshold` - порог AI score (15.0 для soft, 25.0 для strict)
- `ML_MIN_WIN_PROBABILITY` - минимальная вероятность успеха (0.40)
- `ML_MIN_EXPECTED_PROFIT` - минимальная ожидаемая прибыль (0.5%)

---

## 📝 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### **Генерация сигнала:**

```python
# В check_and_send_signals()
signal_type, signal_price = await _generate_signal_impl(
    symbol=symbol,
    df=df,
    user_data=user_data,
    regime_data=regime_data,
    regime_multipliers=regime_multipliers
)

if signal_type and signal_price:
    await send_signal(...)
```

### **Проверка ML фильтра:**

```python
ml_passed, ml_reason, prediction = await check_ml_filter(
    symbol=symbol,
    signal_type=signal_type,
    entry_price=entry_price,
    df=df,
    quality_score=quality_score,
    mtf_score=mtf_score,
    tp1=tp1_price,
    tp2=tp2_price,
    risk_pct=risk_pct,
    leverage=leverage,
    regime_data=regime_data
)
```

---

## 🚀 ОПТИМИЗАЦИИ

1. **Параллельные запросы** - API запросы выполняются параллельно
2. **Кэширование** - данные кэшируются для уменьшения запросов
3. **Connection pooling** - пул соединений для БД
4. **Async/await** - асинхронная обработка

---

## 📚 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ

- [API Reference](../docs/API_REFERENCE.md)
- [Comprehensive System Audit](../scripts/COMPREHENSIVE_SYSTEM_AUDIT.md)
- [Testing Policy](../scripts/TESTING_POLICY.md)

---

_Документация подготовлена: Мария (Technical Writer)_
