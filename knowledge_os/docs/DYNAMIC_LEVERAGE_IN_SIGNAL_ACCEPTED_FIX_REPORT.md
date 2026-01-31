# Отчет об исправлении отображения динамического плеча в сигнале "принят"

## Проблема
В сигнале "принят" для фьючерсов отображалось статическое плечо (x1) вместо динамического плеча из торгового сигнала. Для спота плечо не должно отображаться вообще.

## Причина проблемы
1. В `signal_live.py` динамическое плечо рассчитывалось и отображалось в торговом сигнале, но не передавалось в `callback_data`
2. В `telegram_bot.py` использовалось статическое плечо из `user_data` вместо динамического из сигнала
3. Отсутствовала логика для скрытия плеча для спот режима

## Внесенные изменения

### 1. Обновлен callback_data в signal_live.py

**Добавлено динамическое плечо в callback_data для всех типов сигналов:**

**Новые торговые сигналы (строка 2978):**
```python
# Было:
callback_data=f'accept|{symbol}|{now.strftime("%Y-%m-%dT%H:%M")}|{price}|1.0|{side.lower()}|{risk_pct}'

# Стало:
callback_data=f'accept|{symbol}|{now.strftime("%Y-%m-%dT%H:%M")}|{price}|1.0|{side.lower()}|{risk_pct}|{dynamic_leverage or 1}'
```

**DCA LONG сигналы (строка 2512):**
```python
# Было:
callback_data=f'accept|{symbol}|{df.index[-1]}|{last["close"]}|{new_qty}|long|{risk_pct}'

# Стало:
callback_data=f'accept|{symbol}|{df.index[-1]}|{last["close"]}|{new_qty}|long|{risk_pct}|{leverage}'
```

**DCA SHORT сигналы (строка 2636):**
```python
# Было:
callback_data=f'accept|{symbol}|{df.index[-1]}|{last["close"]}|{new_qty}|short|{risk_pct}'

# Стало:
callback_data=f'accept|{symbol}|{df.index[-1]}|{last["close"]}|{new_qty}|short|{risk_pct}|{leverage}'
```

### 2. Обновлена обработка callback_data в telegram_bot.py

**Добавлена поддержка динамического плеча в функции button (строки 770-780):**
```python
# Если есть dynamic_leverage в data, используем его
if len(data) > 7:
    dynamic_leverage = float(data[7])
else:
    dynamic_leverage = None

leverage = dynamic_leverage if dynamic_leverage is not None else (user_data.get("leverage", 1) if trade_mode == "futures" else 1)
```

### 3. Обновлена команда /accept в telegram_bot.py

**Добавлена поддержка динамического плеча в accept_signal_cmd (строки 3980-3990):**
```python
# Добавлен параметр dynamic_leverage
dynamic_leverage = float(args[6]) if len(args) > 6 else None

# Используется динамическое плечо вместо статического
leverage = dynamic_leverage if dynamic_leverage is not None else (user_data.get("leverage", 1) if trade_mode == "futures" else 1)
```

## Результат

### Для SPOT режима:
- Плечо не отображается в сигнале "принят"
- Показывается только сумма входа в сделку

### Для FUTURES режима:
- Отображается динамическое плечо из торгового сигнала (например, x1.5, x2.0)
- Показывается сумма входа с учетом плеча
- Плечо рассчитывается автоматически на основе волатильности и тренда

### Пример отображения:

**SPOT режим:**
```
✅ Сигнал принят!
Ваш текущий депозит: 1000.00 USDT.
Открытых позиций: 0 на 0.00 USDT.
Свободно для новых сделок: 1000.00 USDT.
Риск на сделку: 2.00% (20.00 USDT).
Сумма входа в сделку: 20.00 USDT.
```

**FUTURES режим:**
```
✅ Сигнал принят!
Ваш текущий депозит: 1000.00 USDT.
Открытых позиций: 0 на 0.00 USDT.
Свободно для новых сделок: 1000.00 USDT.
Риск на сделку: 2.00% (20.00 USDT).
Используемое плечо: x1.5
Сумма входа с учётом плеча: 30.00 USDT.
```

## Совместимость

Все изменения обратно совместимы:
- Старые сигналы без динамического плеча будут работать с плечом x1
- Команда `/accept` поддерживает как старый, так и новый формат
- DCA сигналы используют существующее плечо из позиции

## Тестирование

Рекомендуется протестировать:
1. Принятие новых торговых сигналов для SPOT и FUTURES режимов
2. Принятие DCA сигналов
3. Использование команды `/accept` с новым параметром плеча
4. Проверка корректности отображения плеча в сообщении "сигнал принят"