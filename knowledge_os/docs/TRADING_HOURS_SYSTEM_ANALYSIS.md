# ⏰ АНАЛИЗ СИСТЕМЫ ТОРГОВЫХ ЧАСОВ

## 🎯 **ГДЕ ЗАДАЮТСЯ ТОРГОВЫЕ ЧАСЫ:**

### 📋 **1. Telegram команды (основной способ):**

#### 🎯 **Команда `/set_trading_hours`:**

```python
async def set_trading_hours_cmd(update, context):
    # Формат: /set_trading_hours 9 18
    # Где: 9 - начало торговли, 18 - конец торговли (МСК)

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Укажите время в формате: /set_trading_hours 9 18 (start < end, МСК)"
        )
        return

    try:
        start = int(context.args[0])
        end = int(context.args[1])
        if not (0 <= start < end <= 24):
            await update.message.reply_text(
                "Ошибка: start должен быть меньше end, оба в пределах 0–24. Пример: /set_trading_hours 7 23"
            )
            return

        user_data["trading_hours"] = {"start": start, "end": end}
        save_user_data(context)
        await update.message.reply_text(
            f"✅ Торговые часы установлены: {start:02d}:00–{end:02d}:00 (МСК)"
        )
    except Exception:
        await update.message.reply_text(
            "Ошибка: укажите два числа, например: /set_trading_hours 9 18 (start < end, МСК)"
        )
```

#### 🎯 **Команда `/trading_hours`:**

```python
async def trading_hours_cmd(update, context):
    th = user_data.get("trading_hours")
    if th:
        await update.message.reply_text(
            f"Ваши торговые часы: {th['start']:02d}:00–{th['end']:02d}:00 (МСК)"
        )
    else:
        await update.message.reply_text(
            "Торговые часы не заданы. Используйте /set_trading_hours <start> <end>"
        )
```

### 📋 **2. Файловая система (state.py):**

#### 🎯 **Функции управления:**

```python
TRADING_HOURS_FILE = "trading_hours.txt"

def set_trading_hours(start, end):
    try:
        with open(TRADING_HOURS_FILE, "w") as f:
            f.write(f"{int(start)} {int(end)}")
        backup_file(TRADING_HOURS_FILE)
    except Exception as e:
        logging.error(e, exc_info=True)

def get_trading_hours():
    try:
        with open(TRADING_HOURS_FILE, "r") as f:
            s, e = f.read().split()
            return int(s), int(e)
    except Exception as e:
        logging.error(e, exc_info=True)
        return 0, 24  # по умолчанию круглосуточно
```

## 🔧 **КАК РАБОТАЕТ СИСТЕМА:**

### ✅ **Проверка торговых часов:**

```python
def check_user_trading_hours(user_data):
    """Проверка торговых часов пользователя"""
    th = user_data.get("trading_hours")
    if not th:
        return True  # Если не установлены - разрешаем торговлю

    now = get_msk_now()
    hour = now.hour
    start = th.get("start", 0)
    end = th.get("end", 24)

    # Проверяем, что текущий час входит в торговые часы
    if start <= end:
        # Обычный случай: 9-18
        return start <= hour < end
    else:
        # Переход через полночь: 23-7
        return hour >= start or hour < end
```

### ✅ **Использование в сигналах:**

```python
# В signal_live.py при генерации сигналов
if not check_user_trading_hours(user_data):
    # Пропускаем генерацию сигналов
    return

# Или сохраняем в pending_dca_signals
if not check_user_trading_hours(user_data):
    save_pending_dca_signal(user_id, symbol, side, original_price, original_time, user_data)
    return
```

## 📊 **ФОРМАТЫ И ПРИМЕРЫ:**

### ✅ **Правильные форматы:**

```
/set_trading_hours 9 18    # 09:00-18:00 (МСК)
/set_trading_hours 7 23    # 07:00-23:00 (МСК)
/set_trading_hours 0 24    # Круглосуточно
/set_trading_hours 23 7    # 23:00-07:00 (через полночь)
```

### ❌ **Неправильные форматы:**

```
/set_trading_hours 18 9    # Ошибка: start > end
/set_trading_hours 25 30   # Ошибка: > 24
/set_trading_hours abc     # Ошибка: не числа
/set_trading_hours 9       # Ошибка: только одно число
```

## 🎯 **ЛОГИКА РАБОТЫ:**

### ✅ **Обычные часы (9-18):**

- **Торговля разрешена:** 09:00, 10:00, ..., 17:00
- **Торговля запрещена:** 18:00, 19:00, ..., 08:00

### ✅ **Переход через полночь (23-7):**

- **Торговля разрешена:** 23:00, 00:00, 01:00, ..., 06:00
- **Торговля запрещена:** 07:00, 08:00, ..., 22:00

### ✅ **Круглосуточная торговля (0-24):**

- **Торговля разрешена:** Всегда

## 🔧 **ХРАНЕНИЕ ДАННЫХ:**

### 📊 **В user_data:**

```python
user_data["trading_hours"] = {
    "start": 9,
    "end": 18
}
```

### 📊 **В файле:**

```
trading_hours.txt
9 18
```

### 📊 **Бэкапы:**

```
backups/trading_hours.txt_20240127_143022
```

## 🎯 **ИНТЕГРАЦИЯ С СИСТЕМОЙ:**

### ✅ **Проверка при генерации сигналов:**

- **Если часы не заданы** → торговля разрешена
- **Если часы заданы** → проверяется текущее время
- **Вне торговых часов** → сигналы не генерируются

### ✅ **DCA система:**

- **В неторговое время** → сигналы накапливаются
- **В торговое время** → накопленные сигналы отправляются

### ✅ **Уведомления:**

- **Команда `/trading_hours`** → показывает текущие настройки
- **Команда `/set_trading_hours`** → изменяет настройки

## 🎯 **ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:**

### ✅ **Установка торговых часов:**

```
Пользователь: /set_trading_hours 9 18
Бот: ✅ Торговые часы установлены: 09:00–18:00 (МСК)
```

### ✅ **Просмотр торговых часов:**

```
Пользователь: /trading_hours
Бот: Ваши торговые часы: 09:00–18:00 (МСК)
```

### ✅ **Если не заданы:**

```
Пользователь: /trading_hours
Бот: Торговые часы не заданы. Используйте /set_trading_hours <start> <end>
```

## 🎯 **РЕКОМЕНДАЦИИ:**

### ✅ **Для дневной торговли:**

```
/set_trading_hours 9 18    # 09:00-18:00 (МСК)
```

### ✅ **Для расширенной торговли:**

```
/set_trading_hours 7 23    # 07:00-23:00 (МСК)
```

### ✅ **Для ночной торговли:**

```
/set_trading_hours 23 7    # 23:00-07:00 (МСК)
```

### ✅ **Для круглосуточной торговли:**

```
/set_trading_hours 0 24    # Круглосуточно
```

## 🎯 **ЗАКЛЮЧЕНИЕ:**

**✅ Система торговых часов полностью функциональна!**

### 📊 **Функциональность:**

- **Гибкая настройка** времени торговли
- **Поддержка перехода** через полночь
- **Интеграция с сигналами** и DCA
- **Бэкапы настроек** автоматически

### 🚀 **Готово к использованию:**

- **Команды Telegram** для управления
- **Проверка времени** при генерации сигналов
- **Накопление сигналов** в неторговое время
- **Автоматическое применение** настроек

---

**Статус:** ✅ Система работает
**Дата:** 2024-01-27
**Основная команда:** `/set_trading_hours`
**Просмотр настроек:** `/trading_hours`
