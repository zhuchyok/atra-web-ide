# 📋 ПЛАН ИНТЕГРАЦИИ: Параметры под каждую монету

## 🎯 ЦЕЛЬ

Интегрировать оптимизированные параметры из:

1. `src/ai/intelligent_filter_system.py` - функция `get_symbol_specific_parameters()`
2. `backtests/optimize_intelligent_params_*.json` - результаты оптимизации

В генерацию сигналов (`src/signals/core.py`).

---

## 📊 ТЕКУЩАЯ АРХИТЕКТУРА

### **Что используется сейчас:**

1. **`SYMBOL_SPECIFIC_CONFIG`** (26 монет) - используется для:
   - `ai_score_threshold`
   - `optimal_rsi_oversold/overbought`
   - `min_confidence`

2. **`AdaptiveFilterRegulator`** - используется для:
   - `volume_ratio` (динамическая адаптация)

3. **`AI_TP_OPTIMIZER` / `AI_SL_OPTIMIZER`** - используются для:
   - TP/SL уровни (на основе паттернов)

### **Что НЕ используется:**

1. ❌ `get_symbol_specific_parameters()` - параметры для 100+ монет
2. ❌ JSON файлы `optimize_intelligent_params_*.json`
3. ❌ Параметры `volume_ratio`, `quality_score` из оптимизации
4. ❌ **КРИТИЧНО:** Оптимальные параметры фильтров из `all_filters_optimization_results.json` (+2,477% доходность!)

---

## 🎯 УСПЕШНЫЙ БЭКТЕСТ: +2,477% ДОХОДНОСТЬ

**Файл:** `backtests/all_filters_optimization_results.json`  
**Результаты:**

- ✅ Доходность: +2,477.88%
- ✅ Win Rate: 100% (76 сделок)
- ✅ Profit Factor: Infinity
- ✅ Return per Signal: 32.60%

**Оптимальные параметры фильтров:**

- Volume Profile: `threshold=0.6`
- VWAP: `threshold=0.6`
- AMT: `lookback=20, balance_threshold=0.3, imbalance_threshold=0.5`
- Market Profile: `tolerance_pct=1.5`
- Institutional Patterns: `min_quality_score=0.6`
- Order Flow: `required_confirmations=0, pr_threshold=0.5`
- Microstructure: `tolerance_pct=2.5, min_strength=0.1, lookback=30`
- Momentum: `mfi_long=50, mfi_short=50, stoch_long=50, stoch_short=50`
- Trend Strength: `adx_threshold=15, require_direction=false`

**Подробности:** См. `docs/SUCCESSFUL_BACKTEST_ANALYSIS.md`

---

## 🔧 ПРАВИЛЬНАЯ АРХИТЕКТУРА

### **Иерархия приоритетов параметров:**

```
1. all_filters_optimization_results.json - ВЫСШИЙ ПРИОРИТЕТ (для фильтров)
   └─ Оптимальные параметры всех фильтров (+2,477% доходность)

2. JSON файлы (optimize_intelligent_params_*.json) - ВЫСОКИЙ ПРИОРИТЕТ
   └─ Если монета есть в JSON → используем best_params

3. get_symbol_specific_parameters() - СРЕДНИЙ ПРИОРИТЕТ
   └─ Если монеты нет в JSON → используем из intelligent_filter_system.py

4. SYMBOL_SPECIFIC_CONFIG - НИЗКИЙ ПРИОРИТЕТ
   └─ Если монеты нет нигде → используем из config.py

5. DEFAULT значения - ПОСЛЕДНИЙ ПРИОРИТЕТ
   └─ Если ничего не найдено → используем дефолты
```

### **Где применять параметры:**

#### **1. `volume_ratio` в `soft_entry_signal()`:**

```python
# Текущий код (строка 487-546):
base_threshold = SOFT_VOLUME_RATIO_MIN  # 0.3
ai_threshold = adaptive_regulator.get_adaptive_volume_ratio(...)
compensation_threshold = ...

# ✅ ДОБАВИТЬ:
symbol_params = get_symbol_specific_parameters(symbol)
optimized_volume_ratio = symbol_params.get('volume_ratio')

# Приоритет: optimized_volume_ratio > ai_threshold > base_threshold
final_volume_ratio = optimized_volume_ratio or ai_threshold or base_threshold
```

#### **2. `quality_score` в `_generate_signal_impl()`:**

```python
# Текущий код (строка 2482):
min_quality_threshold = max(0.33, base_quality_threshold + market_adjustment)

# ✅ ДОБАВИТЬ:
symbol_params = get_symbol_specific_parameters(symbol)
optimized_quality_score = symbol_params.get('quality_score', 0.7)

# Приоритет: optimized_quality_score > min_quality_threshold
final_quality_threshold = optimized_quality_score or min_quality_threshold
```

#### **3. `rsi_oversold/overbought` в фильтрах:**

```python
# ✅ ДОБАВИТЬ:
symbol_params = get_symbol_specific_parameters(symbol)
rsi_oversold = symbol_params.get('rsi_oversold', 30)
rsi_overbought = symbol_params.get('rsi_overbought', 70)
```

---

## 📝 ПЛАН РЕАЛИЗАЦИИ

### **Шаг 1: Создать функцию загрузки оптимальных параметров фильтров**

