# ⚠️ ВАЖНО: ВЕРНУТЬ ВРЕМЕННЫЕ ИЗМЕНЕНИЯ ОБРАТНО

**Дата создания:** 2025-12-02  
**Статус:** 🔴 КРИТИЧНО - НЕ ЗАБЫТЬ!

---

## 📋 СПИСОК ВРЕМЕННЫХ ИЗМЕНЕНИЙ ДЛЯ ОТКАТА

### 1. **ML Фильтр** (signal_live.py, строка ~5123)

**Текущее состояние:**

```python
USE_ML_FILTER = False  # 🔧 ТЕСТ: временно отключен
```

**Нужно вернуть:**

```python
USE_ML_FILTER = True  # Включить обратно после исправления prob=0.01%
```

---

### 2. **ML Пороги** (signal_live.py, строки ~5357, 5372)

**Текущее состояние:**

```python
optimized_thresholds = {
    'min_success_prob': 0.1,  # 🔧 ТЕСТ: было 0.4
    'min_expected_profit': 0.1,  # 🔧 ТЕСТ: было 0.3
    'min_combined_score': 0.01  # 🔧 ТЕСТ: было 0.15
}
```

**Нужно вернуть:**

```python
optimized_thresholds = {
    'min_success_prob': 0.4,  # Вернуть обратно
    'min_expected_profit': 0.3,  # Вернуть обратно
    'min_combined_score': 0.15  # Вернуть обратно
}
```

---

### 3. **Correlation Risk** (signal_live.py, строка ~3717)

**Текущее состояние:**

```python
USE_CORRELATION_RISK = False  # 🔧 ТЕСТ: временно отключен
```

**Нужно вернуть:**

```python
USE_CORRELATION_RISK = True  # Включить обратно после исправления
```

### 4. **Correlation Risk Лимиты** (src/risk/correlation_risk.py, строки ~99-116)

**Текущее состояние:**

```python
'BTC_HIGH': {'max_signals': 20, ...},  # 🔧 ТЕСТ: было 5
'ETH_HIGH': {'max_signals': 20, ...},  # 🔧 ТЕСТ: было 5
'SOL_HIGH': {'max_signals': 20, ...},  # 🔧 ТЕСТ: было 10
'BTC_MEDIUM': {'max_signals': 15, ...},  # 🔧 ТЕСТ: было 3
'ETH_MEDIUM': {'max_signals': 15, ...},  # 🔧 ТЕСТ: было 3
'SOL_MEDIUM': {'max_signals': 15, ...},  # 🔧 ТЕСТ: было 3
'BTC_LOW': {'max_signals': 15, ...},  # 🔧 ТЕСТ: было 4
'ETH_LOW': {'max_signals': 15, ...},  # 🔧 ТЕСТ: было 4
'SOL_LOW': {'max_signals': 15, ...},  # 🔧 ТЕСТ: было 4
```

**Нужно вернуть:**

```python
'BTC_HIGH': {'max_signals': 5, ...},  # Вернуть обратно
'ETH_HIGH': {'max_signals': 5, ...},  # Вернуть обратно
'SOL_HIGH': {'max_signals': 10, ...},  # Вернуть обратно
'BTC_MEDIUM': {'max_signals': 3, ...},  # Вернуть обратно
'ETH_MEDIUM': {'max_signals': 3, ...},  # Вернуть обратно
'SOL_MEDIUM': {'max_signals': 3, ...},  # Вернуть обратно
'BTC_LOW': {'max_signals': 4, ...},  # Вернуть обратно
'ETH_LOW': {'max_signals': 4, ...},  # Вернуть обратно
'SOL_LOW': {'max_signals': 4, ...},  # Вернуть обратно
```

---

## 🎯 КОГДА ВЕРНУТЬ

**Условия для отката:**

1. ✅ Сигналы генерируются и отправляются
2. ✅ Проблема с ML моделью (prob=0.01%) исправлена
3. ✅ Correlation Risk работает корректно
4. ✅ Система стабильна

---

## 📝 КОМАНДЫ ДЛЯ ОТКАТА

```bash
# 1. Вернуть ML фильтр
# Отредактировать signal_live.py, строка ~5123

# 2. Вернуть ML пороги
# Отредактировать signal_live.py, строки ~5357, 5372

# 3. Вернуть Correlation Risk лимиты
# Отредактировать src/risk/correlation_risk.py, строки ~99-116

# 4. Закоммитить и задеплоить
git add signal_live.py src/risk/correlation_risk.py
git commit -m "🔙 Откат временных изменений: включены ML фильтр и корректные лимиты"
git push origin main
```

---

## ⚠️ ВАЖНО

**НЕ ЗАБЫТЬ ВЕРНУТЬ ВСЕ ИЗМЕНЕНИЯ ОБРАТНО!**

Эти изменения были сделаны только для диагностики и тестирования.
