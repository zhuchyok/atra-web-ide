# Отчет о динамическом расчете суммы входа

## Обзор системы

**Да, сумма входа у нас полностью динамическая!** Она рассчитывается с учетом всех факторов:

1. **Динамический риск** (1-5%)
2. **Динамический депозит** (с учетом прибыли/убытка)
3. **Открытые сделки** (учитываются в расчете свободных средств)
4. **Динамическое плечо** (для фьючерсов)

## Формула расчета суммы входа

```python
# Основная формула:
Сумма входа = free_deposit * risk_pct / 100 * leverage

# Где:
# - free_deposit = доступные средства (депозит - риски открытых позиций)
# - risk_pct = динамический процент риска (1-5%)
# - leverage = динамическое плечо (для фьючерсов)
```

## 1. 📊 Расчет free_deposit (свободных средств)

### Функция: `recalculate_balance_and_risks()`

```python
def recalculate_balance_and_risks(user_data, user_id=None, force_recalc=False):
    # 1. Получаем базовый депозит
    deposit = user_data.get("deposit", 0)

    # 2. Учитываем прибыль/убыток от закрытых сделок
    total_profit = sum(trade.get("profit", 0) for trade in trade_history)
    updated_deposit = deposit + total_profit

    # 3. Рассчитываем риски по открытым позициям
    total_risk_amount = 0
    for pos in open_positions:
        risk_amount = pos.get("risk_amount", 0)
        if risk_amount > 0:
            total_risk_amount += risk_amount
        else:
            risk_pct = pos.get("risk_pct", 5.0)
            risk_amount = updated_deposit * risk_pct / 100
            total_risk_amount += risk_amount

    # 4. Рассчитываем свободные средства
    free_deposit = max(updated_deposit - total_risk_amount, 0)

    return {
        "updated_deposit": updated_deposit,
        "total_risk_amount": total_risk_amount,
        "free_deposit": free_deposit,
        "total_profit": total_profit
    }
```

### Пример расчета:

- **Базовый депозит**: 1000 USDT
- **Прибыль от сделок**: +50 USDT
- **Обновленный депозит**: 1050 USDT
- **Риски открытых позиций**: 200 USDT
- **Свободные средства**: 850 USDT

## 2. 🎯 Динамический расчет риска

### Функция: `get_dynamic_risk_pct()`

```python
def get_dynamic_risk_pct(df, i):
    # Анализируем последние 20 свечей
    closes = df["close"].iloc[i - 20 : i]

    # Рассчитываем волатильность
    volatility = closes.std() / closes.mean()

    # Рассчитываем тренд
    sma20_now = closes.mean()
    sma20_prev = df["close"].iloc[i - 30 : i - 10].mean()
    trend = (sma20_now - sma20_prev) / sma20_prev

    # Динамический риск
    base_risk = 2.0
    dynamic_risk = base_risk * (1 + 2 * trend) / (1 + 5 * volatility)
    dynamic_risk = max(1.0, min(dynamic_risk, 5.0))  # от 1% до 5%

    return dynamic_risk
```

### Логика динамического риска:

- **Сильный тренд** → **Увеличиваем риск** (до 5%)
- **Высокая волатильность** → **Уменьшаем риск** (до 1%)
- **Слабый тренд** → **Средний риск** (2-3%)

## 3. ⚡ Динамическое плечо (для фьючерсов)

### Функция: `get_dynamic_leverage()`

```python
def get_dynamic_leverage(df, i, base_leverage=1):
    # Анализируем последние 20 свечей
    closes = df["close"].iloc[i - 20 : i]

    # Рассчитываем волатильность и тренд
    volatility = closes.std() / closes.mean()
    trend = (sma20_now - sma20_prev) / sma20_prev

    # Факторы плеча
    trend_factor = 1 + min(abs(trend) * 10, 1.0)  # максимум 2x
    volatility_factor = max(0.5, 1 / (1 + volatility * 2))  # минимум 0.5x
    base_factor = 1 + (base_leverage - 1) * 0.3

    # Итоговое плечо
    dynamic_leverage = base_leverage * trend_factor * volatility_factor * base_factor
    dynamic_leverage = max(0.5, min(dynamic_leverage, 20))  # от 0.5x до 20x

    return int(round(dynamic_leverage))
```

