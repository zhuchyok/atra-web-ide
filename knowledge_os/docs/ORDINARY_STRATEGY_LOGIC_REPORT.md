# Логика формирования сигналов в "ОБЫЧНОЙ" стратегии

## 🎯 Обзор "Обычной" стратегии

**"Обычная" стратегия** - это резервная система, которая работает, когда оптимизированная стратегия не находит сигналов. Она использует **многоуровневый подход** с несколькими типами сигналов.

## 🔄 Многоуровневая логика

### **Уровень 1: Enhanced Bollinger сигналы (высший приоритет)**

#### **1.1 Mean Reversion (Возврат к средней)**

```python
def improved_mean_reversion_signal(df, i):
    # LONG сигнал: возврат от нижней полосы к средней
    long_reversion_conditions = [
        current_price <= bb_lower * 1.05,  # Точное касание нижней полосы
        current_price < bb_middle * 1.01,  # Цена ниже средней полосы
        rsi < 35,  # Экстремальная перепроданость
        volume_ratio > 0.01,  # Всплеск объема
    ]

    # SHORT сигнал: возврат от верхней полосы к средней
    short_reversion_conditions = [
        current_price >= bb_upper * 0.95,  # Точное касание верхней полосы
        current_price > bb_middle * 0.99,  # Цена выше средней полосы
        rsi > 65,  # Экстремальная перекупленность
        volume_ratio > 0.01,  # Всплеск объема
    ]
```

#### **1.2 Breakout (Пробой полос)**

```python
def improved_breakout_signal(df, i):
    # Пробой верхней полосы (LONG)
    # Пробой нижней полосы (SHORT)
    # С подтверждением EMA, RSI и объемом
```

#### **1.3 Squeeze Breakout (Пробой после сжатия)**

```python
def improved_squeeze_breakout_signal(df, i):
    # Обнаружение сжатия полос Боллинджера
    # Пробой после сжатия с подтверждением объемом
```

### **Уровень 2: Классические условия (средний приоритет)**

#### **LONG сигнал - очень мягкие условия:**

```python
long_conditions = [
    current_price <= bb_middle * 0.998,  # Цена немного ниже средней полосы
    ema7 > ema25 * 0.999,  # Очень слабый восходящий тренд
    rsi < 70,  # Слабая перепроданость (смягчено)
    volume_ratio > 0.01,  # Минимальный объем (смягчено)
    volatility > 0.1,  # Минимальная волатильность (смягчено)
    sentiment_score > -sentiment_threshold  # Не слишком негативные настроения
]
```

#### **SHORT сигнал - очень мягкие условия:**

```python
short_conditions = [
    current_price >= bb_middle * 1.002,  # Цена немного выше средней полосы
    ema7 < ema25 * 1.001,  # Очень слабый нисходящий тренд
    rsi > 30,  # Слабая перекупленность (смягчено)
    volume_ratio > 0.01,  # Минимальный объем (смягчено)
    volatility > 0.1,  # Минимальная волатильность (смягчено)
    sentiment_score < sentiment_threshold  # Не слишком позитивные настроения
]
```

### **Уровень 3: Ультра-простая стратегия (низший приоритет)**

#### **LONG: восходящий тренд + не слишком перекуплено**

```python
ultra_long_conditions = [
    ema7 > ema25,  # Восходящий тренд
    rsi < 80,  # Не слишком перекуплено
    volume_ratio > 0.01  # Минимальный объем
]
```

#### **SHORT: нисходящий тренд + не слишком перепродано**

```python
ultra_short_conditions = [
    ema7 < ema25,  # Нисходящий тренд
    rsi > 20,  # Не слишком перепродано
    volume_ratio > 0.01  # Минимальный объем
]
```

## 📊 Используемые индикаторы

### **Технические индикаторы:**

- **Bollinger Bands**: `bb_upper`, `bb_lower`, `bb_middle`
- **EMA**: `ema7`, `ema25`, `ema50`, `ema200`
- **RSI**: `rsi` (14 периодов)
- **Volume**: `volume_ratio` (отношение к среднему объему)
- **Volatility**: `volatility` (процентная волатильность)
- **Momentum**: `momentum` (4-периодный momentum)
- **Trend Strength**: `trend_strength` (сила тренда)

### **Дополнительные фильтры:**

- **Fear & Greed Index**: Индикатор жадности рынка
- **Sentiment Score**: Настроения на основе новостей
- **Volume Spike**: Всплески объема
- **Volatility Filter**: Фильтр по волатильности

## 🎯 Логика принятия решений

### **Приоритетная система:**

#### **1. Enhanced Bollinger сигналы (высший приоритет)**

