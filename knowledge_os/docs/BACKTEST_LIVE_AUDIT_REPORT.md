# АУДИТ СОГЛАСОВАННОСТИ BACKTEST И LIVE ЛОГИКИ

## 📊 Анализ согласованности систем

### Основные компоненты:

#### 1. **Оригинальный бэктестер (`backtest.py`):**

- **`backtest()`** - Основная функция бэктестирования
- Простая логика: TP = entry + ATR _ TP_MULT, SL = entry - ATR _ SL_MULT
- Фиксированные параметры: TP_MULT = 2.5, SL_MULT = 1.2
- Ограничение на 20 свечей для выхода

#### 2. **Синхронизированный бэктестер (`backtester_sync.py`):**

- **`backtest_synchronized()`** - Синхронизированная с live логикой
- Использует те же функции: `get_dynamic_tp_levels`, `get_dynamic_risk_pct`
- Полная поддержка DCA логики
- Динамические TP/SL уровни

#### 3. **Live система (`signal_live.py`):**

- **`check_and_send_signals()`** - Генерация сигналов в реальном времени
- Динамические параметры для каждого пользователя
- Поддержка DCA с накоплением позиций
- Интеграция с фильтрами (BTC-тренд, новости, аномалии, киты)

### 🔧 Сравнительный анализ:

#### **Параметры и константы:**

| Параметр          | backtest.py    | backtester_sync.py | signal_live.py | Согласованность      |
| ----------------- | -------------- | ------------------ | -------------- | -------------------- |
| **FEE**           | 0.001 (0.1%)   | 0.001 (0.1%)       | 0.001 (0.1%)   | ✅                   |
| **SLIPPAGE**      | 0.0005 (0.05%) | 0.0005 (0.05%)     | 0.0005 (0.05%) | ✅                   |
| **START_BALANCE** | 10000          | 10000              | START_BALANCE  | ✅                   |
| **TF**            | "30m"          | "1h"               | "1h"           | ❌ Разные таймфреймы |

#### **Логика расчета TP/SL:**

**backtest.py (простая логика):**

```python
entry = row["close"] * (1 + slippage)
atr = row["atr"]
tp = entry + atr * tp_mult        # TP_MULT = 2.5
sl = entry - atr * sl_mult        # SL_MULT = 1.2
```

**backtester_sync.py (динамическая логика):**

```python
# Использует те же функции что и live система
tp1_pct, tp2_pct = get_dynamic_tp_levels(df, i, signal_side)
risk_pct = get_dynamic_risk_pct(df, i)

if signal_side == "long":
    tp1 = signal_price * (1 + tp1_pct / 100)
    sl = signal_price * (1 - risk_pct)  # risk_pct здесь выступает как расстояние до SL
else:
    tp1 = signal_price * (1 - tp1_pct / 100)
    sl = signal_price * (1 + risk_pct)
```

**signal_live.py (live логика):**

```python
# Для новых сигналов
tp1_pct, tp2_pct = get_dynamic_tp_levels(df, current_index, side)
risk_pct = get_dynamic_risk_pct(df, current_index)

if side == "long":
    tp1 = signal_price * (1 + tp1_pct / 100)
    tp2 = signal_price * (1 + tp2_pct / 100)
    sl = signal_price * (1 - risk_pct)  # Здесь risk_pct - это процент риска от entry
```

### 🚨 Выявленные проблемы:

#### **Проблема 1: Разные таймфреймы**

- **backtest.py**: использует "30m"
- **backtester_sync.py** и **signal_live.py**: используют "1h"
- **Последствия**: несопоставимые результаты бэктестирования

#### **Проблема 2: Разная логика TP/SL**

- **backtest.py**: TP/SL рассчитываются на основе ATR с фиксированными множителями
- **backtester_sync.py/signal_live.py**: TP/SL рассчитываются динамически на основе волатильности и Bollinger Bands
- **Последствия**: разные уровни входа/выхода, несопоставимые результаты

#### **Проблема 3: Отсутствие синхронизации DCA**

