# ✅ ПРОВЕРКА: Это точно алерт о закрытии, не об открытии

## 🔍 АНАЛИЗ КОДА

### 1. Функция алерта

**Файл:** `alert_notifications.py` (строки 55-58)

```python
async def alert_position_closed_by_exchange(self, user_id: int, symbol: str):
    """Алерт о закрытии позиции на бирже."""
    msg = f"✅ <b>Позиция закрыта</b>\n├ Символ: {symbol}\n└ Закрыта на бирже (автосинхронизация)"
    await self.send_alert(user_id, 'position_closed', msg)
```

**Вывод:** Функция называется `alert_position_closed_by_exchange` и отправляет сообщение "Позиция закрыта".

---

### 2. Где вызывается эта функция

**Файл:** `main.py` (строка 1275)

**Контекст:**

```python
# Строка 1240: Закрываем локально те символы, которые более не числятся открытыми на бирже
try:
    local_open = set(await adb_local.get_user_active_symbols(uid))
    to_close = local_open - open_symbols_remote  # Находим позиции, которых НЕТ на бирже

    for sym in to_close:
        # Для auto режима закрываем позиции, если они не найдены на бирже
        await adb_local.close_active_position_by_symbol(uid, sym)  # ← ЗАКРЫТИЕ
        # ...
        # Алерт о закрытии
        await alert_svc.alert_position_closed_by_exchange(uid, sym)  # ← АЛЕРТ
```

**Вывод:** Алерт вызывается **ПОСЛЕ** закрытия позиции (`close_active_position_by_symbol`).

---

### 3. Где открываются позиции

**Файл:** `main.py` (строки 470-490)

**Контекст:**

```python
# Строка 470: Собираем набор символов, которые биржа считает открытыми
open_symbols_remote = set()
for p in (positions or []):
    symbol = p.get('symbol')
    contracts = float(p.get('contracts') or 0)

    if contracts and abs(contracts) > 0:
        # ...
        await adb_local.upsert_active_position(  # ← ОТКРЫТИЕ/ОБНОВЛЕНИЕ
            uid, symbol, direction, entry_price, 'open'
        )
        open_symbols_remote.add(symbol)
        # НЕТ ВЫЗОВА АЛЕРТА!
```

**Вывод:** При открытии/обновлении позиции (`upsert_active_position`) **НЕТ** вызова алерта.

---

### 4. Проверка других мест

**Поиск по коду:**

- ❌ Нет функции `alert_position_opened_by_exchange`
- ❌ Нет функции `alert_position_created`
- ❌ Нет вызовов алерта при открытии позиций

**Вывод:** Алерт отправляется **ТОЛЬКО** при закрытии позиции.

---

## 📊 ЛОГИКА РАБОТЫ

### Сценарий 1: Позиция закрыта на бирже

1. **Локально:** `ETHFIUSDT` открыта
2. **На бирже:** Позиция закрыта (вручную, по SL/TP)
3. **Синхронизация:**
   - `local_open = {'ETHFIUSDT'}`
   - `open_symbols_remote = {}` (пусто, позиции нет на бирже)
   - `to_close = {'ETHFIUSDT'}`
4. **Действие:**
   - `close_active_position_by_symbol(uid, 'ETHFIUSDT')` ← ЗАКРЫТИЕ
   - `alert_position_closed_by_exchange(uid, 'ETHFIUSDT')` ← АЛЕРТ
5. **Результат:** ✅ Алерт "Позиция закрыта"

---

### Сценарий 2: Позиция открыта на бирже

1. **Локально:** Позиции нет
2. **На бирже:** `ETHFIUSDT` открыта
3. **Синхронизация:**
   - `local_open = {}` (пусто)
   - `open_symbols_remote = {'ETHFIUSDT'}`
   - `to_close = {}` (пусто, нет позиций для закрытия)
4. **Действие:**
   - `upsert_active_position(uid, 'ETHFIUSDT', ...)` ← ОТКРЫТИЕ
   - **НЕТ ВЫЗОВА АЛЕРТА**
5. **Результат:** ❌ Алерт НЕ отправляется

---

## ✅ ВЫВОД

**Это точно алерт о закрытии, не об открытии:**

1. ✅ Функция называется `alert_position_closed_by_exchange`
2. ✅ Вызывается **ПОСЛЕ** `close_active_position_by_symbol`
3. ✅ Вызывается **ТОЛЬКО** когда позиция не найдена на бирже (закрыта)
4. ✅ При открытии позиции (`upsert_active_position`) алерт **НЕ** вызывается
5. ✅ В коде нет других функций для алерта об открытии

---

## 🔍 ВОЗМОЖНАЯ ПРОБЛЕМА

**Пользователь видит два разных формата символа:**

- `ETHFIUSDT`
- `ETHFI/USDT:USDT`

Это может быть проблема с нормализацией символа, но **это все равно алерт о закрытии**, просто с разными форматами символа.

---

## 🎯 РЕКОМЕНДАЦИЯ

Если пользователь видит этот алерт сразу после открытия позиции, это может означать:

1. **Позиция была открыта, но быстро закрыта на бирже** (SL/TP сработал)
2. **Проблема с синхронизацией** (система не видит позицию на бирже сразу)
3. **Проблема с форматом символа** (разные форматы: `ETHFIUSDT` vs `ETHFI/USDT:USDT`)

**Но это точно алерт о закрытии, не об открытии!**
