# ✅ ЧЕКЛИСТ ДЕПЛОЯ: Все изменения на сервере

## 📋 ЧТО ДОЛЖНО БЫТЬ НА СЕРВЕРЕ

### ✅ Новые фильтры (Phase 1, 2, 3)

1. **Interest Zone Filter**
   - Файл: `src/filters/interest_zone.py`
   - Конфиг: `USE_INTEREST_ZONE_FILTER = True` в `config.py`
   - Интеграция: `signal_live.py` (строка 156, 4401-4411)

2. **Fibonacci Zone Filter**
   - Файл: `src/filters/fibonacci_zone.py`
   - Конфиг: `USE_FIBONACCI_ZONE_FILTER = True` в `config.py`
   - Интеграция: `signal_live.py` (строка 161, 4413-4423)

3. **Dominance Trend Filter**
   - Файл: `src/filters/dominance_trend.py`
   - Конфиг: `USE_DOMINANCE_TREND_FILTER = True` в `config.py`
   - Интеграция: `signal_live.py` (строка 151, 4388-4399)

4. **Volume Imbalance Filter**
   - Файл: `src/filters/volume_imbalance.py`
   - Конфиг: `USE_VOLUME_IMBALANCE_FILTER = True` в `config.py`
   - Интеграция: `signal_live.py` (строка 165, 4425-4435)

### ✅ Новая логика входа (Phase 1, 2, 3)

1. **Pullback Entry Logic**
   - Файл: `src/analysis/pullback_entry.py`
   - Конфиг: `USE_PULLBACK_ENTRY = True` в `config.py`
   - Интеграция: `signal_live.py` (используется в LONG/SHORT Classic)

2. **Market Structure Analyzer**
   - Файл: `src/analysis/market_structure.py`
   - Используется в: `pullback_entry.py`

3. **Entry Quality Scorer**
   - Файл: `src/analysis/entry_quality.py`
   - Используется в: `pullback_entry.py`

4. **Candle Pattern Detector**
   - Файл: `src/patterns/candle_patterns.py`
   - Используется в: `entry_quality.py`

5. **Adaptive Strategy**
   - Файл: `src/strategies/adaptive_strategy.py`
   - Конфиг: `USE_ADAPTIVE_STRATEGY = True` в `config.py`
   - Интеграция: `pullback_entry.py`

### ✅ Динамические TP/SL

1. **Zone Based TP/SL**
   - Файл: `src/signals/zone_based_tp_sl.py`
   - Конфиг: `USE_DYNAMIC_TP_SL_FROM_ZONES = True` в `config.py`
   - Интеграция: `signal_live.py` (динамическая корректировка TP/SL)

2. **Fibonacci Calculator**
   - Файл: `src/technical/fibonacci.py`
   - Используется в: `fibonacci_zone.py`, `zone_based_tp_sl.py`

### ✅ Защита и исправления

1. **Блокировка авто-исполнения в DEV**
   - Файл: `auto_execution.py` (строка 52)
   - Файл: `signal_live.py` (строка 4220)
   - Проверка: `ATRA_ENV != "prod"` → блокировка

2. **Исправление алертов**
   - Файл: `alert_system.py`
   - Персональные алерты для каждого пользователя
   - Системные алерты только в админский чат

3. **Обновление SL на бирже**
   - Файл: `price_monitor_system.py`
   - SL в безубыток после TP1
   - Trailing SL к TP1

## 🔍 ПРОВЕРКА НА СЕРВЕРЕ

### Шаг 1: Обновить код

```bash
cd /root/atra
git pull origin insight  # или main/master
```

### Шаг 2: Проверить файлы

```bash
# Проверка новых фильтров
ls -la src/filters/interest_zone.py
ls -la src/filters/fibonacci_zone.py
ls -la src/filters/dominance_trend.py
ls -la src/filters/volume_imbalance.py

# Проверка новой логики входа
ls -la src/analysis/pullback_entry.py
ls -la src/analysis/market_structure.py
ls -la src/analysis/entry_quality.py
ls -la src/strategies/adaptive_strategy.py

# Проверка динамических TP/SL
ls -la src/signals/zone_based_tp_sl.py
ls -la src/technical/fibonacci.py

# Проверка защиты
grep -A 5 "КРИТИЧЕСКАЯ ПРОВЕРКА" auto_execution.py
```

### Шаг 3: Проверить конфигурацию

```bash
cd /root/atra
python3 -c "
from config import (
    USE_INTEREST_ZONE_FILTER,
    USE_FIBONACCI_ZONE_FILTER,
    USE_DOMINANCE_TREND_FILTER,
    USE_VOLUME_IMBALANCE_FILTER,
    USE_PULLBACK_ENTRY,
    USE_ADAPTIVE_STRATEGY,
    USE_DYNAMIC_TP_SL_FROM_ZONES
)

print('=== ПРОВЕРКА КОНФИГУРАЦИИ ===')
print(f'USE_INTEREST_ZONE_FILTER: {USE_INTEREST_ZONE_FILTER}')
print(f'USE_FIBONACCI_ZONE_FILTER: {USE_FIBONACCI_ZONE_FILTER}')
print(f'USE_DOMINANCE_TREND_FILTER: {USE_DOMINANCE_TREND_FILTER}')
print(f'USE_VOLUME_IMBALANCE_FILTER: {USE_VOLUME_IMBALANCE_FILTER}')
print(f'USE_PULLBACK_ENTRY: {USE_PULLBACK_ENTRY}')
print(f'USE_ADAPTIVE_STRATEGY: {USE_ADAPTIVE_STRATEGY}')
print(f'USE_DYNAMIC_TP_SL_FROM_ZONES: {USE_DYNAMIC_TP_SL_FROM_ZONES}')
"
```

### Шаг 4: Проверить интеграцию

```bash
cd /root/atra
# Проверка импортов в signal_live.py
grep -c "InterestZoneFilter\|FibonacciZoneFilter\|DominanceTrendFilter\|VolumeImbalanceFilter" signal_live.py
# Должно быть: 20+

# Проверка вызовов check_new_filters
grep -c "check_new_filters" signal_live.py
# Должно быть: 10+

# Проверка PullbackEntryLogic
grep -c "PullbackEntryLogic\|AdaptiveStrategy" signal_live.py
# Должно быть: 2+
```

### Шаг 5: Проверить логи при запуске

```bash
cd /root/atra
python3 main.py 2>&1 | grep -E "InterestZoneFilter|FibonacciZoneFilter|DominanceTrendFilter|VolumeImbalanceFilter|PullbackEntryLogic|AdaptiveStrategy" | head -10
```

Должно быть:

```
✅ InterestZoneFilter инициализирован
✅ FibonacciZoneFilter инициализирован
✅ DominanceTrendFilter инициализирован
✅ VolumeImbalanceFilter инициализирован
```

## ⚠️ ВАЖНО

- **DEV и PROD используют одинаковую логику** генерации сигналов
- **Все фильтры включены по умолчанию** (`USE_*_FILTER = True`)
- **Различия только в:**
  - Telegram токен (DEV vs PROD)
  - Уровень логирования (DEBUG vs INFO)
  - Авто-исполнение (DEV всегда manual, PROD зависит от настроек)

## 📊 РЕЗУЛЬТАТ

После деплоя на сервере:

- ✅ Все новые фильтры работают
- ✅ Новая логика входа активна
- ✅ Динамические TP/SL включены
- ✅ Защита от авто-исполнения в DEV работает
- ✅ Алерты настроены правильно

**Логика генерации сигналов одинаковая для DEV и PROD!**
