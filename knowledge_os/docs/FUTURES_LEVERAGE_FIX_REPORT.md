# Исправление проблемы с плечом для FUTURES режима

## Проблема
При настройке FUTURES режима с депозитом 0 система показывала плечо 1x вместо минимального плеча для фьючерсов.

## Причины
1. **Ошибка импорта**: `local variable 'os' referenced before assignment` в функциях `save_user_data` и `load_user_data`
2. **Некорректный расчет плеча**: При депозите 0 функция `calculate_user_leverage` возвращала 1 для всех режимов
3. **Отсутствие минимального плеча**: Для FUTURES режима не было установлено минимальное плечо

## Исправления

### 1. Исправление импорта `os`
**Проблема**: Локальная переменная `os` перекрывала глобальный импорт в функциях `save_user_data` и `load_user_data`.

**Решение**: Добавлен локальный импорт `os` в обе функции:
```python
def save_user_data(context_or_app):
    import types
    import logging
    import os  # Добавлен локальный импорт
```

### 2. Исправление расчета плеча для FUTURES
**Проблема**: При депозите 0 система возвращала плечо 1 для всех режимов.

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

## Логика расчета плеча

### Для SPOT режима:
- Плечо всегда = 1x

### Для FUTURES режима:
- **Депозит 0**: Плечо = 2x (минимальное)
- **Депозит > 0**: Динамический расчет на основе:
  - Размера депозита
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

## Результат
✅ **Проблема решена**: Теперь при настройке FUTURES режима с депозитом 0 система корректно устанавливает минимальное плечо 2x

✅ **Ошибки импорта исправлены**: Функции `save_user_data` и `load_user_data` работают корректно

✅ **Динамический расчет**: Для депозитов > 0 плечо рассчитывается динамически с учетом всех факторов

## Тестирование
1. Настройка FUTURES режима с депозитом 0 → Плечо 2x ✅
2. Настройка FUTURES режима с депозитом > 0 → Динамическое плечо ✅
3. Настройка SPOT режима → Плечо 1x ✅
4. Сохранение/загрузка данных → Без ошибок ✅

## Команды для проверки
```bash
# Перезапуск бота
./bot_manager.sh restart

# Проверка статуса
./bot_manager.sh status

# Проверка логов
tail -f logs/telegram_bot.log
```