- **backtest.py**: нет DCA логики вообще
- **backtester_sync.py**: имеет базовую DCA логику
- **signal_live.py**: имеет продвинутую DCA логику с динамическими параметрами
- **Последствия**: live система поддерживает усреднение, а бэктест - нет

#### **Проблема 4: Разные параметры фильтрации**

- **backtest.py**: простая фильтрация по техническим индикаторам
- **signal_live.py**: сложная многоуровневая фильтрация (BTC-тренд, новости, аномалии, киты)
- **backtester_sync.py**: использует только техническую фильтрацию
- **Последствия**: бэктест дает более оптимистичные результаты

#### **Проблема 5: Разные модели позиционирования**

- **backtest.py**: простая модель - одна позиция на сигнал
- **signal_live.py**: сложная модель с поддержкой DCA и частичных закрытий
- **Последствия**: несопоставимые торговые сценарии

### 🔧 Рекомендации по улучшению:

#### **1. Стандартизация параметров:**

```python
# Создать общий конфигурационный файл для всех бэктестеров
BACKTEST_CONFIG = {
    'timeframe': '1h',
    'fee': 0.001,
    'slippage': 0.0005,
    'start_balance': 10000,
    'max_candles_for_exit': 20,
    'enable_dca': True,
    'enable_filters': True,
    'use_dynamic_tp_sl': True
}
```

#### **2. Унификация логики TP/SL:**

```python
def calculate_tp_sl_levels(entry_price, side, df, current_index, use_dynamic=True):
    """
    Единая функция расчета TP/SL уровней для всех систем
    """
    if use_dynamic:
        # Динамический расчет для синхронизированного бэктестера и live
        tp1_pct, tp2_pct = get_dynamic_tp_levels(df, current_index, side)
        risk_pct = get_dynamic_risk_pct(df, current_index)
    else:
        # Статический расчет для простого бэктестера
        atr = df['atr'].iloc[current_index] if 'atr' in df.columns else 0.02
        tp1_pct = 2.5 * (atr / entry_price) * 100  # TP_MULT = 2.5
        tp2_pct = 4.0 * (atr / entry_price) * 100  # TP_MULT * 1.6
        risk_pct = 1.2 * (atr / entry_price) * 100  # SL_MULT = 1.2

    # Расчет абсолютных уровней
    if side == "long":
        tp1 = entry_price * (1 + tp1_pct / 100)
        tp2 = entry_price * (1 + tp2_pct / 100)
        sl = entry_price * (1 - risk_pct / 100)
    else:
        tp1 = entry_price * (1 - tp1_pct / 100)
        tp2 = entry_price * (1 - tp2_pct / 100)
        sl = entry_price * (1 + risk_pct / 100)

    return {
        'tp1': tp1,
        'tp2': tp2,
        'sl': sl,
        'tp1_pct': tp1_pct,
        'tp2_pct': tp2_pct,
        'risk_pct': risk_pct
    }
```

#### **3. Синхронизация фильтров:**

```python
def apply_filters(df, current_index, filter_mode="balanced", use_news_filters=True, use_anomaly_filters=True, use_whale_filters=True):
    """
    Единая система фильтрации для всех бэктестеров
    """
    filters_passed = True
    reasons = []

    # 1. Техническая фильтрация (всегда активна)
    if not check_technical_filters(df, current_index, filter_mode):
        filters_passed = False
        reasons.append("technical_filters")

    # 2. BTC тренд фильтр
    if USE_BTC_TREND_FILTER:
        btc_df = get_btc_data()
        if not check_btc_trend_filter(btc_df):
            filters_passed = False
            reasons.append("btc_trend")

    # 3. Новостные фильтры (опционально)
    if use_news_filters:
        if check_negative_news():
            filters_passed = False
            reasons.append("negative_news")

    # 4. Фильтры аномалий (опционально)
    if use_anomaly_filters:
        if check_high_anomaly():
            # Модифицируем параметры вместо блокировки
            pass

    # 5. Китовые фильтры (опционально)
    if use_whale_filters:
        whale_signal = get_whale_signal()
        if whale_signal == "contradictory":
            filters_passed = False
            reasons.append("whale_signal")

    return filters_passed, reasons
```

#### **4. Унификация DCA логики:**