### Логика динамического плеча:

- **Сильный тренд** → **Увеличиваем плечо** (до 20x)
- **Высокая волатильность** → **Уменьшаем плечо** (до 0.5x)
- **Слабый тренд** → **Среднее плечо** (1-5x)

## 4. 💰 Итоговый расчет суммы входа

### В сигналах:

```python
# DCA сигналы
f"💵 Сумма входа: <code>{free_deposit * risk_pct / 100 * (leverage if trade_mode == 'futures' else 1):.2f} USDT</code>\n"

# Обычные сигналы
f"💵 Сумма входа: <code>{free_deposit * risk_pct / 100 * (dynamic_leverage if trade_mode == 'futures' else 1):.2f} USDT</code>\n"
```

### При принятии сигнала:

```python
# Фьючерсы
risk_amount = free_deposit * risk_pct / 100 * leverage

# Спот
risk_amount = free_deposit * risk_pct / 100
```

## 5. 📈 Примеры расчета

### Пример 1: Спот торговля

- **Депозит**: 1000 USDT
- **Открытые позиции**: 200 USDT риска
- **Свободные средства**: 800 USDT
- **Динамический риск**: 2.5%
- **Сумма входа**: 800 × 2.5% × 1 = **20 USDT**

### Пример 2: Фьючерсы

- **Депозит**: 1000 USDT
- **Открытые позиции**: 200 USDT риска
- **Свободные средства**: 800 USDT
- **Динамический риск**: 3.0%
- **Динамическое плечо**: 5x
- **Сумма входа**: 800 × 3% × 5 = **120 USDT**

### Пример 3: Высокая волатильность

- **Депозит**: 1000 USDT
- **Свободные средства**: 800 USDT
- **Динамический риск**: 1.2% (уменьшен из-за волатильности)
- **Динамическое плечо**: 2x (уменьшено из-за волатильности)
- **Сумма входа**: 800 × 1.2% × 2 = **19.2 USDT**

## 6. 🔄 Автоматическое обновление

### Кэширование:

- **Кэш пересчета**: 30 секунд
- **Принудительный пересчет**: при изменении позиций
- **Автоматический пересчет**: при каждом сигнале

### Триггеры пересчета:

1. **Закрытие позиции**
2. **Открытие новой позиции**
3. **Изменение депозита**
4. **Истечение кэша** (30 секунд)

## 7. 📊 Мониторинг и отладка

### Отладочные сообщения:

```python
print(f"[recalculate_balance_and_risks] Данные для {user_id}: deposit={deposit}, positions={len(open_positions)}")
print(f"[recalculate_balance_and_risks] Расчет: deposit={deposit}, profit={total_profit}, updated_deposit={updated_deposit}")
print(f"[DEBUG] Динамическое плечо для {symbol}: {dynamic_leverage} (базовое: {base_leverage})")
```

### Команды для проверки:

- `/balance` - показывает текущий баланс и риски
- `/positions` - показывает открытые позиции
- `/myreport` - полный отчет по позициям

## Результат

### ✅ Система полностью динамическая:

1. **Риск адаптируется** к волатильности и тренду (1-5%)
2. **Плечо адаптируется** к рыночным условиям (0.5-20x)
3. **Депозит учитывает** прибыль/убыток от сделок
4. **Свободные средства** рассчитываются с учетом открытых позиций
5. **Сумма входа** автоматически пересчитывается для каждого сигнала

**Система обеспечивает оптимальное управление капиталом в зависимости от рыночных условий!** 🎯
