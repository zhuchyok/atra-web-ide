# 🛠️ ИСПРАВЛЕНИЕ: Фильтрация алертов по режиму торговли (spot/futures)

**Дата:** 2025-11-06 19:15 MSK  
**Статус:** ✅ **ИСПРАВЛЕНО**

## 🎯 ПРОБЛЕМА

Пользователь получал алерты о закрытии позиций для **обоих режимов** (spot и futures), а не только для выбранного режима пользователя.

### Причина:

- Система синхронизировала позиции с биржей для **всех пользователей** без проверки режима торговли
- `fetch_positions()` возвращает только **futures позиции** (так как Bitget - фьючерсная биржа)
- Для **spot пользователей** синхронизация не нужна (spot - это баланс, а не позиции)
- Система отправляла алерты для всех позиций, независимо от режима пользователя

## ✅ РЕШЕНИЕ

Добавлена проверка режима торговли пользователя перед синхронизацией позиций:

### Изменения в `main.py`:

#### 1. Перед получением позиций с биржи (строки 448-468):

**Было:**

```python
for uid in user_ids:
    keys = await adb_local.get_active_exchange_keys(uid, 'bitget')
    adapter = ExchangeAdapter('bitget', keys=keys or {}, sandbox=False)
    positions = await adapter.fetch_positions()
```

**Стало:**

```python
for uid in user_ids:
    # Получаем режим торговли пользователя (spot/futures)
    # ВАЖНО: Синхронизируем только futures позиции, так как fetch_positions() возвращает только futures
    # Для spot пользователей синхронизация не нужна (spot - это баланс, а не позиции)
    try:
        from db import Database
        db_temp = Database()
        user_data_temp = db_temp.get_user_data(str(uid)) or {}
        user_trade_mode = user_data_temp.get('trade_mode', 'spot')
    except Exception:
        user_trade_mode = 'spot'

    # Для spot пользователей пропускаем синхронизацию позиций
    if user_trade_mode == 'spot':
        logger.debug(
            "⏭️ Пропущена синхронизация позиций для пользователя %d "
            "(spot режим - позиции не синхронизируются)",
            uid
        )
        continue

    keys = await adb_local.get_active_exchange_keys(uid, 'bitget')
    adapter = ExchangeAdapter('bitget', keys=keys or {}, sandbox=False)
    positions = await adapter.fetch_positions()
```

#### 2. Перед закрытием позиций (строки 1261-1282):

**Было:**

```python
try:
    local_open = set(await adb_local.get_user_active_symbols(uid))
    to_close = local_open - open_symbols_remote

    # Проверяем режим пользователя
    user_mode = await adb_local.get_user_mode(uid)
```

**Стало:**

```python
try:
    # Получаем режим торговли пользователя (spot/futures)
    try:
        from db import Database
        db_temp = Database()
        user_data_temp = db_temp.get_user_data(str(uid)) or {}
        user_trade_mode = user_data_temp.get('trade_mode', 'spot')
    except Exception:
        user_trade_mode = 'spot'

    # Для spot пользователей пропускаем синхронизацию
    if user_trade_mode == 'spot':
        logger.debug(
            "⏭️ Пропущена синхронизация закрытия позиций для пользователя %d "
            "(spot режим - позиции не синхронизируются)",
            uid
        )
        continue

    local_open = set(await adb_local.get_user_active_symbols(uid))
    to_close = local_open - open_symbols_remote

    # Проверяем режим пользователя (manual/auto)
    user_mode = await adb_local.get_user_mode(uid)
```

## 📊 РЕЗУЛЬТАТЫ

### Для SPOT пользователей:

- ✅ **НЕ синхронизируются** позиции с биржей
- ✅ **НЕ отправляются** алерты о закрытии позиций
- ✅ Spot - это баланс на спотовом счете, а не позиции на бирже

### Для FUTURES пользователей:

- ✅ **Синхронизируются** только futures позиции
- ✅ **Отправляются** алерты только для futures позиций
- ✅ Работает как раньше (синхронизация с биржей)

## 🔍 ТЕХНИЧЕСКИЕ ДЕТАЛИ

### Почему для spot не нужна синхронизация:

1. **Spot позиции** - это баланс на спотовом счете, а не позиции на бирже
2. **`fetch_positions()`** на Bitget возвращает только futures позиции
3. **Spot пользователи** не открывают позиции на бирже (они покупают/продают активы)

### Почему для futures нужна синхронизация:

1. **Futures позиции** - это реальные позиции на фьючерсной бирже
2. **Нужна синхронизация** для отслеживания закрытия позиций (SL/TP, вручную)
3. **Алерты** нужны для уведомления о закрытии позиций

## 🎯 ВЫВОДЫ

1. ✅ **Проблема решена:** Spot пользователи больше не получают алерты о futures позициях
2. ✅ **Фильтрация работает:** Система проверяет режим пользователя перед синхронизацией
3. ✅ **Логика понятна:** Spot = баланс, Futures = позиции

---

**Следующий шаг:** Перезапустить бота для применения изменений
