# ✅ РЕЖИМЫ MANUAL/AUTO - ПОЛНАЯ РЕАЛИЗАЦИЯ

**Дата:** 2025-01-31  
**Статус:** ✅ **PRODUCTION READY**

---

## 🎯 РЕАЛИЗОВАНО

### **1. Хранение режима пользователя**

- Таблица `user_settings` с полем `trade_mode` (manual|auto)
- По умолчанию: `manual`
- Методы: `get_user_mode()`, `set_user_mode()`

### **2. Telegram команды**

- `/mode` — показать текущий режим
- `/mode_set manual` — ручной режим
- `/mode_set auto` — автоматический режим
- `/connect_bitget <api> <secret> <passphrase>` — подключить ключи Bitget
- `/disconnect_bitget` — отключить ключи

### **3. Статусы сигналов**

- **PENDING** — отправлен, ожидает действия (manual) или fill (auto)
- **OPEN** — принят/исполнен
- **EXPIRED** — истёк по TTL (60 мин)
- **CLOSED** — позиция закрыта

### **4. Manual режим**

```
Сигнал отправлен → PENDING
  ↓
Пользователь нажал /accept → PENDING → OPEN
  ↓
Создаётся запись в active_positions
  ↓
Корреляция учитывает только OPEN из signals_log
```

### **5. Auto режим**

```
Сигнал отправлен → PENDING
  ↓
AutoExecutionService создаёт ордер на бирже
  ↓
Лимитный ордер (90 сек) → если не fill → маркет ордер
  ↓
После подтверждения fill → PENDING → OPEN
  ↓
Запись в active_positions
  ↓
Корреляция учитывает реальные позиции с биржи (active_positions)
```

### **6. Биржевая интеграция**

- `ExchangeAdapter` через ccxt (Bitget/Binance)
- Методы: `create_limit_order`, `create_market_order`, `wait_for_fill`, `fetch_positions`
- Хранение ключей: таблица `user_exchange_keys`

### **7. Синхронизация позиций (auto)**

- Каждые 3 минуты: fetch_positions с биржи
- Обновление локальных позиций
- Закрытие позиций, которых нет на бирже → signals_log: OPEN → CLOSED

### **8. TTL для PENDING**

- Фоновая задача каждые 5 минут
- PENDING старше 60 минут → EXPIRED
- EXPIRED не блокирует корреляцией

### **9. Корреляционная проверка по режимам**

- **Manual:** учитывает только `signals_log.result='OPEN'`
- **Auto:** учитывает реальные позиции из `active_positions` (синхронизированные с биржей)
- PENDING не блокирует в обоих режимах

---

## 📊 АРХИТЕКТУРА

### **Файлы:**

#### **acceptance_database.py**

- `user_settings` (trade_mode)
- `user_exchange_keys` (api_key, secret, passphrase)
- Методы: `get/set_user_mode`, `save/get_exchange_keys`, `expire_pending_signals`
- `create_active_position`, `upsert_active_position`, `close_active_position_by_symbol`

#### **exchange_adapter.py**

- `ExchangeAdapter` класс
- Поддержка Bitget/Binance через ccxt
- Грейсфул fallback если ccxt недоступен

#### **auto_execution.py**

- `AutoExecutionService.execute_and_open()`
- Создание ордеров, ожидание fill, fallback на маркет
- Обновление signals_log и active_positions после fill

#### **signal_live.py**

- После успешной отправки сигнала: проверка режима пользователя
- Если auto → автоматический вызов `AutoExecutionService`

#### **correlation_risk_manager.py**

- `_get_user_open_positions()`: определяет режим пользователя
- Manual: `signals_log.result='OPEN'`
- Auto: `active_positions.status='open'`

#### **telegram_handlers.py**

- Команды: `mode_cmd`, `mode_set_cmd`, `connect_bitget_cmd`, `disconnect_bitget_cmd`

#### **telegram_bot_core.py**

- Регистрация всех команд в боте

#### **main.py**

- Фоновая задача: `expire_pending_periodically()` (TTL)
- Фоновая задача: `sync_positions_periodically()` (синхронизация с биржей для auto)

#### **db.py**

- Изменено: `INSERT signals_log` теперь `result='PENDING'` (было `'OPEN'`)

---

## 🔄 ЛОГИКА РАБОТЫ

### **Сценарий 1: Manual режим**

