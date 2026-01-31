# API Документация: Институциональные индикаторы ATRA

## Обзор

Данный документ описывает API новых институциональных индикаторов, реализованных для достижения уровня крупных prop firms.

## Содержание

1. [Auction Market Theory (AMT)](#auction-market-theory-amt)
2. [Market Profile (TPO)](#market-profile-tpo)
3. [Institutional Order Flow Patterns](#institutional-order-flow-patterns)
4. [Расширенный Cumulative Volume Delta](#расширенный-cumulative-volume-delta)
5. [Order Flow Imbalance по уровням цены](#order-flow-imbalance-по-уровням-цены)
6. [Volume-Weighted Time (VWT)](#volume-weighted-time-vwt)

---

## Auction Market Theory (AMT)

### Класс: `AuctionMarketTheory`

**Расположение:** `src/analysis/auction_market_theory.py`

#### Описание

Анализирует баланс между покупателями и продавцами, определяет фазы рынка (auction/balance/imbalance).

#### Инициализация

```python
from src.analysis.auction_market_theory import AuctionMarketTheory

amt = AuctionMarketTheory(
    lookback=20,                    # Период для анализа (по умолчанию 20 свечей)
    balance_threshold=0.3,          # Порог для определения баланса (0-1)
    imbalance_threshold=0.6,        # Порог для определения дисбаланса (0-1)
)
```

#### Методы

##### `calculate_balance_score(df: pd.DataFrame, i: int) -> Optional[float]`

Рассчитывает баланс между покупателями и продавцами.

**Параметры:**
- `df`: DataFrame с OHLCV данными
- `i`: Индекс текущей свечи

**Возвращает:**
- Баланс от 0 до 1 (0.5 = равновесие), или `None` при ошибке

**Пример:**
```python
balance = amt.calculate_balance_score(df, len(df) - 1)
# balance = 0.65  # Преобладание покупателей
```

##### `detect_market_phase(df: pd.DataFrame, i: int) -> Tuple[Optional[MarketPhase], Optional[Dict[str, Any]]]`

Определяет фазу рынка (auction/balance/imbalance).

**Параметры:**
- `df`: DataFrame с OHLCV данными
- `i`: Индекс текущей свечи

**Возвращает:**
- Tuple[фаза, детали], где:
  - `фаза`: `MarketPhase.AUCTION`, `MarketPhase.BALANCE`, или `MarketPhase.IMBALANCE`
  - `детали`: Dict с `balance_score`, `balance_deviation`, `volatility`, `price_change`, `phase`

**Пример:**
```python
phase, details = amt.detect_market_phase(df, len(df) - 1)
# phase = MarketPhase.IMBALANCE
# details = {
#     'balance_score': 0.65,
#     'balance_deviation': 0.15,
#     'volatility': 0.025,
#     'price_change': 0.05,
#     'phase': 'imbalance'
# }
```

##### `get_auction_levels(df: pd.DataFrame, i: int) -> Dict[str, Optional[float]]`

Определяет уровни аукциона (точки контроля).

**Параметры:**
- `df`: DataFrame с OHLCV данными
- `i`: Индекс текущей свечи

**Возвращает:**
- Dict с уровнями: `high`, `low`, `mid`, `value_area_high`, `value_area_low`

**Пример:**
```python
levels = amt.get_auction_levels(df, len(df) - 1)
# levels = {
#     'high': 105.0,
#     'low': 95.0,
#     'mid': 100.0,
#     'value_area_high': 102.0,
#     'value_area_low': 98.0
# }
```

##### `get_signal(df: pd.DataFrame, i: int) -> Optional[str]`

Определяет торговый сигнал на основе AMT.

**Параметры:**
- `df`: DataFrame с данными
- `i`: Индекс текущей свечи

**Возвращает:**
- `'long'`, `'short'` или `None`

**Пример:**
```python
signal = amt.get_signal(df, len(df) - 1)
# signal = 'long'  # или 'short', или None
```

### Фильтр: `check_amt_filter`

**Расположение:** `src/filters/amt_filter.py`

#### Описание

Фильтрует сигналы на основе фаз рынка по AMT.

#### Использование

```python
from src.filters.amt_filter import check_amt_filter

passed, reason = check_amt_filter(
    df=df,
    i=len(df) - 1,
    side="long",           # "long" или "short"
    strict_mode=True,      # True для строгого режима
)
```

**Параметры:**
- `df`: DataFrame с данными OHLCV
- `i`: Индекс текущей свечи
- `side`: "long" или "short"
- `strict_mode`: True для строгого режима (более жесткие фильтры)

**Возвращает:**
- Tuple[passed, reason], где:
  - `passed`: `True` если фильтр пройден, `False` если заблокирован
  - `reason`: Причина блокировки или `None`

**Логика:**
- **Balance**: блокирует все входы (консолидация)
- **Imbalance**: разрешает входы в направлении дисбаланса
- **Auction**: в строгом режиме блокирует, в мягком разрешает

---

## Market Profile (TPO)

### Класс: `TimePriceOpportunity`

**Расположение:** `src/analysis/market_profile.py`

#### Описание

Анализирует распределение времени по ценам, определяет TPO POC и Value Area.

#### Инициализация

```python
from src.analysis.market_profile import TimePriceOpportunity

tpo = TimePriceOpportunity(
    bins=50,                    # Количество бинов для TPO профиля
    value_area_pct=0.70,        # Процент времени для Value Area
    default_lookback=100,       # Дефолтный lookback период
)
```

#### Методы

##### `calculate_tpo_profile(df: pd.DataFrame, lookback_periods: Optional[int] = None) -> Dict[str, Any]`

Рассчитывает TPO профиль для заданного периода.

**Параметры:**
- `df`: DataFrame с OHLCV данными
- `lookback_periods`: Количество свечей для анализа

**Возвращает:**
- Dict с информацией о TPO профиле:
  - `tpo_poc`: TPO Point of Control
  - `tpo_value_area_high`: Value Area High
  - `tpo_value_area_low`: Value Area Low
  - `tpo_profile`: Dict с распределением времени по ценам
  - `total_time`: Общее время

**Пример:**
```python
profile = tpo.calculate_tpo_profile(df, lookback_periods=100)
# profile = {
#     'tpo_poc': 100.5,
#     'tpo_value_area_high': 102.0,
#     'tpo_value_area_low': 98.0,
#     'tpo_profile': {100.0: 0.5, 100.5: 1.2, ...},
#     'total_time': 100.0
# }
```

##### `get_tpo_poc(df: pd.DataFrame, lookback_periods: Optional[int] = None) -> Optional[float]`

Получает TPO POC (Point of Control на основе времени).

**Параметры:**
- `df`: DataFrame с OHLCV данными
- `lookback_periods`: Количество свечей для анализа

**Возвращает:**
- TPO POC цена или `None`

##### `combine_with_volume_profile(volume_profile: Dict[str, Any], tpo_profile: Dict[str, Any], weight_volume: float = 0.6, weight_time: float = 0.4) -> Dict[str, Any]`

Комбинирует Volume Profile и TPO Profile для более точного POC.

**Параметры:**
- `volume_profile`: Результат Volume Profile
- `tpo_profile`: Результат TPO Profile
- `weight_volume`: Вес Volume Profile (по умолчанию 0.6)
- `weight_time`: Вес TPO Profile (по умолчанию 0.4)

**Возвращает:**
- Комбинированный профиль с улучшенным POC

### Фильтр: `check_market_profile_filter`

**Расположение:** `src/filters/market_profile_filter.py`

#### Использование

```python
from src.filters.market_profile_filter import check_market_profile_filter

passed, reason = check_market_profile_filter(
    df=df,
    i=len(df) - 1,
    side="long",
    strict_mode=True,
    tolerance_pct=1.0,      # Допустимое отклонение от Value Area (%)
)
```

**Логика:**
- **LONG**: цена должна быть близка к Value Area Low или ниже
- **SHORT**: цена должна быть близка к Value Area High или выше

---

## Institutional Order Flow Patterns

### Класс: `InstitutionalPatternDetector`

**Расположение:** `src/analysis/institutional_patterns.py`

#### Описание

Обнаруживает паттерны поведения институционалов: Iceberg Orders и Spoofing.

#### Инициализация

```python
from src.analysis.institutional_patterns import InstitutionalPatternDetector

detector = InstitutionalPatternDetector(
    iceberg_detector=IcebergOrderDetector(
        large_trade_threshold=2.0,
        min_iceberg_size=5,
        lookback=20,
    ),
    spoofing_detector=SpoofingDetector(
        volume_price_divergence_threshold=0.5,
        lookback=10,
    ),
)
```

#### Методы

##### `detect_patterns(df: pd.DataFrame, i: int) -> List[PatternDetection]`

Обнаруживает все институциональные паттерны.

**Параметры:**
- `df`: DataFrame с OHLCV данными
- `i`: Индекс текущей свечи

**Возвращает:**
- Список обнаруженных паттернов (`PatternDetection`)

**Пример:**
```python
patterns = detector.detect_patterns(df, len(df) - 1)
# patterns = [
#     PatternDetection(
#         pattern_type='iceberg',
#         confidence=0.75,
#         details={...},
#         timestamp=100
#     )
# ]
```

##### `get_signal_quality(df: pd.DataFrame, i: int, side: str) -> Dict[str, Any]`

Оценивает качество сигнала на основе обнаруженных паттернов.

**Параметры:**
- `df`: DataFrame с данными
- `i`: Индекс текущей свечи
- `side`: "long" или "short"

**Возвращает:**
- Dict с оценкой качества:
  - `quality_score`: Балл качества (0.0-1.0)
  - `patterns_detected`: Список типов обнаруженных паттернов
  - `pattern_impacts`: Влияние каждого паттерна
  - `recommendation`: 'reject', 'weak', 'moderate', 'strong', 'neutral'

### Фильтр: `check_institutional_patterns_filter`

**Расположение:** `src/filters/institutional_patterns_filter.py`

#### Использование

```python
from src.filters.institutional_patterns_filter import check_institutional_patterns_filter

passed, reason = check_institutional_patterns_filter(
    df=df,
    i=len(df) - 1,
    side="long",
    strict_mode=True,
    min_quality_score=0.6,     # Минимальный балл качества сигнала
)
```

**Логика:**
- **Spoofing обнаружен**: блокирует сигнал (ложные заявки)
- **Iceberg обнаружен**: может подтверждать или ослаблять сигнал
- **Низкое качество**: блокирует в строгом режиме

---

## Расширенный Cumulative Volume Delta

### Класс: `CumulativeDeltaVolume` (расширенный)

**Расположение:** `src/analysis/order_flow/cumulative_delta.py`

#### Новые возможности

##### Временная взвешенность

```python
cdv = CumulativeDeltaVolume(
    lookback=20,
    use_time_weighting=True,      # Включить временную взвешенность
    time_decay=0.95,              # Коэффициент затухания (0.9-0.99)
)
```

Недавние сделки имеют больший вес в расчете CDV.

##### Анализ дивергенций

```python
divergence = cdv.detect_divergence(df, i)
# divergence = {
#     'divergence_type': 'bullish',  # или 'bearish'
#     'confidence': 0.75,
#     'price_trend': 'down',
#     'indicator_trend': 'up',
#     ...
# }
```

### Класс: `DivergenceAnalyzer`

**Расположение:** `src/analysis/order_flow/divergence_analyzer.py`

#### Описание

Анализирует дивергенции между ценой и индикатором (например, CDV).

#### Использование

```python
from src.analysis.order_flow.divergence_analyzer import DivergenceAnalyzer

analyzer = DivergenceAnalyzer(
    lookback=20,
    min_divergence_strength=0.3,
)

divergence = analyzer.detect_divergence(
    price_series=df['close'],
    indicator_series=cdv_series,
    i=len(df) - 1,
)
```

---

## Order Flow Imbalance по уровням цены

### Класс: `PriceLevelImbalance`

**Расположение:** `src/analysis/order_flow/price_level_imbalance.py`

#### Описание

Анализирует дисбаланс Order Flow на каждом уровне цены внутри свечи.

#### Использование

```python
from src.analysis.order_flow.price_level_imbalance import PriceLevelImbalance

analyzer = PriceLevelImbalance(
    price_levels=10,              # Количество уровней цены
    min_imbalance_threshold=0.3,   # Минимальный порог дисбаланса
)

result = analyzer.calculate_imbalance_by_levels(df, len(df) - 1)
# result = {
#     'imbalance_by_levels': {100.0: 0.5, 100.5: -0.3, ...},
#     'max_imbalance_zones': [
#         {'price': 100.0, 'imbalance': 0.5, 'type': 'buy', ...}
#     ],
#     'overall_imbalance': 0.2
# }
```

---

## Volume-Weighted Time (VWT)

### Класс: `VolumeWeightedTime`

**Расположение:** `src/analysis/vwt.py`

#### Описание

Взвешивает время по объему для более точного определения POC.

#### Использование

```python
from src.analysis.vwt import VolumeWeightedTime

vwt = VolumeWeightedTime(
    bins=50,
    value_area_pct=0.70,
    default_lookback=100,
)

profile = vwt.calculate_vwt(df, lookback_periods=100)
# profile = {
#     'vwt_poc': 100.5,
#     'vwt_value_area_high': 102.0,
#     'vwt_value_area_low': 98.0,
#     'vwt_profile': {...},
#     'total_vwt': 1000.0
# }

# Комбинирование с Volume Profile
combined = vwt.combine_with_volume_profile(
    volume_profile=vp_profile,
    vwt_profile=vwt_profile,
    weight_volume=0.5,
    weight_vwt=0.5,
)
```

---

## Конфигурация

Все новые индикаторы можно включить/отключить через переменные окружения в `config.py`:

```python
# Включение/отключение фильтров
USE_AMT_FILTER = True
USE_MARKET_PROFILE_FILTER = True
USE_INSTITUTIONAL_PATTERNS_FILTER = True

# Настройки
AMT_FILTER_CONFIG = {
    "lookback": 20,
    "balance_threshold": 0.3,
    "imbalance_threshold": 0.6,
}

MARKET_PROFILE_FILTER_CONFIG = {
    "bins": 50,
    "value_area_pct": 0.70,
    "default_lookback": 100,
    "tolerance_pct": 1.0,
}

INSTITUTIONAL_PATTERNS_FILTER_CONFIG = {
    "min_quality_score": 0.6,
    "iceberg_large_trade_threshold": 2.0,
    "iceberg_min_size": 5,
    "spoofing_volume_price_divergence_threshold": 0.5,
}
```

---

## Мониторинг и метрики

Все новые индикаторы интегрированы с Prometheus метриками:

- `atra_amt_phase_detected_total` - количество обнаружений фаз AMT
- `atra_amt_balance_score` - распределение баланса AMT
- `atra_tpo_poc_detected_total` - количество обнаружений TPO POC
- `atra_institutional_patterns_detected_total` - количество обнаруженных паттернов
- `atra_cdv_divergence_detected_total` - количество обнаруженных дивергенций
- `atra_filter_amt_checks_total` - количество проверок AMT фильтра
- `atra_filter_market_profile_checks_total` - количество проверок Market Profile фильтра
- `atra_filter_institutional_patterns_checks_total` - количество проверок Institutional Patterns фильтра
- `atra_indicator_processing_time_seconds` - время обработки индикаторов

---

## Примеры использования

### Пример 1: Использование AMT для фильтрации сигналов

```python
from src.analysis.auction_market_theory import AuctionMarketTheory
from src.filters.amt_filter import check_amt_filter

# Инициализация
amt = AuctionMarketTheory(lookback=20)

# Определение фазы рынка
phase, details = amt.detect_market_phase(df, len(df) - 1)

# Фильтрация сигнала
passed, reason = check_amt_filter(df, len(df) - 1, "long", strict_mode=True)

if passed:
    print("Сигнал прошел AMT фильтр")
else:
    print(f"Сигнал заблокирован: {reason}")
```

### Пример 2: Комбинирование TPO и Volume Profile

```python
from src.analysis.market_profile import TimePriceOpportunity
from src.analysis.volume_profile import VolumeProfileAnalyzer

# Инициализация
tpo = TimePriceOpportunity()
vp = VolumeProfileAnalyzer()

# Расчет профилей
volume_profile = vp.calculate_volume_profile(df, lookback_periods=100)
tpo_profile = tpo.calculate_tpo_profile(df, lookback_periods=100)

# Комбинирование
combined = tpo.combine_with_volume_profile(
    volume_profile,
    tpo_profile,
    weight_volume=0.6,
    weight_time=0.4,
)

print(f"Combined POC: {combined['combined_poc']}")
```

### Пример 3: Обнаружение институциональных паттернов

```python
from src.analysis.institutional_patterns import InstitutionalPatternDetector

# Инициализация
detector = InstitutionalPatternDetector()

# Обнаружение паттернов
patterns = detector.detect_patterns(df, len(df) - 1)

for pattern in patterns:
    print(f"Обнаружен паттерн: {pattern.pattern_type}, уверенность: {pattern.confidence}")

# Оценка качества сигнала
quality = detector.get_signal_quality(df, len(df) - 1, "long")
print(f"Качество сигнала: {quality['quality_score']}, рекомендация: {quality['recommendation']}")
```

---

## Тестирование

Все индикаторы покрыты unit и integration тестами:

- `tests/unit/test_amt.py`
- `tests/unit/test_market_profile.py`
- `tests/unit/test_institutional_patterns.py`
- `tests/unit/test_cdv_extended.py`
- `tests/unit/test_price_level_imbalance.py`
- `tests/unit/test_vwt.py`
- `tests/integration/test_amt_filter.py`
- `tests/integration/test_market_profile_filter.py`
- `tests/integration/test_institutional_patterns_filter.py`

Запуск тестов:

```bash
pytest tests/unit/test_amt.py -v
pytest tests/integration/test_amt_filter.py -v
```

---

## Производительность

Все индикаторы оптимизированы для работы в реальном времени:

- AMT: ~1-5ms на свечу
- TPO: ~5-10ms на свечу
- Institutional Patterns: ~10-20ms на свечу
- CDV (расширенный): ~2-5ms на свечу
- Price Level Imbalance: ~3-8ms на свечу
- VWT: ~5-10ms на свечу

Время обработки зависит от:
- Количества свечей в lookback периоде
- Количества бинов для профилей
- Сложности паттернов

---

## Известные ограничения

1. **AMT**: Требует минимум 20 свечей для анализа
2. **TPO**: Точность зависит от качества данных о времени
3. **Institutional Patterns**: Требует достаточного объема данных для обнаружения паттернов
4. **CDV**: Временная взвешенность может увеличить время обработки
5. **Price Level Imbalance**: Точность зависит от количества уровней цены
6. **VWT**: Требует данных об объеме для точного расчета

---

## Поддержка

При возникновении проблем или вопросов:

1. Проверьте логи: `logger.debug()` для детальной информации
2. Проверьте метрики Prometheus: `/metrics` endpoint
3. Проверьте тесты: `pytest tests/unit/test_*.py -v`
4. Обратитесь к документации в коде: docstrings всех классов и методов

---

## Версия

**Версия документа:** 1.0  
**Дата:** 2024  
**Авторы:** Команда ATRA (21 человек)
