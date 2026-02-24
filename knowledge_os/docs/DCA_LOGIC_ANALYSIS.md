# 📊 ЛОГИКА ФОРМИРОВАНИЯ DCA СИГНАЛОВ

## 🔄 **ОБЩИЙ ПРИНЦИП DCA (Dollar-Cost Averaging)**

DCA (усреднение) - это стратегия покупки дополнительных единиц актива по более низкой цене для снижения средней цены входа в позицию.

---

## 🧮 **ОСНОВНАЯ ФУНКЦИЯ РАСЧЕТА DCA**

### **Функция:** `dca_calculate_next_qty_and_tp()`

```python
def dca_calculate_next_qty_and_tp(
    entry_prices, qtys, price, dca_count, deposit, risk_pct,
    leverage=1, side="long", df=None, current_index=None,
    anomaly_circles_count=0
):
```

### **Входные параметры:**

- `entry_prices` - список цен входа в позицию
- `qtys` - список количеств по каждой цене
- `price` - текущая цена для усреднения
- `dca_count` - количество уже выполненных DCA
- `deposit` - депозит пользователя
- `risk_pct` - процент риска на сделку
- `leverage` - плечо
- `side` - сторона позиции (long/short)
- `df` - DataFrame с данными для динамических TP
- `current_index` - текущий индекс в данных
- `anomaly_circles_count` - количество аномальных кругов

---

## 📈 **ЛОГИКА РАСЧЕТА КОЛИЧЕСТВА DCA**

### **1. Базовое количество:**

```python
base_qty = deposit * risk_pct / 100 * leverage / price
```

### **2. Корректировка на основе аномалии:**

```python
if anomaly_circles_count > 0:
    adjusted_volume, volume_multiplier, recommendation = calculate_anomaly_based_volume(
        base_qty * price, anomaly_circles_count, deposit
    )
    base_qty = adjusted_volume / price
    adjusted_risk, risk_multiplier = calculate_anomaly_based_risk(risk_pct, anomaly_circles_count)
    risk_pct = adjusted_risk
```

### **3. Расчет с учетом просадки:**

```python
avg_price = sum(p * q for p, q in zip(entry_prices, qtys)) / sum(qtys)
drawdown = abs((avg_price - price) / avg_price)
new_qty = base_qty * (1 + ALPHA * drawdown) / (1 + dca_count)
```

**Где:**

- `ALPHA` - коэффициент увеличения объема при просадке
- `drawdown` - процент просадки от средней цены
- `dca_count` - уменьшает объем с каждым DCA

---

## 🛡️ **ПРОВЕРКИ ЛИМИТОВ**

### **1. Максимальный риск:**

```python
used_risk = sum(q * p for q, p in zip(qtys, entry_prices)) + new_qty * price
max_risk = deposit * MAX_RISK_PCT / 100 * leverage
if used_risk > max_risk or dca_count >= MAX_DCA:
    return 0, avg_price, None, None, True
```

### **2. Лимиты:**

- `MAX_RISK_PCT` - максимальный процент риска (обычно 30%)
- `MAX_DCA` - максимальное количество DCA (обычно 5)

---

## 🎯 **РАСЧЕТ НОВОЙ СРЕДНЕЙ ЦЕНЫ**

```python
total_qty = sum(qtys) + new_qty
total_cost = sum(q * p for q, p in zip(qtys, entry_prices)) + new_qty * price
avg_price_new = total_cost / total_qty
```

---

## 📊 **ДИНАМИЧЕСКИЕ ТЕЙК-ПРОФИТЫ**

### **1. Получение динамических TP:**

```python
if df is not None and current_index is not None:
    dynamic_tp1_pct, dynamic_tp2_pct = get_dynamic_tp_levels(df, current_index, side)
else:
    dynamic_tp1_pct, dynamic_tp2_pct = 1.0, 2.0
```

### **2. Расчет TP для LONG:**

```python
if side == "long":
    if dca_count + 1 >= 3:
        # Для поздних усреднений - более консервативные TP
        tp1 = avg_price_new * (1 + dynamic_tp1_pct * 0.7 / 100)
        tp2 = avg_price_new * (1 + dynamic_tp2_pct * 0.7 / 100)
    else:
        tp1 = avg_price_new * (1 + dynamic_tp1_pct / 100)
        tp2 = avg_price_new * (1 + dynamic_tp2_pct / 100)
```

### **3. Расчет TP для SHORT:**

```python
else:  # short
    if dca_count + 1 >= 3:
        # Для поздних усреднений - более консервативные TP
        tp1 = avg_price_new * (1 - dynamic_tp1_pct * 0.7 / 100)
        tp2 = avg_price_new * (1 - dynamic_tp2_pct * 0.7 / 100)
    else:
        tp1 = avg_price_new * (1 - dynamic_tp1_pct / 100)
        tp2 = avg_price_new * (1 - dynamic_tp2_pct / 100)
```

