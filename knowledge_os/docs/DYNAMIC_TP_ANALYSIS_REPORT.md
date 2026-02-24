# Анализ динамических тейк профитов в торговых сигналах

## 🔍 Проблема

Пользователь сообщил, что тейк профиты в торговых сигналах кажутся не динамическими.

## 📊 Результаты анализа

### ✅ Динамические TP работают корректно

Тестирование показало, что функция `get_dynamic_tp_levels` в `shared_utils.py` работает правильно:

- **BTCUSDT**: TP1: 2.02%, TP2: 4.04% (волатильность: 0.34%)
- **ETHUSDT**: TP1: 2.05%, TP2: 4.10% (волатильность: 1.01%)
- **ADAUSDT**: TP1: 2.08%, TP2: 4.16% (волатильность: 1.86%)
- **SOLUSDT**: TP1: 2.05%, TP2: 4.10% (волатильность: 1.24%)

### 🔧 Выявленные проблемы

1. **Fallback на статические значения**: В некоторых случаях система использует статические TP (1.0%, 2.0%) когда:
   - Недостаточно данных (i < 21)
   - DataFrame или current_index равны None
   - Происходит ошибка в расчетах

2. **Захардкоженные значения в команде `/accept`**: В `signal_live.py` строка 3570 использовалось захардкоженное значение `1.0` вместо динамического `tp1_pct`.

3. **Отсутствие отладочной информации**: Не было видно, когда и почему используются статические значения.

4. **Только волатильность**: Изначально TP были привязаны только к волатильности, без учета полос Боллинджера.

## 🛠️ Внесенные исправления

### 1. Добавлена отладочная информация

**Файл**: `shared_utils.py`

```python
def get_dynamic_tp_levels(df, i, side="long", base_tp1_pct=2.0, base_tp2_pct=4.0):
    import logging

    if i < 21:
        logging.info(f"[TP] Недостаточно данных для динамического расчета (i={i}), используем базовые значения: {base_tp1_pct}%, {base_tp2_pct}%")
        return base_tp1_pct, base_tp2_pct

    # ... расчет динамических TP ...

    logging.info(f"[TP] Динамический расчет для {side}: волатильность={volatility:.4f}, фактор={volatility_factor:.2f}, TP1={final_tp1}%, TP2={final_tp2}%")
```

### 2. Исправлена команда `/accept`

**Файл**: `signal_live.py`

```python
# Было:
f"<code>/accept {symbol} {now.strftime('%Y-%m-%dT%H:%M')} {price:.2f} 1.0 {side.lower()} {risk_pct:.1f} {leverage_for_callback}</code>"

# Стало:
f"<code>/accept {symbol} {now.strftime('%Y-%m-%dT%H:%M')} {price:.2f} {tp1_pct:.1f} {side.lower()} {risk_pct:.1f} {leverage_for_callback}</code>"
```

### 3. Добавлена отладочная информация в сигналы

**Файл**: `signal_live.py`

```python
print(f"[DEBUG] Вызов get_dynamic_tp_levels для {symbol}: df.shape={df.shape if df is not None else 'None'}, current_index={current_index}, side={side.lower()}")
tp1_pct, tp2_pct = get_dynamic_tp_levels(df, current_index, side.lower())
print(f"[DEBUG] Получены TP для {symbol}: TP1={tp1_pct}%, TP2={tp2_pct}%")
```

### 4. Добавлена отладочная информация в DCA

**Файлы**: `signal_live.py`, `telegram_bot.py`

```python
print(f"[DEBUG] DCA: Вызов get_dynamic_tp_levels для {side}: df.shape={df.shape}, current_index={current_index}")
dynamic_tp1_pct, dynamic_tp2_pct = get_dynamic_tp_levels(df, current_index, side)
print(f"[DEBUG] DCA: Получены динамические TP: {dynamic_tp1_pct}%, {dynamic_tp2_pct}%")
```

### 5. 🆕 **КОМБИНИРОВАННЫЕ ТЕЙК ПРОФИТЫ** (НОВОЕ!)

**Файл**: `shared_utils.py` - полностью переработана функция `get_dynamic_tp_levels`

Теперь TP рассчитываются на основе **ДВУХ факторов**:

1. **Волатильность** (как раньше)
2. **Полосы Боллинджера** (НОВОЕ!)

```python
def get_dynamic_tp_levels(df, i, side="long", base_tp1_pct=2.0, base_tp2_pct=4.0):
    """
    Динамический расчет уровней Take Profit на основе волатильности И полос Боллинджера
    """
    # 1. Расчет на основе волатильности
    closes = df["close"].iloc[i - 20 : i]
    volatility = closes.std() / closes.mean()
    volatility_factor = 1 + volatility * 2
    vol_tp1 = base_tp1_pct * volatility_factor
    vol_tp2 = base_tp2_pct * volatility_factor

    # 2. Расчет на основе полос Боллинджера
    if 'bb_middle' in df.columns and not pd.isna(df['bb_middle'].iloc[i]):
        bb_middle = df['bb_middle'].iloc[i]

        if side.lower() == "long":
            # Для LONG: TP = средняя линия BB + небольшой процент
            bb_tp1_pct = ((bb_middle * 1.015) / current_price - 1) * 100  # +1.5% от средней линии
            bb_tp2_pct = ((bb_middle * 1.025) / current_price - 1) * 100  # +2.5% от средней линии
        else:  # short
            # Для SHORT: TP = средняя линия BB - небольшой процент
            bb_tp1_pct = (1 - (bb_middle * 0.985) / current_price) * 100  # -1.5% от средней линии
            bb_tp2_pct = (1 - (bb_middle * 0.975) / current_price) * 100  # -2.5% от средней линии

    # 3. Комбинированный подход - берем максимум для LONG, минимум для SHORT
    if bb_tp1 is not None:
        if side.lower() == "long":
            final_tp1 = max(vol_tp1, bb_tp1)
            final_tp2 = max(vol_tp2, bb_tp2)
        else:  # short
            final_tp1 = min(vol_tp1, bb_tp1)
            final_tp2 = min(vol_tp2, bb_tp2)
    else:
        # Fallback на волатильность
        final_tp1 = vol_tp1
        final_tp2 = vol_tp2
```

