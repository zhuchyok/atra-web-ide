# Архитектура институциональных индикаторов ATRA

## Обзор архитектуры

Система институциональных индикаторов построена по модульному принципу с четким разделением ответственности:

```
src/
├── analysis/                    # Анализаторы индикаторов
│   ├── auction_market_theory.py  # AMT
│   ├── market_profile.py         # TPO
│   ├── institutional_patterns.py # Institutional Patterns
│   ├── order_flow/
│   │   ├── cumulative_delta.py   # Расширенный CDV
│   │   ├── divergence_analyzer.py # Анализ дивергенций
│   │   └── price_level_imbalance.py # Imbalance по уровням
│   └── vwt.py                    # VWT
│
├── filters/                      # Фильтры на основе индикаторов
│   ├── amt_filter.py            # AMT фильтр
│   ├── market_profile_filter.py # Market Profile фильтр
│   └── institutional_patterns_filter.py # Institutional Patterns фильтр
│
├── signals/                      # Интеграция в систему сигналов
│   ├── core.py                  # Основная логика (интеграция AMT)
│   └── filters_volume_vwap.py  # Интеграция Market Profile
│
├── monitoring/                   # Мониторинг и метрики
│   └── prometheus.py            # Prometheus метрики
│
└── metrics/                      # Метрики фильтров
    └── filter_metrics.py        # Метрики эффективности фильтров
```

---

## Компоненты системы

### 1. Анализаторы (Analysis Layer)

#### 1.1 Auction Market Theory (AMT)

**Файл:** `src/analysis/auction_market_theory.py`

**Ответственность:**
- Анализ баланса покупателей/продавцов
- Определение фаз рынка (auction/balance/imbalance)
- Расчет уровней аукциона

**Зависимости:**
- `pandas`, `numpy`
- Использует Volume Delta и CDV для анализа

**Интеграция:**
- Используется в `AMTFilter`
- Интегрирован в `src/signals/core.py`

#### 1.2 Market Profile (TPO)

**Файл:** `src/analysis/market_profile.py`

**Ответственность:**
- Анализ распределения времени по ценам
- Расчет TPO POC и Value Area
- Комбинирование с Volume Profile

**Зависимости:**
- `pandas`, `numpy`
- Интегрируется с `VolumeProfileAnalyzer`

**Интеграция:**
- Используется в `MarketProfileFilter`
- Интегрирован в `src/signals/filters_volume_vwap.py`

#### 1.3 Institutional Order Flow Patterns

**Файл:** `src/analysis/institutional_patterns.py`

**Ответственность:**
- Обнаружение Iceberg Orders
- Обнаружение Spoofing
- Оценка качества сигнала

**Зависимости:**
- `pandas`, `numpy`
- Интегрируется с ML системой

**Интеграция:**
- Используется в `InstitutionalPatternsFilter`
- Интегрирован в `signal_live.py`
- ML features в `ml/features/institutional_patterns_features.py`

#### 1.4 Расширенный Cumulative Volume Delta

**Файл:** `src/analysis/order_flow/cumulative_delta.py`

**Улучшения:**
- Временная взвешенность (недавние сделки важнее)
- Интеграция с `DivergenceAnalyzer`

**Файл:** `src/analysis/order_flow/divergence_analyzer.py`

**Ответственность:**
- Анализ дивергенций между ценой и CDV
- Обнаружение бычьих/медвежьих дивергенций

#### 1.5 Order Flow Imbalance по уровням цены

**Файл:** `src/analysis/order_flow/price_level_imbalance.py`

**Ответственность:**
- Анализ дисбаланса на каждом уровне цены внутри свечи
- Определение зон максимального дисбаланса

**Интеграция:**
- Интегрирован в `VolumeImbalanceFilter`

#### 1.6 Volume-Weighted Time (VWT)

**Файл:** `src/analysis/vwt.py`

**Ответственность:**
- Взвешивание времени по объему
- Расчет VWT POC и Value Area
- Комбинирование с Volume Profile

