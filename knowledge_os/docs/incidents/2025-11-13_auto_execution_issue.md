# Инцидент: Сигналы в Telegram, но позиции не открылись на бирже (13.11.2025)

## 📋 Описание проблемы

**Дата:** 13 ноября 2025 (ночь)  
**Симптомы:**

- Сигналы приходят в Telegram ✅
- Позиции НЕ открываются на бирже ❌

## 🔍 Диагностика

### ✅ Проверено:

1. **Режим пользователя:**

   ```sql
   SELECT user_id, trade_mode FROM user_settings WHERE user_id = 556251171;
   -- Результат: 556251171|auto ✅
   ```

2. **Ключи API:**

   ```sql
   SELECT user_id, exchange_name, COUNT(*) FROM user_exchange_keys
   WHERE user_id = 556251171 AND exchange_name = 'bitget';
   -- Результат: 556251171|bitget|1 ✅
   ```

3. **Код автоисполнения:**
   - Блок автоисполнения находится в `signal_live.py` (строки 3757-3833)
   - Вызывается ПОСЛЕ успешной отправки сигнала в Telegram
   - Проверяет режим пользователя (`mode == 'auto'`)
   - Проверяет наличие ключей API
   - Вызывает `auto_exec.execute_and_open()`

### ❓ Возможные причины:

1. **Ошибки в блоке автоисполнения:**
   - Исключения перехватываются try-except (строка 3826)
   - Ошибки логируются, но не прерывают выполнение
   - Нужно проверить логи на наличие `❌ [AUTO] Ошибка автоисполнения`

2. **Проверки в `auto_execution.py`:**
   - BTC alignment проверка (может блокировать)
   - Проверка существующих позиций (дубликаты)
   - Проверка размера позиции
   - Ошибки при создании ордеров

3. **Проблемы с переменными:**
   - `entry_amount_usdt` может быть не определена
   - `leverage` может быть не определена
   - `sl_price`, `tp1_price`, `tp2_price` могут быть None

4. **Проблемы с API биржи:**
   - Ошибки подключения к Bitget
   - Проблемы с ключами (неправильное шифрование/дешифрование)
   - Rate limiting

## 🔧 Решение

### 1. Улучшить логирование

Добавить более детальное логирование в блок автоисполнения:

```python
# В signal_live.py, строка 3757
logger.info("🔍 [AUTO CHECK] Начало проверки автоисполнения для %s", symbol)
logger.info("🔍 [AUTO CHECK] user_id=%s, entry_amount_usdt=%s, leverage=%s",
           user_id_local, entry_amount_usdt, leverage)
```

### 2. Проверить переменные перед вызовом

```python
# Проверка обязательных переменных
if entry_amount_usdt is None or entry_amount_usdt <= 0:
    logger.error("❌ [AUTO] %s: entry_amount_usdt не определена или <= 0", symbol)
    return

if leverage is None or leverage <= 0:
    logger.error("❌ [AUTO] %s: leverage не определена или <= 0", symbol)
    return
```

### 3. Добавить проверку результата

```python
if success:
    logger.info("✅ [AUTO] %s успешно открыт автоматически", symbol)
    # Проверяем, что позиция действительно открыта
    positions = await adb.get_active_positions_by_user(str(user_id_local))
    if any(p.get('symbol') == symbol for p in positions):
        logger.info("✅ [AUTO] %s: Позиция подтверждена в БД", symbol)
    else:
        logger.warning("⚠️ [AUTO] %s: Позиция не найдена в БД после открытия!", symbol)
else:
    logger.warning("❌ [AUTO] %s не удалось открыть автоматически", symbol)
    # Дополнительная диагностика
    logger.warning("❌ [AUTO] Проверьте логи auto_execution для деталей")
```

### 4. Проверить логи за ночь

```bash
# Проверить логи автоисполнения
grep -E "\[AUTO\]|execute_and_open" logs/system.log | tail -50

# Проверить ошибки
grep -E "❌.*AUTO|ERROR.*auto_execution" logs/system.log | tail -50
```

## 📊 Следующие шаги

1. ✅ Проверить логи за ночь 13.11.2025
2. ✅ Добавить детальное логирование
3. ✅ Проверить переменные перед вызовом auto_execution
4. ✅ Добавить проверку результата открытия позиции
5. ✅ Создать мониторинг успешности автоисполнения

## 🎯 Ожидаемый результат

После исправлений:

- Все сигналы в режиме `auto` должны автоматически открываться на бирже
- Детальные логи помогут быстро диагностировать проблемы
- Мониторинг покажет процент успешных автоисполнений
