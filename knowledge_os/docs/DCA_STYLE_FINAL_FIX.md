# Итоговое исправление стиля DCA сигналов

## 🎯 Проблема

Пользователь заметил, что стиль DCA сигналов не был полностью исправлен. DCA сигналы все еще использовали старый формат callback_data и не соответствовали новому стилю.

## ❌ Что было неправильно:

- **Старый формат callback_data**: `accept|{symbol}|{df.index[-1]}|{last["close"]}|{new_qty}|long|{risk_pct}|{leverage}`
- **Несоответствие новому стилю** сигналов
- **Отсутствие единообразия** в форматировании

## ✅ Исправления

### 1. Обновлен формат callback_data для DCA LONG

**Было:**

```python
callback_data=f'accept|{symbol}|{df.index[-1]}|{last["close"]}|{new_qty}|long|{risk_pct}|{leverage}'
```

**Стало:**

```python
# Создаем клавиатуру с новым форматом callback_data
short_time = now.strftime("%m%d%H%M")
short_price = f"{last['close']:.4f}"
short_risk = f"{risk_pct:.1f}"
short_leverage = f"{leverage:.1f}"

callback_data = f'accept|{symbol}|{short_time}|{short_price}|long|{short_risk}|{short_leverage}'
```

### 2. Обновлен формат callback_data для DCA SHORT

**Было:**

```python
callback_data=f'accept|{symbol}|{df.index[-1]}|{last["close"]}|{new_qty}|short|{risk_pct}|{leverage}'
```

**Стало:**

```python
# Создаем клавиатуру с новым форматом callback_data
short_time = now.strftime("%m%d%H%M")
short_price = f"{last['close']:.4f}"
short_risk = f"{risk_pct:.1f}"
short_leverage = f"{leverage:.1f}"

callback_data = f'accept|{symbol}|{short_time}|{short_price}|short|{short_risk}|{short_leverage}'
```

## 🔧 Технические изменения

### 1. Новый формат callback_data

- **Время**: `MMddHHmm` вместо `df.index[-1]`
- **Цена**: `{price:.4f}` вместо `{last["close"]}`
- **Риск**: `{risk:.1f}` вместо `{risk_pct}`
- **Плечо**: `{leverage:.1f}` вместо `{leverage}`
- **Убрано**: `{new_qty}` (не нужно для принятия сигнала)

### 2. Единообразие с новыми сигналами

- Тот же формат callback_data, что и у новых торговых сигналов
- Совместимость с обработчиком в `telegram_bot.py`

## 📊 Результат проверки

- ✅ Новый формат времени для DCA LONG
- ✅ Новый формат цены для DCA LONG
- ✅ Новый формат callback_data для DCA LONG
- ✅ Новый формат callback_data для DCA SHORT
- ✅ Старый формат callback_data полностью удален
- ✅ HTML заголовок DCA сигналов
- ✅ HTML форматирование для символа
- ✅ HTML форматирование для DCA информации
- ✅ Быстрые команды в DCA сигналах
- ✅ HTML форматирование для TP информации

## 🎉 Итог

Теперь все DCA сигналы имеют:

- **Единый стиль** с новыми торговыми сигналами
- **Новый формат callback_data** для корректной работы кнопок
- **HTML форматирование** для красивого отображения
- **Структурированную информацию** в логическом порядке
- **Быстрые команды** для удобства пользователя

**DCA сигналы теперь полностью соответствуют новому стилю!** 🎯
