# 📊 ВСЕ ФИЛЬТРЫ В СИСТЕМЕ ATRA

**Дата:** 2024-12-XX  
**Статус:** Полный список всех фильтров с описанием и параметрами

---

## ✅ ОПТИМИЗИРОВАННЫЕ ФИЛЬТРЫ

### 1. 🔵 Order Flow Filter

**Файл:** `src/filters/order_flow_filter.py`  
**Статус:** ✅ Оптимизирован  
**Параметры:**

- `required_confirmations`: 0 (только PR проверка)
- `pr_threshold`: 0.5

**Описание:** Фильтр на основе индикаторов потока ордеров (CDV, Volume Delta, Pressure Ratio)

---

### 2. 🟢 Microstructure Filter

**Файл:** `src/filters/microstructure_filter.py`  
**Статус:** ✅ Оптимизирован  
**Параметры:**

- `tolerance_pct`: 2.5
- `min_strength`: 0.1
- `lookback`: 30

**Описание:** Фильтр на основе микроструктуры рынка (Liquidity Zones, Absorption Levels)

---

### 3. 🟡 Momentum Filter

**Файл:** `src/filters/momentum_filter.py`  
**Статус:** ✅ Оптимизирован  
**Параметры:**

- `mfi_long`: 50
- `mfi_short`: 50
- `stoch_long`: 50
- `stoch_short`: 50

**Описание:** Фильтр на основе продвинутых индикаторов момента (MFI, Stochastic RSI)

---

### 4. 🟣 Trend Strength Filter

**Файл:** `src/filters/trend_strength_filter.py`  
**Статус:** ✅ Оптимизирован  
**Параметры:**

- `adx_threshold`: 15
- `require_direction`: false

**Описание:** Фильтр на основе силы тренда (ADX, TSI)

---

## ❌ НЕ ОПТИМИЗИРОВАННЫЕ ФИЛЬТРЫ (ТРЕБУЮТ ДОБАВЛЕНИЯ)

### 5. 📊 Volume Profile (VP) Filter

**Файл:** `src/signals/filters_volume_vwap.py`  
**Статус:** ❌ Не оптимизирован  
**Параметры для оптимизации:**