**Интеграция:**
- Интегрирован в `VolumeProfileAnalyzer`

---

### 2. Фильтры (Filter Layer)

#### 2.1 AMT Filter

**Файл:** `src/filters/amt_filter.py`

**Логика фильтрации:**
- **Balance**: блокирует все входы
- **Imbalance**: разрешает входы в направлении дисбаланса
- **Auction**: в строгом режиме блокирует, в мягком разрешает

**Интеграция:**
- Интегрирован в `src/signals/core.py` (strict и soft режимы)
- Метрики Prometheus

#### 2.2 Market Profile Filter

**Файл:** `src/filters/market_profile_filter.py`

**Логика фильтрации:**
- **LONG**: цена должна быть близка к Value Area Low или ниже
- **SHORT**: цена должна быть близка к Value Area High или выше
- Использует комбинированный POC (Volume Profile + TPO)

**Интеграция:**
- Интегрирован в `src/signals/core.py` (в секции Volume Profile/VWAP)
- Метрики Prometheus

#### 2.3 Institutional Patterns Filter

**Файл:** `src/filters/institutional_patterns_filter.py`

**Логика фильтрации:**
- **Spoofing обнаружен**: всегда блокирует
- **Iceberg обнаружен**: может подтверждать или ослаблять
- **Низкое качество**: блокирует в строгом режиме

**Интеграция:**
- Интегрирован в `signal_live.py` (функция `check_new_filters`)
- Метрики Prometheus

---

### 3. Интеграция в систему сигналов

#### 3.1 Интеграция в `src/signals/core.py`

**AMT Filter:**
- Интегрирован в `strict_entry_signal()` и `soft_entry_signal()`
- Проверяется после базовых условий и других фильтров

**Market Profile Filter:**
- Интегрирован в секцию Volume Profile/VWAP
- Проверяется вместе с Volume Profile и VWAP фильтрами

#### 3.2 Интеграция в `signal_live.py`

**Institutional Patterns Filter:**
- Интегрирован в функцию `check_new_filters()`
- Проверяется после других новых фильтров (Dominance, Interest Zone, Fibonacci, Volume Imbalance)

---

### 4. Мониторинг и метрики

#### 4.1 Prometheus метрики

**Файл:** `src/monitoring/prometheus.py`

**Метрики для новых индикаторов:**
- `atra_amt_phase_detected_total` - количество обнаружений фаз
- `atra_amt_balance_score` - распределение баланса
- `atra_tpo_poc_detected_total` - количество обнаружений TPO POC
- `atra_institutional_patterns_detected_total` - количество паттернов
- `atra_cdv_divergence_detected_total` - количество дивергенций
- `atra_filter_amt_checks_total` - проверки AMT фильтра
- `atra_filter_market_profile_checks_total` - проверки Market Profile фильтра
- `atra_filter_institutional_patterns_checks_total` - проверки Institutional Patterns фильтра
- `atra_indicator_processing_time_seconds` - время обработки

**Функции для записи метрик:**
- `record_amt_phase()` - запись фазы AMT
- `record_tpo_poc()` - запись TPO POC
- `record_institutional_pattern()` - запись паттерна
- `record_cdv_divergence()` - запись дивергенции
- `record_filter_check()` - запись проверки фильтра
- `record_indicator_processing_time()` - запись времени обработки

#### 4.2 Метрики фильтров

**Файл:** `src/metrics/filter_metrics.py`

**Новые типы фильтров:**
- `FilterType.AMT_FILTER`
- `FilterType.MARKET_PROFILE_FILTER`
- `FilterType.INSTITUTIONAL_PATTERNS_FILTER`

---

### 5. Конфигурация

**Файл:** `config.py`

**Флаги включения/отключения:**
```python
USE_AMT_FILTER = True
USE_MARKET_PROFILE_FILTER = True
USE_INSTITUTIONAL_PATTERNS_FILTER = True
```

