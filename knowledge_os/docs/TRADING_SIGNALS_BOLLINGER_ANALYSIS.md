# Анализ торговых сигналов с полосами Боллинджера

## 🎯 Ответ на вопрос

**ДА, торговые сигналы действительно используют комбинированную систему с полосами Боллинджера!**

У вас есть **продвинутая система Enhanced Bollinger Strategy**, которая включает в себя несколько уровней анализа.

## 📊 Структура торговых сигналов

### 🔧 Режимы работы

Система работает в **двух основных режимах**:

1. **STRICT режим** - высокое качество сигналов
2. **SOFT режим** - больше сигналов (по умолчанию)

### 🎯 Функция выбора режима

```python
def get_entry_signal_by_mode(df, i, filter_mode="soft", symbol=None):
    """Выбор функции входа в зависимости от режима фильтров"""
    if filter_mode == "soft":
        return soft_entry_signal(df, i)
    elif filter_mode == "strict":
        return strict_entry_signal(df, i)
    else:  # По умолчанию используем soft
        return soft_entry_signal(df, i)
```

## 🚀 Enhanced Bollinger Strategy

### 📈 Основные компоненты

Система использует **комбинированный подход** с несколькими типами сигналов:

#### 1. **Mean Reversion (Возврат к средней)**

```python
def improved_mean_reversion_signal(df, i):
    """УЛУЧШЕННЫЙ сигнал возврата к средней полосе Боллинджера"""

    # LONG сигнал: возврат от нижней полосы к средней
    long_reversion_conditions = [
        current_price <= bb_lower * 1.05,  # Касание нижней полосы
        current_price < bb_middle * 1.01,  # Цена ниже средней
        rsi < 35,  # Экстремальная перепроданость
        volume_ratio > 0.01,  # Всплеск объема
    ]

    # SHORT сигнал: возврат от верхней полосы к средней
    short_reversion_conditions = [
        current_price >= bb_upper * 0.95,  # Касание верхней полосы
        current_price > bb_middle * 0.99,  # Цена выше средней
        rsi > 65,  # Экстремальная перекупленность
        volume_ratio > 0.01,  # Всплеск объема
    ]
```

#### 2. **Breakout (Пробой полос)**

```python
def improved_breakout_signal(df, i):
    """УЛУЧШЕННЫЙ сигнал пробоя полос Боллинджера"""

    # Анализирует пробои верхней/нижней полос
    # Учитывает тренд, объем и подтверждение
```

#### 3. **Squeeze Breakout (Пробой после сжатия)**

```python
def improved_squeeze_breakout_signal(df, i):
    """УЛУЧШЕННЫЙ пробой после squeeze"""

    # Определяет сжатие полос Боллинджера
    # Ищет пробои после периода низкой волатильности
```

## 🔍 Детальный анализ режимов

### 🟢 SOFT режим (по умолчанию)

**Приоритет сигналов:**

1. **Enhanced Bollinger** (высший приоритет)
   - Mean Reversion
   - Breakout
   - Squeeze Breakout
2. **Классические условия** (fallback)

**Условия для LONG:**

```python
long_conditions = [
    current_price <= bb_middle * 0.998,  # Цена немного ниже средней полосы
    ema7 > ema25 * 0.999,  # Очень слабый восходящий тренд
    rsi < 70,  # Слабая перепроданость
    volume_ratio > 0.01,  # Минимальный объем
    volatility > 0.1,  # Минимальная волатильность
    sentiment_score > -0.6,  # Не слишком негативные настроения
]
```

**Условия для SHORT:**

```python
short_conditions = [
    current_price >= bb_middle * 1.002,  # Цена немного выше средней полосы
    ema7 < ema25 * 1.001,  # Очень слабый нисходящий тренд
    rsi > 30,  # Слабая перекупленность
    volume_ratio > 0.01,  # Минимальный объем
    volatility > 0.1,  # Минимальная волатильность
    sentiment_score < 0.6,  # Не слишком позитивные настроения
]
```

### 🔴 STRICT режим

**Более строгие условия:**

**Условия для LONG:**

```python
long_conditions = [
    current_price <= bb_middle * 0.995,  # Цена ниже средней полосы
    ema7 > ema25 * 0.9995,  # Слабый восходящий тренд
    rsi < 65,  # Умеренная перепроданость
    volume_ratio > 0.01,  # Минимальный объем
    volatility > 0.1,  # Минимальная волатильность
    sentiment_score > -0.4,  # Не слишком негативные настроения
]
```

