# 🔍 Диагностика проблемы автоисполнения

## Проблема

Сигналы приходят в Telegram, но позиции не открываются на бирже.

## Сигналы для проверки

- LINKUSDT SHORT 13.11.2025 05:15
- ETHUSDT SHORT 13.11.2025 05:28
- LINKUSDT SHORT 13.11.2025 05:46

## Проверка на сервере

### 1. Проверить логи автоисполнения

```bash
# На сервере
grep -i "AUTO CHECK\|AUTO\]\|execute_and_open" logs/system.log | tail -50
```

### 2. Проверить режим пользователя

```bash
sqlite3 trading.db "SELECT user_id, trade_mode FROM user_settings WHERE user_id = 556251171;"
```

### 3. Проверить наличие ключей API

```bash
sqlite3 trading.db "SELECT user_id, exchange_name FROM user_exchange_keys WHERE user_id = 556251171 AND exchange_name = 'bitget';"
```

### 4. Проверить сигналы в БД

```bash
sqlite3 trading.db "SELECT symbol, direction, entry_price, created_at FROM signals_log WHERE symbol IN ('LINKUSDT', 'ETHUSDT') AND date(created_at) = date('now') ORDER BY created_at DESC;"
```

### 5. Проверить активные позиции

```bash
sqlite3 trading.db "SELECT symbol, direction, entry_price, status FROM active_positions WHERE symbol IN ('LINKUSDT', 'ETHUSDT') AND status = 'open';"
```

## Возможные причины

1. **Переменные не в области видимости** - исправлено в последнем коммите
2. **Режим пользователя не 'auto'** - проверить в БД
3. **Нет ключей API** - проверить в БД
4. **Ошибка в auto_execution** - проверить логи
5. **Блокировка BTC трендом** - проверить логи
6. **Проблема с расчетом переменных** - проверить логи

## Исправления

✅ Исправлен доступ к переменным через `locals()` и fallback на `user_data`
✅ Добавлено детальное логирование для диагностики
✅ Добавлена обработка ошибок при получении переменных

## Следующие шаги

1. Проверить логи на сервере
2. Убедиться, что режим пользователя = 'auto'
3. Убедиться, что ключи API есть
4. Проверить, что переменные правильно получаются
