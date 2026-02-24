# 🔧 ОТЧЕТ: ИСПРАВЛЕНИЕ ОШИБКИ leverage_for_callback

## 📊 **ПРОБЛЕМА**

### **❌ Ошибка в логах:**

```
[DEBUG] Динамическое плечо для XRPUSDT: 1.3 (базовое: 1)
ERROR:root:[main_loop] Ошибка: local variable 'leverage_for_callback' referenced before assignment
Traceback (most recent call last):
  File "/Users/zhuchyok/Documents/GITHUB/atra/signal_live.py", line 3073, in main_loop
    signal_history = await check_and_send_signals(signal_history)
  File "/Users/zhuchyok/Documents/GITHUB/atra/signal_live.py", line 2982, in check_and_send_signals
    f"<code>/accept {symbol} {now.strftime('%Y-%m-%dT%H:%M')} {price:.2f} 1.0 {side.lower()} {risk_pct:.1f} {leverage_for_callback}</code>\n"
UnboundLocalError: local variable 'leverage_for_callback' referenced before assignment
```

### **🔍 Диагностика проблемы:**

**Проблема:** Переменная `leverage_for_callback` использовалась в строке 2982 до её определения в строке 2987.

**Логика ошибки:**

1. В строке 2982 формируется сообщение с использованием `leverage_for_callback`
2. Но переменная `leverage_for_callback` определяется только в строке 2987
3. Это приводит к ошибке `UnboundLocalError`

---

## 🔧 **ИСПРАВЛЕНИЕ**

### **✅ Что было исправлено:**

#### **Было (неправильно):**

```python
msg = (
    f"⚠️ Риск: <code>{risk_pct:.2f}%</code>"
    f"{f' | ⚡ Плечо: <code>x{dynamic_leverage}</code>' if trade_mode == 'futures' and dynamic_leverage else ''}\n"
    f"{btc_trend_info}\n"
    f"🔧 Режим: <code>{'Строгий' if filter_mode == 'balanced' else 'Мягкий'}</code> ({trade_mode})\n"
    f"{technical_analysis}"
    f"{news_info}\n"
    f"\n💡 <b>БЫСТРЫЕ КОМАНДЫ:</b>\n"
    f"• Принятие сигнала:\n"
    f"<code>/accept {symbol} {now.strftime('%Y-%m-%dT%H:%M')} {price:.2f} 1.0 {side.lower()} {risk_pct:.1f} {leverage_for_callback}</code>\n"  # ❌ ОШИБКА!
    f"• Активные позиции: <code>/positions</code>\n"
    f"• История сделок: <code>/trade_history</code>"
)

# Создаем клавиатуру
# Для фьючерсов передаем динамическое плечо, для спота - 1
leverage_for_callback = dynamic_leverage if trade_mode == 'futures' and dynamic_leverage else 1  # ❌ ОПРЕДЕЛЕНО ПОСЛЕ ИСПОЛЬЗОВАНИЯ!
```

#### **Стало (правильно):**

```python
msg = (
    f"⚠️ Риск: <code>{risk_pct:.2f}%</code>"
    f"{f' | ⚡ Плечо: <code>x{dynamic_leverage}</code>' if trade_mode == 'futures' and dynamic_leverage else ''}\n"
    f"{btc_trend_info}\n"
    f"🔧 Режим: <code>{'Строгий' if filter_mode == 'balanced' else 'Мягкий'}</code> ({trade_mode})\n"
    f"{technical_analysis}"
    f"{news_info}\n"
    f"\n💡 <b>БЫСТРЫЕ КОМАНДЫ:</b>\n"
    f"• Принятие сигнала:\n"
)

# Создаем клавиатуру
# Для фьючерсов передаем динамическое плечо, для спота - 1
leverage_for_callback = dynamic_leverage if trade_mode == 'futures' and dynamic_leverage else 1  # ✅ ОПРЕДЕЛЕНО ДО ИСПОЛЬЗОВАНИЯ

msg += (
    f"<code>/accept {symbol} {now.strftime('%Y-%m-%dT%H:%M')} {price:.2f} 1.0 {side.lower()} {risk_pct:.1f} {leverage_for_callback}</code>\n"  # ✅ ТЕПЕРЬ РАБОТАЕТ!
    f"• Активные позиции: <code>/positions</code>\n"
    f"• История сделок: <code>/trade_history</code>"
)
```

