# 🔍 ОТЧЕТ: АНАЛИЗ МЕСТ ХРАНЕНИЯ СИГНАЛОВ

**Дата анализа:** 18 ноября 2025  
**Проблема:** Сигналы от 17.11.2025 не найдены в основных таблицах

---

## 📊 **ВЫЯВЛЕННАЯ ПРОБЛЕМА**

### **Сигналы от 17.11.2025 (SUIUSDT, LINKUSDT) были отправлены в Telegram, но:**

- ❌ **НЕ найдены в `signals_log`** (последние записи от 9 ноября)
- ❌ **НЕ найдены в `accepted_signals`** (последние записи от 26 октября)
- ❌ **НЕ найдены в `risk_signal_history`** (последние записи от 10 ноября)

### **Вывод:**

Сигналы **отправляются в Telegram**, но **НЕ сохраняются в базу данных** при отправке!

---

## 🔍 **АНАЛИЗ КОДА**

### **1. Функция `send_signal` (signal_live.py):**

```python
async def send_signal(...):
    # ... формирование сообщения ...
    # ... отправка в Telegram ...

    # ❌ ОТСУТСТВУЕТ: Сохранение в signals_log
    # ❌ ОТСУТСТВУЕТ: Регистрация через signal_acceptance_manager
    # ❌ ОТСУТСТВУЕТ: Сохранение в accepted_signals

    # ✅ ЕСТЬ: Сохранение в correlation_manager (только для истории рисков)
    await correlation_manager.save_signal_to_history_async(...)

    # ✅ ЕСТЬ: Добавление в signal_history (только в памяти)
    signal_history.append(signal_data)
```

### **2. Где ДОЛЖНЫ сохраняться сигналы:**

#### **A. При отправке в Telegram:**

- **`accepted_signals`** - через `signal_acceptance_manager.register_signal()`
- **`signals_log`** - через `db.insert_signal_log_entry()` или `db.insert_signal_log()`

#### **B. При принятии (кнопка "ПРИНЯТЬ"):**

- **`accepted_signals`** - обновление статуса на "accepted"
- **`signals_log`** - обновление result на "OPEN"
- **`active_positions`** - создание новой позиции

### **3. Текущая ситуация:**

**Сигналы сохраняются ТОЛЬКО при принятии:**

- ✅ При нажатии кнопки "ПРИНЯТЬ" → сохраняется в `accepted_signals` и `signals_log`
- ❌ При отправке в Telegram → **НЕ сохраняется нигде**

---

## 🎯 **РЕШЕНИЕ ПРОБЛЕМЫ**

### **Нужно добавить сохранение сигналов в `send_signal`:**

```python
async def send_signal(...):
    # ... существующий код ...

    # 🆕 ДОБАВИТЬ: Регистрация сигнала в системе принятия
    if SIGNAL_ACCEPTANCE_AVAILABLE and signal_acceptance_manager:
        try:
            signal_data_obj = SignalData(
                symbol=symbol,
                direction=signal_type,
                entry_price=signal_price,
                signal_time=datetime.now(),
                user_id=str(user_data.get("user_id")),
                chat_id=user_data.get("user_id"),
                tp1_price=tp1_price,
                tp2_price=tp2_price,
                sl_price=sl_price,
                leverage=leverage,
                risk_percent=risk_pct,
                entry_amount=entry_amount_usdt,
                confidence=ai_confidence
            )

            # Регистрируем сигнал (сохранит в accepted_signals)
            message_id = ...  # Получить из отправки в Telegram
            await signal_acceptance_manager.register_signal(
                signal_data_obj,
                message_id,
                user_data.get("user_id")
            )
        except Exception as e:
            logger.error("❌ Ошибка регистрации сигнала: %s", e)

    # 🆕 ДОБАВИТЬ: Сохранение в signals_log
    try:
        from db import db
        db.insert_signal_log_entry({
            "symbol": symbol,
            "entry": signal_price,
            "stop": sl_price,
            "tp1": tp1_price,
            "tp2": tp2_price,
            "entry_time": datetime.now().isoformat(),
            "result": "PENDING",  # Статус до принятия
            "user_id": user_data.get("user_id"),
            # ... другие поля ...
        })
    except Exception as e:
        logger.error("❌ Ошибка сохранения в signals_log: %s", e)
```

---

## 📋 **ТАБЛИЦЫ БАЗЫ ДАННЫХ**

### **1. `signals_log` (trading.db):**

- **Назначение:** Основная таблица для всех сигналов
- **Когда сохраняется:** ❌ НЕ сохраняется при отправке
- **Когда обновляется:** ✅ При принятии (PENDING → OPEN)

### **2. `accepted_signals` (trading.db):**

- **Назначение:** Сигналы с кнопками принятия
- **Когда сохраняется:** ❌ НЕ сохраняется при отправке
- **Когда обновляется:** ✅ При принятии (pending → accepted)

### **3. `risk_signal_history` (trading.db):**

- **Назначение:** История для расчета корреляционных рисков
- **Когда сохраняется:** ✅ При отправке (через correlation_manager)
- **Проблема:** Не содержит полной информации о сигнале

---

## ✅ **РЕКОМЕНДАЦИИ**

### **Немедленные действия:**

1. **Добавить сохранение в `send_signal`:**
   - Регистрация через `signal_acceptance_manager.register_signal()`
   - Сохранение в `signals_log` через `db.insert_signal_log_entry()`

2. **Проверить, что `message_id` доступен:**
   - Нужно получить `message_id` из результата отправки в Telegram
   - Передать его в `register_signal()`

3. **Обновить скрипт диагностики:**
   - Проверять `accepted_signals` с фильтром по дате
   - Проверять `risk_signal_history` для сигналов без принятия

### **Долгосрочные улучшения:**

1. **Единая точка сохранения:**
   - Создать функцию `save_signal_to_all_storage()`
   - Вызывать её из `send_signal`

2. **Логирование:**
   - Логировать все попытки сохранения
   - Логировать ошибки сохранения

3. **Мониторинг:**
   - Алерты при отсутствии сохранения
   - Проверка целостности данных

---

## 🔗 **СВЯЗАННЫЕ ФАЙЛЫ**

- `signal_live.py` - функция `send_signal()` (строки 3099-4300)
- `signal_acceptance_manager.py` - функция `register_signal()` (строка 84)
- `acceptance_database.py` - функция `save_signal()` (строка 153)
- `db.py` - функция `insert_signal_log_entry()` (строка 1654)

---

**Следующий шаг:** Добавить сохранение сигналов в `send_signal` перед отправкой в Telegram.
