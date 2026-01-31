# Интеграция плеча с балансом из /myreport

## Проблема
Пользователь сообщил, что при настройке FUTURES режима система показывает плечо 1x вместо минимального плеча для фьючерсов, и нужно привязать плечо к балансу из команды `/myreport`.

## Исправления

### 1. Исправление ошибок импорта `os`
**Проблема**: `local variable 'os' referenced before assignment` в различных функциях.

**Решение**: Добавлены локальные импорты `os` в функции:
- `save_user_data()` - добавлен `import os`
- `load_user_data()` - добавлен `import os`
- `start()` - добавлен `import os`
- `button()` - добавлен `import os`

### 2. Исправление расчета плеча для FUTURES
**Проблема**: При депозите 0 система возвращала плечо 1x для всех режимов.

**Решение**: Добавлена проверка для FUTURES режима с минимальным плечом 2x:

#### В функции `setup_trade_mode_futures`:
```python
# Если депозит равен 0, используем минимальное плечо для FUTURES
if deposit <= 0:
    user_data["leverage"] = 2  # Минимальное плечо для FUTURES
else:
    user_data["leverage"] = calculate_user_leverage(deposit, "futures", filter_mode)
```

#### В функции `setup_filter_mode_balanced`:
```python
# Если депозит равен 0 и режим FUTURES, используем минимальное плечо
if deposit <= 0 and trade_mode == "futures":
    user_data["leverage"] = 2  # Минимальное плечо для FUTURES
else:
    user_data["leverage"] = calculate_user_leverage(deposit, trade_mode, "balanced")
```

#### В функции `setup_filter_mode_soft`:
```python
# Если депозит равен 0 и режим FUTURES, используем минимальное плечо
if deposit <= 0 and trade_mode == "futures":
    user_data["leverage"] = 2  # Минимальное плечо для FUTURES
else:
    user_data["leverage"] = calculate_user_leverage(deposit, trade_mode, "soft")
```

### 3. Интеграция с балансом из /myreport
**Проблема**: Плечо не учитывало актуальный баланс из команды `/myreport`.

**Решение**: Система теперь использует функцию `recalculate_balance_and_risks()` для получения актуального баланса:

```python
# Пересчитываем баланс и риски для актуальной информации
balance_update = recalculate_balance_and_risks(user_data, user_id)

if balance_update:
    deposit = balance_update["updated_deposit"]
    total_profit = balance_update["total_profit"]
    total_risk_amount = balance_update["total_risk_amount"]
    free_deposit = balance_update["free_deposit"]
else:
    deposit = user_data.get("deposit", 0)
```

## Логика расчета плеча

### Для SPOT режима:
- Плечо всегда = 1x

### Для FUTURES режима:
- **Депозит 0**: Плечо = 2x (минимальное)
- **Депозит > 0**: Динамический расчет на основе:
  - Размера депозита (включая прибыль/убытки)
  - Режима фильтров (soft/balanced)
  - Риск-толерантности

### Динамический расчет плеча:
```python
def calculate_base_leverage(deposit):
    if deposit < 100: return 1
    elif deposit < 500: return 2
    elif deposit < 1000: return 3
    elif deposit < 5000: return 5
    elif deposit < 10000: return 8
    else: return 10

def calculate_risk_based_leverage(deposit, risk_tolerance):
    base_leverage = calculate_base_leverage(deposit)
    multipliers = {
        "conservative": 0.5,  # Уменьшаем плечо
        "moderate": 1.0,      # Оставляем как есть
        "aggressive": 1.5     # Увеличиваем плечо
    }
    return int(max(1, min(base_leverage * multipliers[risk_tolerance], 20)))
```

## Интеграция с /myreport

### Команда `/myreport`:
- Использует `recalculate_balance_and_risks()` для получения актуального баланса
- Показывает обновленный депозит с учетом прибыли/убытков
- Отображает динамическое плечо для FUTURES режима

### Команда `/balance`:
- Также использует `recalculate_balance_and_risks()` для актуальных данных
- Показывает свободные средства для новых сделок
- Учитывает риски по открытым позициям

## Результат

✅ **Проблема решена**: Теперь при настройке FUTURES режима система корректно устанавливает минимальное плечо 2x

✅ **Ошибки импорта исправлены**: Все функции работают корректно

✅ **Интеграция с балансом**: Плечо рассчитывается на основе актуального баланса из `/myreport`

✅ **Динамический расчет**: Для депозитов > 0 плечо рассчитывается с учетом всех факторов

## Тестирование

1. **Настройка FUTURES режима с депозитом 0** → Плечо 2x ✅
2. **Настройка FUTURES режима с депозитом > 0** → Динамическое плечо ✅
3. **Настройка SPOT режима** → Плечо 1x ✅
4. **Команда /myreport** → Актуальный баланс и плечо ✅
5. **Команда /balance** → Свободные средства и риски ✅

## Команды для проверки

```bash
# Перезапуск бота
./bot_manager.sh restart

# Проверка статуса
./bot_manager.sh status

# Проверка логов
tail -f logs/telegram_bot.log
```

## Использование

1. **Настройка режима**: Выберите FUTURES режим в настройках
2. **Проверка баланса**: Используйте `/myreport` для просмотра актуального баланса
3. **Проверка плеча**: Система автоматически рассчитает оптимальное плечо
4. **Торговля**: Плечо будет применяться автоматически к новым сигналам