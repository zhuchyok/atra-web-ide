# 📋 План внедрения фильтров в бектест

**Дата:** 2025-11-13  
**Цель:** Добавить все критичные фильтры из реальной системы в бектест

## 🎯 ПРИОРИТЕТЫ

### **ЭТАП 1: Критичные фильтры (влияют на качество сигналов)**
1. ✅ **Direction Confidence** - минимум 3/4 для soft, 4/4 для strict
2. ✅ **RSI Warning** - блокировка RSI > 65 для BUY, RSI < 35 для SELL
3. ✅ **Quality Score** - минимум 0.68
4. ✅ **Pattern Confidence** - минимум 0.60
5. ✅ **AI Score Filter** - soft=15.0, strict=25.0

### **ЭТАП 2: Важные фильтры (защита от рисков)**
6. ⏳ **Anomaly Filter** - блокировка 0 и >=5 кружков
7. ⏳ **Liquidity Checker** - проверка depth и 24h volume
8. ⏳ **Portfolio Risk Manager** - полная интеграция
9. ⏳ **AI Volume Filter** - улучшение фильтрации объема
10. ⏳ **AI Volatility Filter** - фильтрация волатильности

### **ЭТАП 3: Дополнительные фильтры (оптимизация)**
11. ⏳ **Composite Signal Score** - дополнительный бонус
12. ⏳ **Symbol Blocker** - блокировка проблемных символов
13. ⏳ **Symbol Health** - проверка здоровья символа
14. ⏳ **Volume Quality** - проверка манипуляций объемом
15. ⏳ **False Breakout Detector** - защита от ложных пробоев
16. ⏳ **MTF Confirmation** - подтверждение на 4h
17. ⏳ **Static Levels** - бонус к качеству

## 📝 ДЕТАЛЬНЫЙ ПЛАН ЭТАПА 1

### 1. Direction Confidence
**Функция:** `calculate_direction_confidence(df, signal_type, trade_mode, filter_mode)`

**Логика:**
- 4 проверки: EMA alignment, Price >/< EMA, RSI, MACD
- Soft: минимум 3/4
- Strict: минимум 4/4

**Интеграция:**
```python
# В generate_signal после проверки BTC alignment
if not calculate_direction_confidence(
    df,
    direction,
    trade_mode='futures',
    filter_mode='soft'  # или 'strict'
):
    return None
```

### 2. RSI Warning
**Функция:** `check_rsi_warning(df, signal_type)`

**Логика:**
- BUY: блокирует если RSI > 65
- SELL: блокирует если RSI < 35

**Интеграция:**
```python
# После direction_confidence
if not check_rsi_warning(df, direction):
    return None
```

### 3. Quality Score
**Класс:** `SignalQualityValidator`

**Логика:**
- 5 компонентов: данные (30%), тренд (25%), объем (20%), волатильность (15%), RSI (10%)
- Минимум 0.68

**Интеграция:**
```python
# Инициализация в __init__
self.quality_validator = SignalQualityValidator()

# В generate_signal
quality_score = self.quality_validator.calculate_quality_score(df, direction, symbol)
if not self.quality_validator.is_signal_valid(quality_score):
    return None
```

### 4. Pattern Confidence
**Класс:** `PatternConfidenceScorer`

**Логика:**
- Базовый confidence для каждого паттерна
- Бонусы за тренд и дополнительные условия
- Минимум 0.60

**Интеграция:**
```python
# Инициализация в __init__
self.pattern_scorer = PatternConfidenceScorer()

# В generate_signal (после определения pattern_type)
pattern_confidence = self.pattern_scorer.calculate_pattern_confidence(
    pattern_type='classic_ema',  # или другой
    df=df,
    signal_type=direction
)
if not self.pattern_scorer.is_pattern_reliable(pattern_confidence):
    return None
```

### 5. AI Score Filter
**Функция:** `calculate_ai_signal_score(df, ai_params, symbol)`

**Логика:**
- Расчет AI-скора на основе индикаторов
- Пороги: soft=15.0, strict=25.0

**Интеграция:**
```python
# В generate_signal (в начале, после расчета индикаторов)
ai_params = get_ai_optimized_parameters(symbol)
score = calculate_ai_signal_score(df, ai_params, symbol)

filter_mode = 'soft'  # или 'strict'
required_threshold = 15.0 if filter_mode == 'soft' else 25.0

if score < required_threshold:
    return None
```

## 🔧 ТЕХНИЧЕСКИЕ ДЕТАЛИ

### Необходимые импорты:
```python
from signal_live import (
    calculate_direction_confidence,
    check_rsi_warning,
    calculate_ai_signal_score,
    get_ai_optimized_parameters,
    SignalQualityValidator,
    PatternConfidenceScorer,
)
```

### Необходимые индикаторы:
- ADX (для trend_strength в Quality Score)
- Volatility (для volatility_quality)

### Порядок проверок:
1. Pipeline Validation (уже есть)
2. AI Score Filter
3. AI Volume Filter
4. AI Volatility Filter
5. Anomaly Filter
6. Symbol Blocker
7. Symbol Health
8. Liquidity Checker
9. Pattern Detection (EMA, альтернативные)
10. BTC Alignment
11. Direction Confidence
12. RSI Warning
13. Quality Score
14. Pattern Confidence
15. Volume Quality
16. False Breakout Detector
17. MTF Confirmation
18. Correlation Risk Manager
19. Portfolio Risk Manager

## 📊 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

После добавления всех критичных фильтров:
- **Количество сигналов:** уменьшится на 30-40%
- **Win Rate:** увеличится на 5-10%
- **Profit Factor:** улучшится на 0.2-0.3
- **MaxDD:** уменьшится на 3-5%

## ✅ КРИТЕРИИ УСПЕХА

1. Все критичные фильтры интегрированы
2. Бектест проходит без ошибок
3. Результаты более реалистичны (ближе к реальной системе)
4. Win Rate > 50%
5. Profit Factor > 1.0

