# Отчет об исправлении проблемы "сигнал принят открытых позиций 0 на 0.00"

## Проблема
При принятии сигнала отображалось некорректное количество открытых позиций и сумма риска:
```
✅ Сигнал принят!
Ваш текущий депозит: 1000.00 USDT.
Открытых позиций: 0 на 0.00 USDT.
```

## Причина проблемы
В коде на строках 883-884 файла `telegram_bot.py` использовался неправильный расчет суммы риска:

```python
used_amount = sum(pos.get("risk_amount", 0) for pos in open_positions)
```

Проблема заключалась в том, что:
1. `risk_amount` в позициях мог быть не установлен или равен 0
2. Не учитывался правильный расчет риска на основе процента от депозита
3. Не использовалась функция `recalculate_balance_and_risks` для корректного пересчета

## Внесенные изменения

### 1. Обновлен расчет баланса и рисков (строки 883-895)
**Было:**
```python
used_amount = sum(pos.get("risk_amount", 0) for pos in open_positions)
free_deposit = max(deposit - used_amount, 0)
```

**Стало:**
```python
# Используем правильный расчет баланса и рисков
balance_data = recalculate_balance_and_risks(user_data, user_id)
if balance_data:
    used_amount = balance_data["total_risk_amount"]
    free_deposit = balance_data["free_deposit"]
    updated_deposit = balance_data["updated_deposit"]
else:
    # Fallback если пересчет не удался
    used_amount = sum(pos.get("risk_amount", 0) for pos in open_positions)
    free_deposit = max(deposit - used_amount, 0)
    updated_deposit = deposit
```

### 2. Улучшена функция recalculate_balance_and_risks (строка 4611)
**Добавлен параметр user_id:**
```python
def recalculate_balance_and_risks(user_data, user_id=None):
```

**Исправлен расчет риска (строки 4635-4645):**
```python
# Проверяем, что updated_deposit не None и является числом
if updated_deposit is not None and isinstance(updated_deposit, (int, float)) and updated_deposit > 0:
    risk_amount = updated_deposit * risk_pct / 100
    total_risk_amount += risk_amount
```

### 3. Добавлено поле risk_pct при создании позиций (строка 925)
**Добавлено в структуру позиции:**
```python
"risk_pct": risk_pct,
```

### 4. Обновлено отображение депозита (строка 900)
**Было:**
```python
f"Ваш текущий депозит: {deposit:.2f} USDT.\n"
```

**Стало:**
```python
f"Ваш текущий депозит: {updated_deposit:.2f} USDT.\n"
```

## Результат
Теперь при принятии сигнала корректно отображается:
- Обновленный депозит с учетом прибыли/убытков
- Правильное количество открытых позиций
- Корректная сумма риска по всем позициям
- Точные свободные средства для новых сделок

## Тестирование
Создан и выполнен тест функции `recalculate_balance_and_risks`, который подтвердил корректность расчетов:
- ✅ Депозит рассчитан правильно
- ✅ Риск рассчитан правильно
- ✅ Свободные средства рассчитаны правильно

## Файлы изменены
- `telegram_bot.py` - основные исправления логики расчета баланса и рисков

## Статус
✅ **ИСПРАВЛЕНО** - Проблема с отображением открытых позиций в сигнале решена