---

## 🔍 **УСЛОВИЯ АКТИВАЦИИ DCA**

### **Функция:** `should_dca()`

```python
def should_dca(side, last_close, stop_loss, dca_pct):
    if side == "long":
        return last_close <= stop_loss * (1 - dca_pct / 100)
    else:
        return last_close >= stop_loss * (1 + dca_pct / 100)
```

**Логика:**

- **LONG:** DCA активируется, когда цена падает ниже `stop_loss * (1 - dca_pct/100)`
- **SHORT:** DCA активируется, когда цена растет выше `stop_loss * (1 + dca_pct/100)`

---

## 📋 **ПРОЦЕСС ФОРМИРОВАНИЯ DCA СИГНАЛА**

### **1. Проверка открытых позиций:**

```python
user_positions = user_data.get('open_positions', [])
has_user_long = any(
    pos["symbol"] == symbol and pos.get("side", "long") == "long"
    for pos in user_positions
)
```

### **2. Получение данных позиции:**

```python
if has_user_long:
    pos = next((p for p in user_positions if p['symbol'] == symbol and p.get('side', 'long') == 'long'), None)
    if pos:
        entry_prices = pos.get('entry_prices', [pos.get('entry_price', last['close'])])
        qtys = pos.get('qtys', [pos.get('qty', 1)])
        dca_count = pos.get('n_dca', 0)
```

### **3. Расчет нового DCA:**

```python
new_qty, avg_price_new, tp1, tp2, limit_reached = dca_calculate_next_qty_and_tp(
    entry_prices, qtys, last['close'], dca_count, deposit, risk_pct,
    leverage, side='long', df=df, current_index=len(df)-1
)
```

### **4. Проверка лимитов:**

```python
if limit_reached or new_qty <= 0:
    continue  # лимит усреднений или риска
```

---

## 📊 **ИНФОРМАЦИЯ В DCA СИГНАЛЕ**

### **Основные данные:**

- **Символ** и **сторона** позиции
- **Цена усреднения** (текущая цена)
- **Новая средняя цена** после DCA
- **Количество для покупки** (new_qty)
- **Динамические TP1 и TP2**
- **Процент прибыли** для каждого TP

### **Технический анализ:**

- RSI, MACD, Объем, EMA, Bollinger Bands
- BTC тренд (если включен)
- Данные о китах (если включены)
- Индикатор аномалий

### **Риск-менеджмент:**

- **Текущий риск** в позиции
- **Максимальный риск** (лимит)
- **Количество DCA** (n_dca)
- **Общий объем** позиции

---

## 🔄 **ОСОБЕННОСТИ DCA ДЛЯ SHORT**

### **Логика усреднения:**

- **LONG:** усреднение вниз (покупаем дешевле)
- **SHORT:** усреднение вверх (продаем дороже)

### **Расчет TP для SHORT:**

```python
profit_pct_tp1 = ((avg_price_new - tp1) / avg_price_new) * 100
profit_pct_tp2 = ((avg_price_new - tp2) / avg_price_new) * 100
```

---

## ⚠️ **ОГРАНИЧЕНИЯ И ЗАЩИТЫ**

### **1. Максимальный риск:**

- Не более 30% депозита в одной позиции
- Учитывает все предыдущие входы

### **2. Максимальное количество DCA:**

- Обычно 5 DCA на позицию
- Предотвращает чрезмерное усреднение

### **3. Минимальное количество:**

- Если `new_qty <= 0`, DCA не отправляется

### **4. Консервативные TP для поздних DCA:**

- После 3-го DCA TP уменьшаются на 30%
- Снижает риск при глубокой просадке

---

## 🎯 **ПРЕИМУЩЕСТВА СИСТЕМЫ DCA**

1. **Автоматическое усреднение** при просадке
2. **Динамические TP** на основе волатильности
3. **Защита от чрезмерного риска**
4. **Интеграция с техническим анализом**
5. **Учет аномалий рынка**
6. **Адаптация к рыночным условиям**

---

## 📈 **ПРИМЕР РАБОТЫ DCA**

### **Сценарий LONG позиции:**

1. **Первый вход:** 100 USDT по цене 50,000
2. **Цена падает до 45,000** → активируется DCA
3. **DCA расчет:** дополнительно 120 USDT по 45,000
4. **Новая средняя цена:** 47,273
5. **Динамические TP:** +4.7% и +9.3% от новой средней
6. **Общий риск:** 220 USDT (в пределах лимита)

### **Результат:**

- **Снижение средней цены** с 50,000 до 47,273
- **Увеличение объема** позиции
- **Более быстрый выход в прибыль** при развороте