```python
def load_optimal_filter_params() -> Optional[Dict[str, Any]]:
    """Загружает оптимальные параметры всех фильтров из успешного бэктеста"""
    results_file = "backtests/all_filters_optimization_results.json"
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("best_params", {})
        except Exception as e:
            logger.debug("Ошибка загрузки optimal_filter_params: %s", e)
    return None

def load_optimized_params_from_json(symbol: str) -> Optional[Dict[str, Any]]:
    """Загружает оптимизированные параметры из последнего JSON файла"""
    import glob
    json_files = sorted(glob.glob("backtests/optimize_intelligent_params_*.json"))
    if json_files:
        latest_file = json_files[-1]
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if symbol in data:
                    return data[symbol].get("best_params", {})
        except Exception as e:
            logger.debug("Ошибка загрузки JSON для %s: %s", symbol, e)
    return None
```

### **Шаг 2: Создать универсальную функцию получения параметров**

```python
def get_symbol_optimized_params(symbol: str) -> Dict[str, Any]:
    """
    Получает оптимизированные параметры для символа с приоритетами:
    1. JSON файлы (высший приоритет)
    2. get_symbol_specific_parameters() (средний)
    3. SYMBOL_SPECIFIC_CONFIG (низкий)
    4. DEFAULT (последний)
    """
    # 1. Пробуем JSON
    json_params = load_optimized_params_from_json(symbol)
    if json_params:
        logger.debug("✅ [%s] Параметры из JSON: %s", symbol, json_params)
        return json_params

    # 2. Пробуем intelligent_filter_system
    try:
        from src.ai.intelligent_filter_system import get_symbol_specific_parameters
        intelligent_params = get_symbol_specific_parameters(symbol)
        if intelligent_params:
            logger.debug("✅ [%s] Параметры из intelligent_filter_system: %s", symbol, intelligent_params)
            return intelligent_params
    except Exception as e:
        logger.debug("⚠️ [%s] Ошибка загрузки intelligent_params: %s", symbol, e)

    # 3. Пробуем SYMBOL_SPECIFIC_CONFIG
    try:
        from src.core.config import SYMBOL_SPECIFIC_CONFIG, DEFAULT_SYMBOL_CONFIG
        config_params = SYMBOL_SPECIFIC_CONFIG.get(symbol, DEFAULT_SYMBOL_CONFIG)
        if config_params:
            # Конвертируем в формат intelligent_filter_system
            return {
                'volume_ratio': config_params.get('soft_volume_ratio', 0.5),
                'quality_score': config_params.get('min_confidence', 65) / 100.0,
                'rsi_oversold': config_params.get('optimal_rsi_oversold', 25),
                'rsi_overbought': config_params.get('optimal_rsi_overbought', 75),
            }
    except Exception as e:
        logger.debug("⚠️ [%s] Ошибка загрузки config_params: %s", symbol, e)

    # 4. DEFAULT
    return {
        'volume_ratio': 0.4,
        'quality_score': 0.65,
        'rsi_oversold': 40,
        'rsi_overbought': 60,
        'trend_strength': 0.15,
        'momentum_threshold': -5.0
    }
```

### **Шаг 3: Интегрировать в `src/signals/core.py`**

#### **3.1. В `soft_entry_signal()` (volume_ratio):**

```python
# После строки 487, перед расчетом ai_threshold:
symbol_params = get_symbol_optimized_params(symbol)
optimized_volume_ratio = symbol_params.get('volume_ratio')

# Используем оптимизированный volume_ratio как базовый порог
if optimized_volume_ratio:
    base_threshold = optimized_volume_ratio
    logger.debug("📊 [%s] Используем оптимизированный volume_ratio: %.2f", symbol, optimized_volume_ratio)
```

#### **3.2. В `_generate_signal_impl()` (quality_score):**

```python
# После строки 2482, перед проверкой quality_score:
symbol_params = get_symbol_optimized_params(symbol)
optimized_quality_score = symbol_params.get('quality_score')

# Используем оптимизированный quality_score
if optimized_quality_score:
    min_quality_threshold = max(0.33, optimized_quality_score)
    logger.debug("📊 [%s] Используем оптимизированный quality_score: %.2f", symbol, optimized_quality_score)
```

#### **3.3. В RSI фильтрах:**

```python
# В enhanced_rsi_filter():
symbol_params = get_symbol_optimized_params(symbol)
rsi_oversold = symbol_params.get('rsi_oversold', base_rsi_oversold)
rsi_overbought = symbol_params.get('rsi_overbought', base_rsi_overbought)
```

---

## ✅ ПРЕИМУЩЕСТВА

1. **Приоритетность:** JSON → intelligent_filter_system → config → default
2. **Обратная совместимость:** Если параметров нет, используются дефолты
3. **Гибкость:** Можно обновлять JSON без изменения кода
4. **Логирование:** Все загрузки параметров логируются

---

## 📊 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

После интеграции:

- ✅ Параметры из JSON будут использоваться автоматически
- ✅ Параметры из `intelligent_filter_system.py` будут использоваться для монет без JSON
- ✅ Каждая монета будет использовать свои оптимизированные параметры
- ✅ Улучшится качество сигналов за счет индивидуальных параметров

---

**Дата:** 2025-12-02  
**Статус:** План готов к реализации
