# 🎯 Обновление иконок для Take Profit

## ✅ **ИЗМЕНЕНИЯ:**

Добавлены единообразные иконки для TP1 и TP2 во всех местах системы:

### **🎯 TP1 (основная цель):**

- **Иконка:** 🎯
- **Значение:** Основная цель прибыли

### **🚀 TP2 (максимальная цель):**

- **Иконка:** 🚀
- **Значение:** Максимальная цель прибыли

## 📁 **ОБНОВЛЕННЫЕ ФАЙЛЫ:**

### **1. signal_live.py (основные торговые сигналы):**

```python
# Было:
tp_info = f"TP1: {fmt.format(tp1)} ({'+' if side == 'LONG' else '-'}{tp1_pct:.1f}%)\nTP2: {fmt.format(tp2)} ({'+' if side == 'LONG' else '-'}{tp2_pct:.1f}%)"

# Стало:
tp_info = f"🎯 TP1: {fmt.format(tp1)} ({'+' if side == 'LONG' else '-'}{tp1_pct:.1f}%)\n🚀 TP2: {fmt.format(tp2)} ({'+' if side == 'LONG' else '-'}{tp2_pct:.1f}%)"
```

### **2. telegram_bot.py (позиции):**

```python
# Было:
pos_str = f"{pos['symbol']} | Вход: {pos['entry_price']} | TP1: {pos['tp1']} | TP2: {pos['tp2']} | Стадия: {pos.get('stage', 'open')}"

# Стало:
pos_str = f"{pos['symbol']} | Вход: {pos['entry_price']} | 🎯 TP1: {pos['tp1']} | 🚀 TP2: {pos['tp2']} | Стадия: {pos.get('stage', 'open')}"
```

### **3. telegram_bot.py (статистика сигналов):**

```python
# Было:
f"🎯 TP1: `{tp1:.6f}` | 🎯 TP2: `{tp2:.6f}`\n\n"

# Стало:
f"🎯 TP1: `{tp1:.6f}` | 🚀 TP2: `{tp2:.6f}`\n\n"
```

### **4. telegram_bot.py (тестовые сигналы):**

```python
# Было:
f"Монета: {symbol}\nВход: {entry_price}\nTP1: {tp1}\nTP2: {tp2}\nРиск: {risk_pct:.2f}%"

# Стало:
f"Монета: {symbol}\nВход: {entry_price}\n🎯 TP1: {tp1}\n🚀 TP2: {tp2}\nРиск: {risk_pct:.2f}%"
```

### **5. telegram_bot.py (открытие позиций):**

```python
# Было:
f"Средняя цена: {fmt.format(avg_price_new)}\nTP1: {fmt.format(tp1)}\nTP2: {fmt.format(tp2)}\n"

# Стало:
f"Средняя цена: {fmt.format(avg_price_new)}\n🎯 TP1: {fmt.format(tp1)}\n🚀 TP2: {fmt.format(tp2)}\n"
```

## 🎯 **РЕЗУЛЬТАТ:**

✅ **Единообразие** - все TP1 и TP2 теперь имеют одинаковые иконки во всей системе
✅ **Визуальное различие** - легко отличить TP1 от TP2
✅ **Улучшенный UX** - пользователи быстрее понимают уровни целей

## 📱 **ПРИМЕР ОТОБРАЖЕНИЯ:**

```
🟢 НОВЫЙ ТОРГОВЫЙ СИГНАЛ

📊 Символ: `BTCUSDT`
💰 Цена входа: `65,432.10`
📈 Сторона: `LONG`
🎯 TP1: 65,987.45 (+0.85%)
🚀 TP2: 66,542.80 (+1.70%)
⚠️ Риск: `2.50%`
```

**Система теперь имеет единообразные и понятные иконки для всех уровней Take Profit!** 🎯🚀
