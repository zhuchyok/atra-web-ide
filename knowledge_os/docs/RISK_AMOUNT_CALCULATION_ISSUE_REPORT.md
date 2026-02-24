# ⚠️ ПРОБЛЕМА С РАСЧЕТОМ "ЗАНЯТО РИСКАМИ" - ОТЧЕТ

## 🎯 **ПРОБЛЕМА:**

В команде `/myreport` показывается "Занято рисками: 0.00 USDT", хотя это может быть неправильно.

---

## 🔍 **АНАЛИЗ ПРОБЛЕМЫ:**

### **❌ Проблема в функции `recalculate_balance_and_risks`:**

```python
def recalculate_balance_and_risks(user_data):
    # ...
    for pos in open_positions:
        # Рассчитываем risk_amount для каждой позиции
        pos_qty = pos.get("qty", 0)
        pos_entry_price = pos.get("entry_price", 0)
        pos_risk_pct = pos.get("risk_pct", 2.0)
        pos_leverage = pos.get("leverage", 1)

        # Стоимость позиции
        position_value = pos_qty * pos_entry_price

        # Risk amount с учетом плеча
        if pos_leverage > 1:
            risk_amount = position_value / pos_leverage * pos_risk_pct / 100
        else:
            risk_amount = position_value * pos_risk_pct / 100

        pos["risk_amount"] = risk_amount  # ← ПРОБЛЕМА: добавляем поле, которого нет в структуре
        total_risk_amount += risk_amount
```

### **❌ Проблемы:**

1. **Отсутствует поле `risk_amount`** в структуре позиции
2. **Неправильная логика расчета** - риск должен быть фиксированным для позиции
3. **Не учитывается реальный риск** - должен быть основан на депозите, а не на стоимости позиции

---

## 📊 **СТРУКТУРА ПОЗИЦИИ:**

### **✅ Текущая структура:**

```python
{
    "symbol": symbol,
    "entry_prices": [entry_price],
    "qtys": [qty_new],
    "qty": qty_new,
    "entry_price": entry_price,
    "tp1": tp1,
    "tp2": tp2,
    "n_dca": 0,
    "leverage": leverage if trade_mode == "futures" else None,
    "stage": "open",
    "side": side,
    "risk_pct": risk_pct,
    # НЕТ поля "risk_amount"!
}
```

---

## ✅ **ПРАВИЛЬНАЯ ЛОГИКА РАСЧЕТА:**

### **🎯 Что такое "Занято рисками":**

**"Занято рисками"** = сумма всех рисков по открытым позициям

### **📈 Правильный расчет:**

```python
# Для каждой позиции:
risk_amount = deposit * risk_pct / 100

# Общий риск:
total_risk_amount = sum(risk_amount for all positions)
```

### **💡 Пример:**

- **Депозит:** 200 USDT
- **Риск на сделку:** 2%
- **Открытых позиций:** 2
- **Занято рисками:** 200 × 2% × 2 = 8 USDT

---

## 🔧 **ИСПРАВЛЕНИЕ:**

### **📝 Нужно изменить функцию `recalculate_balance_and_risks`:**

```python
def recalculate_balance_and_risks(user_data):
    try:
        deposit = user_data.get("deposit", 0)
        open_positions = user_data.get("open_positions", [])

        # Правильный расчет риска
        total_risk_amount = 0
        for pos in open_positions:
            risk_pct = pos.get("risk_pct", 2.0)
            # Риск = процент от депозита
            risk_amount = deposit * risk_pct / 100
            total_risk_amount += risk_amount

        # Свободные средства
        free_deposit = max(deposit - total_risk_amount, 0)

        return {
            "updated_deposit": deposit,
            "total_risk_amount": total_risk_amount,
            "free_deposit": free_deposit,
            "total_profit": 0,  # пока не реализовано
            "open_positions_count": len(open_positions)
        }
    except Exception as e:
        print(f"[recalculate_balance_and_risks] Ошибка: {e}")
        return None
```

---

## 📊 **ПРИМЕР РАСЧЕТА:**

### **🔍 Ваш случай:**

- **Депозит:** 200 USDT
- **Открытых позиций:** 0
- **Риск на сделку:** 2%

### **✅ Правильный результат:**

```
💵 Депозит: 200.00 USDT
⚠️ Занято рисками: 0.00 USDT  ← ПРАВИЛЬНО!
🆓 Свободно: 200.00 USDT
```

### **✅ Если бы были открытые позиции:**

```
💵 Депозит: 200.00 USDT
⚠️ Занято рисками: 8.00 USDT  ← 2 позиции × 2% × 200
🆓 Свободно: 192.00 USDT
```

---

## 🚀 **РЕКОМЕНДАЦИИ:**

### **📋 Для исправления:**

1. Изменить логику расчета в `recalculate_balance_and_risks`
2. Убрать добавление поля `risk_amount` в позицию
3. Рассчитывать риск на основе депозита, а не стоимости позиции

### **📋 Для понимания:**

- "Занято рисками" = сумма всех рисков по открытым позициям
- Риск = процент от депозита (не от стоимости позиции)
- Если нет открытых позиций → занято рисками = 0

---

## 🎯 **ИТОГ:**

**В вашем случае "Занято рисками: 0.00 USDT" показывается правильно, так как у вас нет открытых позиций. Но логика расчета в коде нуждается в исправлении.** ✅