**Настройки:**
- `AMT_FILTER_CONFIG` - настройки AMT
- `MARKET_PROFILE_FILTER_CONFIG` - настройки Market Profile
- `INSTITUTIONAL_PATTERNS_FILTER_CONFIG` - настройки Institutional Patterns

---

## Поток данных

### Генерация сигнала

```
1. Получение OHLCV данных
   ↓
2. Расчет базовых индикаторов (EMA, RSI, MACD, ...)
   ↓
3. Проверка базовых условий (strict/soft)
   ↓
4. Проверка фильтров:
   - Volume Profile / VWAP / Market Profile
   - Order Flow
   - AMT
   - Microstructure
   - Momentum
   - Trend Strength
   ↓
5. Проверка новых фильтров (signal_live.py):
   - Dominance Trend
   - Interest Zone
   - Fibonacci
   - Volume Imbalance
   - Institutional Patterns
   ↓
6. Генерация сигнала (если все фильтры пройдены)
```

### Обработка индикаторов

```
1. Вызов анализатора (например, AMT)
   ↓
2. Расчет индикатора
   ↓
3. Запись метрик Prometheus
   ↓
4. Возврат результата
   ↓
5. Использование в фильтре
   ↓
6. Запись метрик фильтра
```

---

## Производительность

### Оптимизации

1. **Кэширование**: Результаты расчетов кэшируются где возможно
2. **Ленивая загрузка**: Индикаторы загружаются только при необходимости
3. **Асинхронность**: Фильтры могут работать асинхронно
4. **Векторизация**: Использование NumPy для быстрых вычислений

### Время обработки

- **AMT**: ~1-5ms на свечу
- **TPO**: ~5-10ms на свечу
- **Institutional Patterns**: ~10-20ms на свечу
- **CDV (расширенный)**: ~2-5ms на свечу
- **Price Level Imbalance**: ~3-8ms на свечу
- **VWT**: ~5-10ms на свечу

**Общее время обработки всех фильтров:** ~30-60ms на сигнал

---

## Тестирование

### Unit-тесты

**Расположение:** `tests/unit/`

- `test_amt.py` - тесты AMT
- `test_market_profile.py` - тесты TPO
- `test_institutional_patterns.py` - тесты Institutional Patterns
- `test_cdv_extended.py` - тесты расширенного CDV
- `test_price_level_imbalance.py` - тесты Price Level Imbalance
- `test_vwt.py` - тесты VWT

**Покрытие:** >80% для всех модулей

### Integration-тесты

**Расположение:** `tests/integration/`

- `test_amt_filter.py` - интеграция AMT фильтра
- `test_market_profile_filter.py` - интеграция Market Profile фильтра
- `test_institutional_patterns_filter.py` - интеграция Institutional Patterns фильтра

---

## Расширяемость

### Добавление нового индикатора

1. **Создать анализатор** в `src/analysis/`
2. **Создать фильтр** в `src/filters/`
3. **Добавить метрики** в `src/monitoring/prometheus.py`
4. **Интегрировать** в `src/signals/core.py` или `signal_live.py`
5. **Добавить конфигурацию** в `config.py`
6. **Написать тесты** в `tests/unit/` и `tests/integration/`
7. **Обновить документацию**

### Добавление нового паттерна

1. **Создать детектор** в `src/analysis/institutional_patterns.py`
2. **Интегрировать** в `InstitutionalPatternDetector`
3. **Добавить логику** в `get_signal_quality()`
4. **Обновить ML features** в `ml/features/institutional_patterns_features.py`
5. **Написать тесты**

---

## Безопасность и надежность

### Обработка ошибок

- Все функции имеют try/except блоки
- Graceful degradation: при ошибке фильтр пропускается
- Логирование всех ошибок

### Валидация данных

- Проверка наличия необходимых колонок
- Проверка достаточности данных
- Проверка валидности индексов

### Мониторинг

- Prometheus метрики для всех индикаторов
- Логирование важных событий
- Алерты при аномалиях

---

## Версия

**Версия документа:** 1.0  
**Дата:** 2024  
**Авторы:** Команда ATRA (21 человек)