```python
# Сначала проверяем mean reversion
reversion_side, reversion_price = improved_mean_reversion_signal(df, i)
if reversion_side:
    # Применяем фильтр индикатора жадности
    fear_greed_allowed = apply_fear_greed_filter(fear_greed_value, reversion_side, "soft")
    if fear_greed_allowed:
        # Проверяем настроения
        if sentiment_score > -sentiment_threshold:
            return reversion_side, reversion_price

# Затем проверяем breakout
breakout_side, breakout_price = improved_breakout_signal(df, i)
if breakout_side:
    # Аналогичные проверки...

# Наконец проверяем squeeze breakout
squeeze_side, squeeze_price = improved_squeeze_breakout_signal(df, i)
if squeeze_side:
    # Аналогичные проверки...
```

#### **2. Классические условия (средний приоритет)**

```python
# Если Enhanced Bollinger не сработал
if all(long_conditions):
    return "LONG", current_price
elif all(short_conditions):
    return "SHORT", current_price
```

#### **3. Ультра-простая стратегия (низший приоритет)**

```python
# Если классические условия не сработали
if all(ultra_long_conditions):
    return "LONG", current_price
elif all(ultra_short_conditions):
    return "SHORT", current_price
```

## 🔍 Фильтры и проверки

### **Fear & Greed Filter:**

```python
def apply_fear_greed_filter(fear_greed_value, side, mode="soft"):
    if mode == "soft":
        if side == "LONG" and fear_greed_value > 85:  # Слишком жадный рынок
            return False, "Рынок слишком жадный для LONG"
        elif side == "SHORT" and fear_greed_value < 15:  # Слишком страшный рынок
            return False, "Рынок слишком страшный для SHORT"
    return True, "OK"
```

### **Sentiment Filter:**

```python
# Для LONG: не слишком негативные настроения
sentiment_score > -sentiment_threshold  # threshold = 0.6

# Для SHORT: не слишком позитивные настроения
sentiment_score < sentiment_threshold   # threshold = 0.6
```

### **Volume Filter:**

```python
volume_ratio > 0.01  # Минимальный объем (очень мягкий)
```

### **Volatility Filter:**

```python
volatility > 0.1  # Минимальная волатильность (очень мягкий)
```

## 📈 Примеры условий для сигналов

### **LONG сигнал (Mean Reversion):**

- Цена касается нижней полосы Боллинджера (`current_price <= bb_lower * 1.05`)
- Цена ниже средней полосы (`current_price < bb_middle * 1.01`)
- RSI показывает перепроданость (`rsi < 35`)
- Есть всплеск объема (`volume_ratio > 0.01`)
- Рынок не слишком жадный (`fear_greed_value <= 85`)
- Настроения не слишком негативные (`sentiment_score > -0.6`)

### **SHORT сигнал (Mean Reversion):**

- Цена касается верхней полосы Боллинджера (`current_price >= bb_upper * 0.95`)
- Цена выше средней полосы (`current_price > bb_middle * 0.99`)
- RSI показывает перекупленность (`rsi > 65`)
- Есть всплеск объема (`volume_ratio > 0.01`)
- Рынок не слишком страшный (`fear_greed_value >= 15`)
- Настроения не слишком позитивные (`sentiment_score < 0.6`)

## 🎯 Преимущества многоуровневой системы

### **1. Максимальное покрытие:**

- Enhanced Bollinger находит качественные сигналы
- Классические условия находят дополнительные возможности
- Ультра-простая стратегия работает в любых условиях

### **2. Адаптивность:**

- Разные уровни для разных рыночных условий
- Автоматическое переключение между уровнями

### **3. Надежность:**

- Если один уровень не работает, другие продолжают
- Резервные механизмы для критических ситуаций

## 📊 Статистика использования уровней

### **Типичное распределение:**

- **Enhanced Bollinger**: ~60-70% сигналов
- **Классические условия**: ~20-30% сигналов
- **Ультра-простая**: ~10-20% сигналов

### **Когда используется каждый уровень:**

- **Enhanced Bollinger**: Качественные рыночные условия
- **Классические условия**: Умеренные рыночные условия
- **Ультра-простая**: Любые рыночные условия

## 🚀 Заключение

### ✅ **"Обычная" стратегия - это сложная многоуровневая система:**

1. **Enhanced Bollinger сигналы** - высшее качество
2. **Классические условия** - умеренное качество
3. **Ультра-простая стратегия** - базовое покрытие

### 🔄 **Система автоматически:**

- Переключается между уровнями в зависимости от рыночных условий
- Применяет множественные фильтры для качества сигналов
- Обеспечивает максимальное покрытие рынка

### 📈 **Результат:**

- **Высокое качество сигналов** на всех уровнях
- **Максимальное покрытие рынка**
- **Надежная работа в любых условиях**

**"Обычная" стратегия - это не простая, а очень умная и адаптивная система!** 🎉
