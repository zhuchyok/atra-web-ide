# 🔍 ПРОВЕРКА ПОРЯДКА ФИЛЬТРОВ

## 📊 ПРАВИЛЬНЫЙ ПОРЯДОК (из успешного бэктеста +2,477%)

Согласно `docs/SUCCESSFUL_BACKTEST_ANALYSIS.md`:

1. **Volume Profile** (проверка VAL/VAH/POC)
2. **VWAP** (проверка относительно VWAP)
3. **AMT** (Accumulation/Markup/Trend)
4. **Market Profile** (проверка толерантности)
5. **Institutional Patterns** (качество паттернов)
6. **Order Flow** (поток ордеров, без подтверждений)
7. **Microstructure** (микроструктура рынка)
8. **Momentum** (MFI и Stochastic)
9. **Trend Strength** (ADX, без требования направления)

## 🔍 ТЕКУЩИЙ ПОРЯДОК В КОДЕ

### В `strict_entry_signal` (src/signals/core.py:290-352):

**ТЕКУЩИЙ ПОРЯДОК:**

1. ✅ Volume Profile
2. ✅ VWAP
3. ✅ Market Profile
4. ❌ **Order Flow** (должен быть после AMT и Institutional Patterns)
5. ❌ **Microstructure** (должен быть после Order Flow)
6. ❌ **Momentum** (должен быть после Microstructure)
7. ❌ **Trend Strength** (должен быть после Momentum)
8. ❌ **AMT** (должен быть 3-м, после VWAP)
9. ❌ **Institutional Patterns** (должен быть 5-м, после Market Profile)

**ПРАВИЛЬНЫЙ ПОРЯДОК ДОЛЖЕН БЫТЬ:**

1. Volume Profile
2. VWAP
3. **AMT** ← переместить сюда
4. **Market Profile** ← уже здесь
5. **Institutional Patterns** ← переместить сюда
6. **Order Flow** ← переместить сюда
7. **Microstructure** ← переместить сюда
8. **Momentum** ← переместить сюда
9. **Trend Strength** ← переместить сюда

### В `soft_entry_signal` (src/signals/core.py:633-790):

**ТЕКУЩИЙ ПОРЯДОК:**

1. ✅ Volume Profile (перед baseline)
2. ✅ VWAP (перед baseline)
3. ✅ Baseline (ослабленный, 70%)
4. ✅ Market Profile
5. ❌ **Order Flow** (должен быть после AMT и Institutional Patterns)
6. ❌ **Microstructure** (должен быть после Order Flow)
7. ❌ **Momentum** (должен быть после Microstructure)
8. ❌ **Trend Strength** (должен быть после Momentum)
9. ❌ **AMT** (должен быть после Market Profile)
10. ❌ **Institutional Patterns** (должен быть после AMT)

**ПРАВИЛЬНЫЙ ПОРЯДОК ДОЛЖЕН БЫТЬ:**

1. Volume Profile (перед baseline) ✅
2. VWAP (перед baseline) ✅
3. Baseline (ослабленный, 70%) ✅
4. **AMT** ← добавить сюда
5. **Market Profile** ← уже здесь
6. **Institutional Patterns** ← добавить сюда
7. **Order Flow** ← переместить сюда
8. **Microstructure** ← переместить сюда
9. **Momentum** ← переместить сюда
10. **Trend Strength** ← переместить сюда

## ⚠️ ПРОБЛЕМА

**Порядок фильтров НЕ соответствует успешному бэктесту!**

Нужно исправить порядок в обоих функциях (`strict_entry_signal` и `soft_entry_signal`).
