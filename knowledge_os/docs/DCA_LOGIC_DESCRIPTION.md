# Логика DCA (Dollar-Cost Averaging) - Подробное описание

## 📋 Обзор DCA системы

**DCA (Dollar-Cost Averaging)** - это стратегия усреднения позиций при просадке для снижения средней цены входа и увеличения потенциальной прибыли.

## 🎯 Основные принципы DCA

### 1. **Адаптивная просадка**

- Просадка рассчитывается динамически на основе волатильности актива
- Учитывается ATR, объем торгов, рыночные условия
- Разные просадки для разных типов активов

### 2. **Умное усреднение**

- Размер DCA позиции зависит от глубины просадки
- Учитывается количество предыдущих DCA
- Защита от превышения лимитов риска

### 3. **Динамические тейк-профиты**

- TP пересчитываются после каждого DCA
- Учитывается новая средняя цена
- Адаптируются под волатильность рынка

## 🔧 Ключевые функции DCA

### 1. `should_dca()` - Проверка условий DCA

```python
def should_dca(side, last_close, stop_loss, dca_pct, df=None, current_index=None, user_id=None, symbol=None):
    """
    УПРОЩЕННАЯ функция проверки условий DCA - только проверка просадки
    Технические условия (90%) проверяются в основной логике
    """
    # Базовая проверка просадки
    if side == "long":
        basic_condition = last_close <= stop_loss * (1 - dca_pct / 100)
    else:
        basic_condition = last_close >= stop_loss * (1 + dca_pct / 100)

    return basic_condition
```

**Логика:**

- **LONG**: цена должна упасть ниже стоп-лосса на `dca_pct`%
- **SHORT**: цена должна подняться выше стоп-лосса на `dca_pct`%
- Технические условия (90%) проверяются в основной логике сигналов

### 2. `calculate_adaptive_dca_drawdown()` - Адаптивная просадка

```python
def calculate_adaptive_dca_drawdown(df, current_index, symbol=None):
    """
    АДАПТИВНАЯ ПРОСАДКА ДЛЯ DCA НА ОСНОВЕ ВОЛАТИЛЬНОСТИ
    """
    # Получаем ATR как процент от цены
    atr_pct = atr / current_price

    # Определяем тип волатильности
    if atr_pct < 0.02:  # < 2%
        volatility_type = "low_volatility"
        base_drawdown = 0.8  # 0.8%
    elif atr_pct < 0.04:  # 2-4%
        volatility_type = "medium_volatility"
        base_drawdown = 1.2  # 1.2%
    else:  # > 4%
        volatility_type = "high_volatility"
        base_drawdown = 2.0  # 2.0%

    # Применяем множители
    multiplier = 1.0

    # По объему
    if volume_ratio > 1.5:
        multiplier *= 1.05  # +5%
    elif volume_ratio < 0.7:
        multiplier *= 0.95  # -5%

    # По тренду
    if ema_diff > 0.02:  # Сильный тренд
        multiplier *= 1.1   # +10%
    elif ema_diff < 0.005:  # Боковик
        multiplier *= 0.9   # -10%

    # Финальная просадка
    adaptive_drawdown = base_drawdown * multiplier
    return max(0.5, min(3.0, adaptive_drawdown))  # Ограничение 0.5-3.0%
```

**Логика:**

- **Низкая волатильность** (BTC, ETH): 0.8% просадка
- **Средняя волатильность** (XRP, ADA): 1.2% просадка
- **Высокая волатильность** (DOGE, SHIB): 2.0% просадка
- **Множители**: объем (+5%/-5%), тренд (+10%/-10%)
- **Ограничения**: 0.5-3.0% для интрадей торговли

### 3. `dca_calculate_next_qty_and_tp()` - Расчет количества и TP

```python
def dca_calculate_next_qty_and_tp(entry_prices, qtys, price, dca_count, deposit, risk_pct, leverage=1, side="long", df=None, current_index=None):
    # Базовое количество
    base_qty = deposit * risk_pct / 100 * leverage / price

    # Средняя цена
    avg_price = sum(p * q for p, q in zip(entry_prices, qtys)) / sum(qtys)

    # Просадка
    drawdown = abs((avg_price - price) / avg_price)

    # Новое количество (увеличивается с просадкой, уменьшается с количеством DCA)
    new_qty = base_qty * (1 + ALPHA * drawdown) / (1 + dca_count)

    # Проверка лимитов риска
    used_risk = sum(q * p for q, p in zip(qtys, entry_prices)) + new_qty * price
    max_risk = deposit * MAX_RISK_PCT / 100 * leverage

    if used_risk > max_risk or dca_count >= MAX_DCA:
        return 0, avg_price, None, None, True  # Лимит достигнут

    # Новая средняя цена
    total_qty = sum(qtys) + new_qty
    total_cost = sum(q * p for q, p in zip(qtys, entry_prices)) + new_qty * price
    avg_price_new = total_cost / total_qty

    # Динамические TP
    dynamic_tp1_pct, dynamic_tp2_pct = get_dynamic_tp_levels(df, current_index, side)

    # Расчет TP с учетом количества DCA
    if dca_count + 1 >= 3:
        # Для поздних DCA - более консервативные TP (70% от обычных)
        tp1 = avg_price_new * (1 + dynamic_tp1_pct * 0.7 / 100)
        tp2 = avg_price_new * (1 + dynamic_tp2_pct * 0.7 / 100)
    else:
        # Для ранних DCA - обычные TP
        tp1 = avg_price_new * (1 + dynamic_tp1_pct / 100)
        tp2 = avg_price_new * (1 + dynamic_tp2_pct / 100)

    return new_qty, avg_price_new, tp1, tp2, False
```