---

## 🎯 **ЛОГИКА ИСПРАВЛЕНИЯ**

### **📊 Порядок выполнения:**

1. **Формирование основной части сообщения** (без `leverage_for_callback`)
2. **Определение `leverage_for_callback`** на основе режима торговли
3. **Добавление быстрых команд** с использованием определенной переменной
4. **Создание callback_data** с правильным плечом

### **🔧 Логика определения плеча:**

```python
leverage_for_callback = dynamic_leverage if trade_mode == 'futures' and dynamic_leverage else 1
```

- **Для фьючерсов:** Используется динамическое плечо (если рассчитано)
- **Для спота:** Всегда используется плечо 1
- **Fallback:** Если динамическое плечо не рассчитано, используется 1

---

## ✅ **РЕЗУЛЬТАТЫ ИСПРАВЛЕНИЯ**

### **🎯 Что теперь работает:**

#### **1. Правильное формирование сообщений:**

- ✅ Переменная `leverage_for_callback` определяется до использования
- ✅ Нет ошибок `UnboundLocalError`
- ✅ Сообщения формируются корректно

#### **2. Корректная передача плеча:**

- ✅ В быстрых командах `/accept` передается правильное плечо
- ✅ В callback_data передается корректное значение
- ✅ Для фьючерсов - динамическое плечо, для спота - 1

#### **3. Стабильная работа системы:**

- ✅ Нет прерываний в main_loop
- ✅ Сигналы отправляются без ошибок
- ✅ Плечо отображается правильно

### **📊 Примеры работы:**

#### **Для фьючерсов:**

```
⚡ Плечо: x1.3
💡 БЫСТРЫЕ КОМАНДЫ:
• Принятие сигнала:
/accept XRPUSDT 2024-01-15T12:00 0.52 1.0 long 2.0 1.3
```

#### **Для спота:**

```
💡 БЫСТРЫЕ КОМАНДЫ:
• Принятие сигнала:
/accept XRPUSDT 2024-01-15T12:00 0.52 1.0 long 2.0 1
```

---

## 🛡️ **ПРЕДОТВРАЩЕНИЕ ПОВТОРЕНИЯ**

### **📋 Рекомендации для разработчиков:**

1. **Порядок определения переменных:**
   - Всегда определяйте переменные до их использования
   - Используйте `+=` для добавления к уже созданным строкам

2. **Проверка зависимостей:**
   - Проверяйте, что все переменные определены перед использованием
   - Используйте IDE для выявления неопределенных переменных

3. **Структура кода:**
   - Разделяйте формирование сообщений на логические блоки
   - Определяйте все необходимые переменные в начале блока

### **🔍 Тестирование:**

- ✅ Проверка формирования сообщений
- ✅ Проверка передачи плеча в командах
- ✅ Проверка работы callback_data
- ✅ Проверка стабильности main_loop

---

## 📋 **ЗАКЛЮЧЕНИЕ**

### **✅ Проблема решена:**

1. **✅ Ошибка исправлена** - переменная определяется до использования
2. **✅ Система стабильна** - нет прерываний в main_loop
3. **✅ Плечо передается правильно** - для фьючерсов и спота
4. **✅ Сообщения формируются корректно** - все данные отображаются

### **🎯 Результат:**

Система генерации сигналов теперь работает **стабильно и без ошибок**, правильно передавая динамическое плечо в команды и callback_data.