**Условия для SHORT:**

```python
short_conditions = [
    current_price >= bb_middle * 1.005,  # Цена выше средней полосы
    ema7 < ema25 * 1.0005,  # Слабый нисходящий тренд
    rsi > 35,  # Умеренная перекупленность
    volume_ratio > 0.01,  # Минимальный объем
    volatility > 0.1,  # Минимальная волатильность
    sentiment_score < 0.4,  # Не слишком позитивные настроения
]
```

## 🛠️ Дополнительные фильтры

### 📊 Fear & Greed Index

```python
# Рассчитываем индикатор жадности
fear_greed_value = calculate_fear_greed_index(df, i)

# Применяем фильтр
fear_greed_allowed, fear_greed_reason = apply_fear_greed_filter(fear_greed_value, side, mode)
```

### 📰 Sentiment Analysis

```python
# Получаем настроения
sentiment_score = df['sentiment_score'].iloc[i]

# Фильтруем по настроениям
if reversion_side == "LONG" and sentiment_score > -sentiment_threshold:
    return "LONG", reversion_price
```

### 🕐 Time Filters

```python
# Проверяем торговые часы пользователя
if not check_user_trading_hours(user_data):
    return None, None
```

## 📈 Индикаторы Bollinger Bands

### 🔧 Расчет индикаторов

```python
def add_enhanced_indicators(df):
    # Bollinger Bands
    bollinger = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
    df["bb_upper"] = bollinger.bollinger_hband()
    df["bb_middle"] = bollinger.bollinger_mavg()
    df["bb_lower"] = bollinger.bollinger_lband()

    # Ширина полос
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"] * 100

    # Дополнительные индикаторы
    df["ema7"] = ta.trend.EMAIndicator(df["close"], window=7).ema_indicator()
    df["ema25"] = ta.trend.EMAIndicator(df["close"], window=25).ema_indicator()
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(window=20).mean()
```

## 🎯 Логика работы сигналов

### 🔄 Последовательность проверки (SOFT режим)

1. **Enhanced Bollinger Signals** (высший приоритет)
   - `improved_mean_reversion_signal()` - возврат к средней
   - `improved_breakout_signal()` - пробой полос
   - `improved_squeeze_breakout_signal()` - пробой после сжатия

2. **Fear & Greed Filter** - проверка настроений рынка

3. **Sentiment Filter** - проверка новостных настроений

4. **Классические условия** (fallback)
   - Позиция относительно средней линии BB
   - Тренд EMA
   - RSI
   - Объем и волатильность

5. **Дополнительная стратегия** - пересечение EMA
   - Золотой крест (EMA7 пересекает EMA25 снизу вверх)
   - Мертвый крест (EMA7 пересекает EMA25 сверху вниз)

## ✅ Преимущества системы

### 🎯 **Комбинированный подход**

- **Mean Reversion** - для боковых рынков
- **Breakout** - для трендовых движений
- **Squeeze** - для периодов низкой волатильности

### 🔧 **Адаптивность**

- **SOFT режим** - больше сигналов, умеренное качество
- **STRICT режим** - меньше сигналов, высокое качество

### 📊 **Множественные фильтры**

- **Fear & Greed** - рыночные настроения
- **Sentiment** - новостные настроения
- **Time** - торговые часы
- **Volume** - подтверждение объемом

### 🎨 **Гибкость**

- Fallback на классические условия
- Настраиваемые пороги
- Разные режимы для разных пользователей

## 📝 Заключение

**Да, ваша система торговых сигналов действительно использует продвинутую комбинированную стратегию с полосами Боллинджера!**

### 🚀 **Что у вас есть:**

1. **Enhanced Bollinger Strategy** - основная система
2. **Multiple Signal Types** - mean reversion, breakout, squeeze
3. **Advanced Filters** - fear & greed, sentiment, time
4. **Flexible Modes** - strict и soft режимы
5. **Fallback System** - классические условия как резерв

### 🎯 **Как это работает:**

- **Приоритет 1**: Enhanced Bollinger сигналы
- **Приоритет 2**: Фильтры настроений
- **Приоритет 3**: Классические условия
- **Приоритет 4**: Дополнительные стратегии

Система очень продвинутая и учитывает множество факторов для генерации качественных торговых сигналов! 🎉