- `volume_profile_threshold`: [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

**Описание:** Фильтр на основе Volume Profile (VPVR) - проверяет расположение цены относительно Value Area  
**Примечание:** Помечен как неэффективный, но пользователь просит включить все фильтры

---

### 6. 📈 VWAP Filter

**Файл:** `src/signals/filters_volume_vwap.py`  
**Статус:** ❌ Не оптимизирован  
**Параметры для оптимизации:**

- `vwap_threshold`: [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

**Описание:** Фильтр на основе VWAP и его стандартных отклонений

---

### 7. 🎯 AMT (Auction Market Theory) Filter

**Файл:** `src/filters/amt_filter.py`  
**Статус:** ❌ Не оптимизирован  
**Параметры для оптимизации:**

- `lookback`: [15, 20, 25]
- `balance_threshold`: [0.2, 0.3, 0.4]
- `imbalance_threshold`: [0.5, 0.6, 0.7]

**Описание:** Фильтр на основе Auction Market Theory - определяет фазы рынка (Balance, Imbalance, Auction)

---

### 8. 📉 Market Profile (TPO) Filter

**Файл:** `src/filters/market_profile_filter.py`  
**Статус:** ❌ Не оптимизирован  
**Параметры для оптимизации:**

- `tolerance_pct`: [0.5, 1.0, 1.5, 2.0]

**Описание:** Фильтр на основе Market Profile (TPO + Volume Profile) - комбинированный POC и Value Area

---

### 9. 🏛️ Institutional Patterns Filter

**Файл:** `src/filters/institutional_patterns_filter.py`  
**Статус:** ❌ Не оптимизирован  
**Параметры для оптимизации:**

- `min_quality_score`: [0.5, 0.6, 0.7, 0.8]

**Описание:** Фильтр на основе обнаруженных паттернов институционалов (Iceberg Orders, Spoofing)

---

## 💡 ФИЛЬТРЫ ДЛЯ ВЫХОДА (НЕ ДЛЯ ВХОДА)

### 10. ⚠️ Exhaustion Filter

**Файл:** `src/filters/exhaustion_filter.py`  
**Статус:** ⚠️ Для выхода, не для входа  
**Описание:** Фильтр для раннего выхода при исчерпании движения (Volume Exhaustion, Price Exhaustion, Liquidity Exhaustion)  
**Примечание:** Используется для выхода из позиции, не для фильтрации входных сигналов

---

## 🔧 ДРУГИЕ ФИЛЬТРЫ В СИСТЕМЕ

### 11. 📰 News Filter

**Файл:** `src/filters/news.py`  
**Статус:** ✅ Включен в config.py  
**Описание:** Фильтр на основе новостей - блокирует сигналы при негативных новостях

---

### 12. 🐋 Whale Filter

**Файл:** `src/filters/whale.py`  
**Статус:** ✅ Включен в config.py  
**Описание:** Фильтр отслеживания китов - анализирует активность крупных игроков

---

### 13. 📊 BTC Trend Filter

**Файл:** `src/filters/btc_trend.py`  
**Статус:** ✅ Включен в config.py  
**Описание:** Фильтр тренда биткоина - блокирует сигналы против тренда BTC

---

### 14. 📈 Dominance Trend Filter

**Файл:** `src/filters/dominance_trend.py`  
**Статус:** ✅ Включен в config.py  
**Описание:** Фильтр тренда доминации BTC - блокирует LONG альтов при росте BTC.D

---

### 15. 🎯 Interest Zone Filter

**Файл:** `src/filters/interest_zone.py`  
**Статус:** ✅ Включен в config.py  
**Описание:** Фильтр зон интереса - проверяет расположение цены относительно зон интереса

---

### 16. 📐 Fibonacci Zone Filter

**Файл:** `src/filters/fibonacci_zone.py`  
**Статус:** ✅ Включен в config.py  
**Описание:** Фильтр Фибоначчи - проверяет расположение цены относительно уровней Фибоначчи

---

### 17. 📊 Volume Imbalance Filter

**Файл:** `src/filters/volume_imbalance.py`  
**Статус:** ✅ Включен в config.py  
**Описание:** Фильтр имбалансов объема - проверяет скачки объема

---

## 📋 СТАТУС В config.py

```python
# ✅ Включены и оптимизированы
USE_ORDER_FLOW_FILTER = True
USE_MICROSTRUCTURE_FILTER = True
USE_MOMENTUM_FILTER = True
USE_TREND_STRENGTH_FILTER = True

# ❌ Включены, но НЕ оптимизированы
USE_VP_FILTER = False  # Помечен как неэффективный
USE_VWAP_FILTER = True
USE_AMT_FILTER = True
USE_MARKET_PROFILE_FILTER = True
USE_INSTITUTIONAL_PATTERNS_FILTER = True

# ⚠️ Для выхода
USE_EXHAUSTION_FILTER = True  # Используется для раннего выхода
```

---

## 🎯 ПЛАН ДОБАВЛЕНИЯ В ОПТИМИЗАЦИЮ

1. ✅ **Order Flow** - оптимизирован
2. ✅ **Microstructure** - оптимизирован
3. ✅ **Momentum** - оптимизирован
4. ✅ **Trend Strength** - оптимизирован
5. ❌ **Volume Profile (VP)** - нужно добавить
6. ❌ **VWAP** - нужно добавить
7. ❌ **AMT Filter** - нужно добавить
8. ❌ **Market Profile Filter** - нужно добавить
9. ❌ **Institutional Patterns Filter** - нужно добавить

**Итого:** 5 фильтров нужно добавить в оптимизацию

---

## 📊 ОЖИДАЕМОЕ КОЛИЧЕСТВО КОМБИНАЦИЙ

Если добавить все 5 фильтров с сокращенным набором параметров:

- **Volume Profile:** 3 варианта (0.6, 0.8, 1.0)
- **VWAP:** 3 варианта (0.6, 0.8, 1.0)
- **AMT:** 2 варианта (lookback=20, balance=0.3, imbalance=0.6 или 0.5)
- **Market Profile:** 2 варианта (tolerance=1.0 или 1.5)
- **Institutional Patterns:** 2 варианта (min_quality=0.6 или 0.7)

**Текущие фильтры:** 3 × 2 × 2 × 2 = 24 комбинации  
**С новыми фильтрами:** 24 × 3 × 3 × 2 × 2 × 2 = **1,728 комбинаций**

**Это слишком много!** Нужно использовать уже оптимизированные параметры для первых 4 фильтров и оптимизировать только новые 5.

---

## 💡 РЕКОМЕНДАЦИЯ

1. **Использовать уже оптимизированные параметры** для Order Flow, Microstructure, Momentum, Trend Strength
2. **Оптимизировать только новые 5 фильтров** с сокращенным набором параметров
3. **Итоговое количество комбинаций:** 3 × 3 × 2 × 2 × 2 = **72 комбинации** (приемлемо)

---

## ✅ СЛЕДУЮЩИЕ ШАГИ

1. Обновить `scripts/optimize_all_filters_comprehensive.py` для включения всех фильтров
2. Использовать оптимальные параметры для уже оптимизированных фильтров
3. Добавить параметры для новых 5 фильтров
4. Запустить оптимизацию на 30-дневном периоде
5. Применить оптимальные параметры