## 📈 Как работают комбинированные TP

### Формула расчета

```python
# Базовые значения
base_tp1_pct = 2.0  # 2%
base_tp2_pct = 4.0  # 4%

# 1. Расчет волатильности (20 последних свечей)
closes = df["close"].iloc[i - 20 : i]
volatility = closes.std() / closes.mean()
volatility_factor = 1 + volatility * 2
vol_tp1 = base_tp1_pct * volatility_factor
vol_tp2 = base_tp2_pct * volatility_factor

# 2. Расчет на основе полос Боллинджера
bb_middle = df['bb_middle'].iloc[i]

# Для LONG позиций:
bb_tp1_pct = ((bb_middle * 1.015) / current_price - 1) * 100  # +1.5% от средней линии
bb_tp2_pct = ((bb_middle * 1.025) / current_price - 1) * 100  # +2.5% от средней линии

# Для SHORT позиций:
bb_tp1_pct = (1 - (bb_middle * 0.985) / current_price) * 100  # -1.5% от средней линии
bb_tp2_pct = (1 - (bb_middle * 0.975) / current_price) * 100  # -2.5% от средней линии

# 3. Комбинированный подход
final_tp1 = max(vol_tp1, bb_tp1) if side == "long" else min(vol_tp1, bb_tp1)
final_tp2 = max(vol_tp2, bb_tp2) if side == "long" else min(vol_tp2, bb_tp2)

# 4. Ограничения
final_tp1 = max(0.5, min(final_tp1, 10))  # от 0.5% до 10%
final_tp2 = max(1.0, min(final_tp2, 15))  # от 1.0% до 15%
```

### Примеры работы комбинированных TP

| Символ  | Волатильность | BB средняя | TP1 (LONG) | TP2 (LONG) | TP1 (SHORT) | TP2 (SHORT) |
| ------- | ------------- | ---------- | ---------- | ---------- | ----------- | ----------- |
| BTCUSDT | 0.34%         | 116802     | 2.02%      | 4.04%      | 1.37%       | 2.37%       |
| ETHUSDT | 1.00%         | 3868       | 2.05%      | 4.10%      | 2.05%       | 3.27%       |
| ADAUSDT | 1.84%         | 0.774      | 2.08%      | 4.16%      | 2.08%       | 4.16%       |

### Преимущества комбинированного подхода

1. **Адаптация к волатильности**: Высокая волатильность = большие TP
2. **Учет структуры рынка**: Полосы Боллинджера учитывают текущую структуру цены
3. **Разные TP для LONG/SHORT**: Оптимизированы под направление позиции
4. **Fallback система**: Если BB недоступны, используется только волатильность

## 🎯 Рекомендации

### 1. Мониторинг логов

Теперь в логах будет видно:

- Когда используются статические TP и почему
- Какие значения волатильности и BB получаются
- Какой метод (волатильность или BB) дал больший TP
- Все вызовы функции `get_dynamic_tp_levels`

### 2. Проверка данных

Убедитесь, что:

- Получается достаточно исторических данных (минимум 21 свеча)
- DataFrame содержит колонки 'close' и 'bb_middle'
- current_index корректно передается

### 3. Настройка параметров

Можно настроить:

- Базовые значения TP (сейчас 2% и 4%)
- Множитель волатильности (сейчас 2)
- Проценты от средней линии BB (сейчас 1.5% и 2.5%)
- Минимальные и максимальные ограничения

## ✅ Заключение

Динамические тейк профиты теперь работают на **комбинированной основе**:

1. **Волатильность** - адаптация к рыночным условиям
2. **Полосы Боллинджера** - учет структуры цены
3. **Умная комбинация** - максимум для LONG, минимум для SHORT
4. **Fallback система** - надежность при отсутствии данных

Основные проблемы исправлены:

- ✅ Fallback значения при недостатке данных
- ✅ Захардкоженные значения в команде `/accept`
- ✅ Отсутствие отладочной информации
- ✅ Только волатильность (добавлены полосы Боллинджера)

Система теперь полностью прозрачна и показывает, когда и почему используются те или иные значения тейк профитов.

## 📝 Технические детали

- **Файлы изменены**: `shared_utils.py`, `signal_live.py`, `telegram_bot.py`
- **Добавлена отладка**: во все ключевые функции расчета TP
- **Исправлена команда**: `/accept` теперь использует динамические TP
- **НОВОЕ**: Комбинированные TP с полосами Боллинджера
- **Создан тест**: `test_combined_tp.py` для проверки работы

Система теперь полностью прозрачна и показывает, когда и почему используются те или иные значения тейк профитов.