1. Пользователь: `/mode_set manual`
2. Система отправляет сигнал BTCUSDT BUY → `signals_log.result='PENDING'`
3. Корреляция: PENDING не блокирует
4. Пользователь: `/accept` → `signals_log.result='OPEN'` + `active_positions`
5. Корреляция теперь учитывает BTCUSDT как открытую позицию
6. TTL: если не принять за 60 мин → `EXPIRED`

### **Сценарий 2: Auto режим**

1. Пользователь: `/connect_bitget <api> <secret> <passphrase>`
2. Пользователь: `/mode_set auto`
3. Система отправляет сигнал ETHUSDT BUY → `signals_log.result='PENDING'`
4. `AutoExecutionService`:
   - Создаёт лимитный ордер на Bitget
   - Ждёт 90 секунд
   - Если не fill → создаёт маркет ордер
5. После fill: `signals_log.result='OPEN'` + `active_positions`
6. Фоновая синхронизация (каждые 3 мин):
   - Получает позиции с Bitget
   - Обновляет `active_positions`
   - Если позиция закрыта на бирже → локально `CLOSED`
7. Корреляция учитывает реальные позиции с биржи

### **Сценарий 3: Смешанный портфель**

- User A (manual): 3 PENDING, 2 OPEN → корреляция блокирует по 2 OPEN
- User B (auto): 1 PENDING, 5 OPEN (с биржи) → корреляция блокирует по 5 реальным

---

## 🛡️ ЗАЩИТЫ И ПРОВЕРКИ

### **1. Идемпотентность**

- `signal_key` уникален для каждого сигнала
- Дубли не создаются

### **2. Противоположные сигналы**

- Блокировка LONG+SHORT на один актив (correlation_risk_manager)

### **3. TTL PENDING**

- Автоматическое истечение через 60 минут
- EXPIRED не участвуют в корреляции

### **4. Синхронизация с биржей (auto)**

- Расхождения автоматически исправляются каждые 3 минуты
- Закрытые на бирже позиции закрываются локально

### **5. Fallback при ошибках**

- Если ccxt недоступен → работает в режиме без реальных ордеров
- Если биржа недоступна → локальная БД продолжает работать
- Корреляция работает даже при сбоях внешних систем

---

## 📈 ПРЕИМУЩЕСТВА

### **Manual режим:**

- ✅ Полный контроль пользователя
- ✅ Не требует ключей биржи
- ✅ Сигналы не блокируются до принятия
- ✅ TTL автоматически очищает старые PENDING

### **Auto режим:**

- ✅ Автоматическое исполнение
- ✅ Реальная торговля на бирже
- ✅ Синхронизация с биржей (источник правды)
- ✅ Лимит → маркет fallback для надёжности
- ✅ Корреляция по реальным позициям

### **Общие:**

- ✅ Безопасное переключение режимов
- ✅ Персональные настройки для каждого пользователя
- ✅ Корреляция адаптируется под режим
- ✅ Грейсфул работа при сбоях

---

## 🧪 ТЕСТИРОВАНИЕ

### **Manual режим:**

```bash
/mode_set manual
# Ожидание: сигнал приходит, статус PENDING
# Действие: /accept
# Результат: OPEN, позиция учитывается в корреляции
```

### **Auto режим:**

```bash
/connect_bitget <api_key> <secret> <passphrase>
/mode_set auto
# Ожидание: сигнал приходит → автоматическое исполнение
# Результат: ордер на бирже, после fill → OPEN
# Проверка: позиция синхронизирована с биржей
```

### **TTL:**

```bash
# Отправить сигнал, не принимать 60+ минут
# Результат: автоматически EXPIRED
```

### **Корреляция:**

```bash
# Manual: открыта позиция BTCUSDT → блокируется ETHUSDT (если корреляция > 0.75)
# Auto: реальная позиция BTCUSDT на бирже → блокируется ETHUSDT
```

---

## 🚀 ГОТОВО К PRODUCTION

**Все этапы завершены:**

- ✅ Хранение режима пользователя
- ✅ Telegram команды
- ✅ PENDING/OPEN/EXPIRED/CLOSED статусы
- ✅ Manual режим с /accept
- ✅ Auto режим с реальными ордерами
- ✅ Биржевая интеграция (Bitget/Binance)
- ✅ Синхронизация позиций
- ✅ TTL для PENDING
- ✅ Корреляция по источникам
- ✅ Защиты и fallback

**Система работает как живой организм:**

- Автоматическое истечение старых сигналов
- Синхронизация с биржей
- Адаптация корреляции под режим
- Грейсфул обработка ошибок

---

**СТАТУС: ГОТОВО К ЗАПУСКУ** ✅🚀