```python
class DCAManager:
    def __init__(self, max_dca_count=3, alpha=2.0, max_risk_pct=5.0):
        self.max_dca_count = max_dca_count
        self.alpha = alpha
        self.max_risk_pct = max_risk_pct

    def calculate_dca_position(self, entry_prices, qtys, current_price, dca_count, deposit, risk_pct, leverage, side, df, current_index):
        """
        Единая логика DCA для всех систем
        """
        # 1. Проверка лимитов
        if dca_count >= self.max_dca_count:
            return 0, 0, None, None, True

        # 2. Расчет средней цены
        avg_price = sum(p * q for p, q in zip(entry_prices, qtys)) / sum(qtys)

        # 3. Расчет просадки
        drawdown = abs((avg_price - current_price) / avg_price)

        # 4. Минимальная просадка для DCA
        min_drawdown_for_dca = 0.05
        if drawdown < min_drawdown_for_dca:
            return 0, avg_price, None, None, False

        # 5. Расчет размера DCA позиции
        base_qty = deposit * risk_pct / 100 * leverage / current_price
        new_qty = base_qty * (1 + self.alpha * drawdown) / (1 + dca_count)

        # 6. Проверка рисковых ограничений
        used_risk = sum(q * p for q, p in zip(qtys, entry_prices)) + new_qty * current_price
        max_risk = deposit * self.max_risk_pct / 100 * leverage
        if used_risk > max_risk:
            return 0, avg_price, None, None, True

        # 7. Расчет новых TP/SL
        new_avg_price = (sum(q * p for q, p in zip(entry_prices, qtys)) + new_qty * current_price) / (sum(qtys) + new_qty)

        tp1, tp2 = self.calculate_dca_tp_levels(new_avg_price, side, df, current_index)

        return new_qty, new_avg_price, tp1, tp2, False

    def calculate_dca_tp_levels(self, avg_price, side, df, current_index):
        """
        Расчет TP уровней для DCA позиции
        """
        if df is not None and current_index is not None:
            tp1_pct, tp2_pct = get_dynamic_tp_levels(df, current_index, side)
            # Снижаем TP для поздних DCA
            dca_penalty = 0.3  # 30% снижение
            tp1_pct *= (1 - dca_penalty)
            tp2_pct *= (1 - dca_penalty)
        else:
            tp1_pct, tp2_pct = 1.0, 2.0

        if side == "long":
            tp1 = avg_price * (1 + tp1_pct / 100)
            tp2 = avg_price * (1 + tp2_pct / 100)
        else:
            tp1 = avg_price * (1 - tp1_pct / 100)
            tp2 = avg_price * (1 - tp2_pct / 100)

        return tp1, tp2
```

### 📋 План синхронизации:

#### **Фаза 1: Стандартизация параметров**

1. Объединить все бэктестеры в один файл с разными режимами
2. Стандартизировать таймфрейм (использовать 1h для всех)
3. Унифицировать комиссии и проскальзывание

#### **Фаза 2: Синхронизация логики**

1. Использовать единую систему расчета TP/SL
2. Добавить DCA поддержку во все бэктестеры
3. Синхронизировать фильтры

#### **Фаза 3: Валидация**

1. Сравнить результаты разных бэктестеров
2. Провести кросс-валидацию на одних данных
3. Документировать различия и их причины

#### **Фаза 4: Оптимизация**

1. Добавить возможность переключения режимов
2. Оптимизировать производительность
3. Добавить подробную отчетность

### 🎯 Приоритеты:

#### **Высокий приоритет:**

1. Стандартизировать таймфреймы и параметры
2. Синхронизировать логику TP/SL
3. Добавить DCA поддержку в оригинальный бэктестер

#### **Средний приоритет:**

1. Унифицировать систему фильтрации
2. Добавить возможность переключения режимов
3. Создать сравнительные отчеты

#### **Низкий приоритет:**

1. Оптимизировать производительность
2. Добавить расширенную аналитику
3. Создать документацию по различиям

---

_Аудит согласованности backtest и live логики завершен. Системы имеют значительные различия, требующие синхронизации для получения сопоставимых результатов._
