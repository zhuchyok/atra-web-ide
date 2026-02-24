# 🚀 БЫСТРЫЙ СПРАВОЧНИК ATRA

## **⚡ ЭКСТРЕННЫЕ ИСПРАВЛЕНИЯ**

### **🔧 ПРОБЛЕМА: Неправильные расчеты в принятых сигналах**

**БЫСТРОЕ РЕШЕНИЕ:**

```python
# В telegram_bot.py - замени пересчет на прямое использование
# БЫЛО:
from signal_live import get_dynamic_leverage, get_dynamic_risk_pct
dynamic_risk_pct = get_dynamic_risk_pct(df, current_index)

# СТАЛО:
dynamic_risk_pct = risk_pct  # Используй переданный параметр
dynamic_leverage = leverage  # Используй переданный параметр
```

### **🔧 ПРОБЛЕМА: Несоответствие TP и объема**

**БЫСТРОЕ РЕШЕНИЕ:**

```python
# Все расчеты на момент принятия
current_price = ohlc[-1]["close"]  # Актуальная цена
tp1 = current_price * (1 + dynamic_tp1_pct / 100)  # TP на актуальной цене
qty = risk_amount / current_price * dynamic_leverage  # Объем на актуальной цене
```

### **🔧 ПРОБЛЕМА: Неправильный расчет свободных средств**

**БЫСТРОЕ РЕШЕНИЕ:**

```python
# Правильный расчет
total_risk = sum(pos.get("risk_amount", 0) for pos in open_positions)
free_deposit = max(deposit - total_risk, 0)
```

---

## **📱 СТАНДАРТЫ СООБЩЕНИЙ**

### **HTML ФОРМАТИРОВАНИЕ:**

```python
msg = f"✅ <b>СИГНАЛ ПРИНЯТ!</b>\n\n💰 <b>Депозит:</b> <code>{deposit:.2f} USDT</code>"
await query.message.reply_text(msg, parse_mode="HTML")
```

### **КРАТКИЕ СООБЩЕНИЯ:**

```python
# БЫЛО: "⚠️ *АВТОМАТИЧЕСКИЙ РИСК*\n\n🎯 **Система учитывает:**"
# СТАЛО: "⚠️ Риск автоматически рассчитывается системой!"
```

---

## **🤖 КОМАНДЫ BOTFATHER**

### **ОПТИМИЗИРОВАННЫЙ СПИСОК:**

```
start - 🚀 Начать работу
help - ❓ Список команд
set_balance - 💰 Установить депозит
balance - 💎 Показать баланс
positions - 📊 Открытые позиции
myreport - 👤 Персональный отчет
accept - ✅ Принять сигнал
set_trade_mode - ⚙️ Режим торговли
set_filter_mode - 🎯 Режим фильтров
status - 📈 Статус бота
health - 🤖 Здоровье системы
report - 📋 Отчет за день
report_week - 📊 Отчет за неделю
list_users - 👥 Список пользователей
add_user - ➕ Добавить пользователя
remove_user - ➖ Удалить пользователя
signal_stats - 📊 Статистика сигналов
```

---

## **🔍 ДИАГНОСТИКА**

### **ОТЛАДОЧНЫЕ ПРИНТЫ:**

```python
print(f"[DEBUG] callback_data: {data}")
print(f"[DEBUG] Актуальная цена: {current_price}")
print(f"[DEBUG] Расчет TP: TP1={tp1:.2f}, TP2={tp2:.2f}")
print(f"[DEBUG] Свободные средства: {free_deposit:.2f}")
```

### **ПРОВЕРКА ДАННЫХ:**

```python
print(f"[DEBUG] Пользовательские данные: {user_data}")
print(f"[DEBUG] Открытые позиции: {open_positions}")
```

---

## **⚡ БЫСТРЫЕ ШАБЛОНЫ**

### **CALLBACK_DATA:**

```python
callback_data = f'accept|{symbol}|{short_time}|{short_price}|{side.lower()}|{short_risk}|{short_leverage}|{short_tp1}|{short_tp2}'
```

### **ПАРСИНГ:**

```python
risk_pct = float(data[5]) if len(data) > 5 else user_data.get("risk_pct", 2.0)
leverage = float(data[6]) if len(data) > 6 else user_data.get("leverage", 1)
tp1_pct = float(data[7]) if len(data) > 7 else 1.0
tp2_pct = float(data[8]) if len(data) > 8 else 2.0
```

### **РАСЧЕТ СРЕДСТВ:**

```python
total_risk = sum(pos.get("risk_amount", 0) for pos in open_positions)
free_deposit = max(deposit - total_risk, 0)
```

### **РАСЧЕТ TP:**

```python
tp1 = current_price * (1 + dynamic_tp1_pct / 100)
tp2 = current_price * (1 + dynamic_tp2_pct / 100)
```

---

## **🚨 ЧАСТЫЕ ОШИБКИ**

### **"string not found" при search_replace:**

1. Используй `grep_search` для поиска точного текста
2. Скопируй найденный текст с точными отступами
3. Примени `search_replace`

### **Неправильные расчеты:**

1. Проверь передачу параметров через `callback_data`
2. Убедись, что нет пересчета в `telegram_bot.py`
3. Проверь, что все расчеты на момент принятия

### **Несоответствие данных:**

1. Добавь отладочные принты
2. Проверь актуальность цен
3. Убедись в правильности расчетов

---

## **✅ ЧЕКЛИСТ**

### **ПЕРЕД ЗАПУСКОМ:**

- [ ] Динамические параметры передаются через `callback_data`
- [ ] Нет пересчета в `telegram_bot.py`
- [ ] Все расчеты на момент принятия
- [ ] Правильный расчет свободных средств
- [ ] HTML форматирование сообщений
- [ ] Обновлены команды BotFather

### **ПРИ ТЕСТИРОВАНИИ:**

- [ ] Новые сигналы принимаются корректно
- [ ] DCA сигналы работают правильно
- [ ] TP уровни соответствуют актуальной цене
- [ ] Свободные средства рассчитываются верно
- [ ] Сообщения отображаются корректно

---

## **📞 ЭКСТРЕННАЯ ПОМОЩЬ**

**При критических проблемах:**

1. 🔍 Проверь этот справочник
2. 📖 Обратись к `COMPREHENSIVE_SYSTEM_GUIDE.md`
3. 🔧 Примени быстрые исправления
4. ✅ Протестируй изменения

**Система должна работать стабильно!** 🚀