**Логика:**

- **Базовое количество**: `deposit * risk_pct * leverage / price`
- **Увеличение с просадкой**: `(1 + ALPHA * drawdown)` где ALPHA = 2
- **Уменьшение с количеством DCA**: `/(1 + dca_count)`
- **Лимиты**: максимум 50% депозита, максимум 5 DCA
- **TP**: динамические на основе волатильности, консервативные для поздних DCA

## ⚙️ Конфигурация DCA

### Адаптивная просадка:

```python
DCA_DRAWDOWN_CONFIG = {
    "low_volatility": {
        "base_drawdown": 0.8,    # BTC, ETH
        "atr_threshold": 0.02,   # ATR < 2%
    },
    "medium_volatility": {
        "base_drawdown": 1.2,    # XRP, ADA
        "atr_threshold": 0.04,   # ATR 2-4%
    },
    "high_volatility": {
        "base_drawdown": 2.0,    # DOGE, SHIB
        "atr_threshold": 0.06,   # ATR > 4%
    }
}
```

### Множители рыночных условий:

```python
VOLATILITY_MULTIPLIERS = {
    "trending_market": 1.1,    # +10% в тренде
    "sideways_market": 0.9,    # -10% в боковике
    "high_volume": 1.05,       # +5% при высоком объеме
    "low_volume": 0.95         # -5% при низком объеме
}
```

### Технические условия:

```python
DCA_TECHNICAL_CONDITIONS = {
    "require_rsi_extreme": True,
    "rsi_oversold_threshold": 25,    # Для LONG DCA
    "rsi_overbought_threshold": 75,  # Для SHORT DCA
    "require_volume_confirmation": True,
    "min_volume_ratio": 1.5,
    "require_bb_touch": True,
    "bb_touch_threshold": 0.02,      # 2% от полосы
    "require_trend_confirmation": True,
    "min_trend_strength": 0.3,
    "require_volatility_check": True,
    "min_volatility_pct": 1.5,
    "max_volatility_pct": 8.0
}
```

## 🔄 Процесс DCA

### 1. **Проверка условий**

- Есть ли открытая позиция по символу
- Достигнута ли адаптивная просадка
- Выполнены ли технические условия (90%)
- Не превышены ли лимиты риска

### 2. **Расчет параметров**

- Адаптивная просадка на основе ATR
- Размер DCA позиции с учетом просадки
- Новая средняя цена после DCA
- Динамические TP для всех позиций

### 3. **Отправка сигнала**

- DCA сигнал с новыми параметрами
- Информация о средней цене
- Обновленные TP для быстрого выхода
- Кнопки принятия/отклонения

### 4. **Обновление позиции**

- Добавление DCA к существующей позиции
- Пересчет средней цены
- Обновление TP для всей позиции
- Логирование DCA операции

## 📊 Примеры DCA

### Пример 1: BTCUSDT (низкая волатильность)

```
Вход: 50,000 USDT
DCA 1: 49,600 USDT (просадка 0.8%)
DCA 2: 49,200 USDT (просадка 1.6%)
Средняя цена: 49,600 USDT
TP1: 50,096 USDT (+1.0%)
TP2: 50,592 USDT (+2.0%)
```

### Пример 2: XRPUSDT (средняя волатильность)

```
Вход: 0.5000 USDT
DCA 1: 0.4940 USDT (просадка 1.2%)
DCA 2: 0.4880 USDT (просадка 2.4%)
Средняя цена: 0.4940 USDT
TP1: 0.4989 USDT (+1.0%)
TP2: 0.5039 USDT (+2.0%)
```

### Пример 3: DOGEUSDT (высокая волатильность)

```
Вход: 0.0800 USDT
DCA 1: 0.0784 USDT (просадка 2.0%)
DCA 2: 0.0768 USDT (просадка 4.0%)
Средняя цена: 0.0784 USDT
TP1: 0.0792 USDT (+1.0%)
TP2: 0.0800 USDT (+2.0%)
```

## 🎯 Преимущества DCA системы

### 1. **Адаптивность**

- Просадка подстраивается под волатильность
- Учитывает рыночные условия
- Разные стратегии для разных активов

### 2. **Защита риска**

- Лимиты на максимальный риск (50% депозита)
- Максимум 5 DCA на позицию
- Консервативные TP для поздних DCA

### 3. **Оптимизация для интрадей**

- Быстрые просадки (0.5-3.0%)
- Динамические TP на основе волатильности
- Учет объема и тренда

### 4. **Интеграция с основной стратегией**

- Использует те же технические условия
- Единая логика сигналов
- Автоматическая оптимизация параметров

## ✅ Заключение

DCA система представляет собой умную стратегию усреднения, которая:

1. **Адаптируется** к волатильности каждого актива
2. **Защищает** от чрезмерного риска
3. **Оптимизируется** для интрадей торговли
4. **Интегрируется** с основной расширенной стратегией

Система обеспечивает эффективное управление позициями при просадках, увеличивая вероятность прибыльного выхода из сделок.

**Статус**: ✅ DCA логика полностью описана и оптимизирована
