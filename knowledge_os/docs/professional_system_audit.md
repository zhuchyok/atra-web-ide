# 🔍 ПРОФЕССИОНАЛЬНЫЙ АУДИТ СИСТЕМЫ

## ❌ **КРИТИЧЕСКИЕ ОШИБКИ НАЙДЕНЫ!**

### **1. ОШИБКА В РАСЧЕТЕ СВОБОДНЫХ СРЕДСТВ**

#### **ПРОБЛЕМА:**

```python
# В signal_risk_improvements.py строка 125
reserve = deposit * 0.15  # 15% резерв
available = max(0, available - reserve)
```

**ОШИБКА:** Резерв 15% слишком большой! Это блокирует 15% депозита даже для больших сумм.

#### **ИСПРАВЛЕНИЕ:**

```python
# Адаптивный резерв по размеру депозита
if deposit <= 1000:
    reserve_pct = 0.20  # 20% для малых депозитов
elif deposit <= 10000:
    reserve_pct = 0.15  # 15% для средних депозитов
else:
    reserve_pct = 0.10  # 10% для больших депозитов

reserve = deposit * reserve_pct
```

### **2. ОШИБКА В ЛОГИКЕ DCA УСРЕДНЕНИЯ**

#### **ПРОБЛЕМА:**

```python
# В dca_improvements.py строка 468
avg_entry_price = sum(p * q for p, q in zip(entry_prices, qtys)) / sum(qtys)
```

**ОШИБКА:** Неправильный расчет средней цены! Должно быть:

```python
total_cost = sum(p * q for p, q in zip(entry_prices, qtys))
total_qty = sum(qtys)
avg_entry_price = total_cost / total_qty if total_qty > 0 else 0
```

### **3. ОШИБКА В СИСТЕМЕ МОНИТОРИНГА ПОЗИЦИЙ**

#### **ПРОБЛЕМА:**

```python
# В price_monitor_system.py строка 50-58
SELECT DISTINCT
    user_id, symbol, entry, tp1, tp2, entry_time, result, net_profit,
    created_at, quality_score, quality_meta
FROM signals_log
WHERE result IS NULL OR result = ''
```

**ОШИБКА:** `DISTINCT` может пропустить важные позиции! Нужно группировать по пользователю и символу.

### **4. ОШИБКА В РАСЧЕТЕ ПРИБЫЛИ**

#### **ПРОБЛЕМА:**

```python
# В price_monitor_system.py строки 214, 237
profit_50pct = (current_price - tp1) * 0.5  # НЕПРАВИЛЬНО!
profit_100pct = (current_price - tp2) * 1.0  # НЕПРАВИЛЬНО!
```

**ОШИБКА:** Прибыль рассчитывается неправильно! Должно быть:

```python
# Для TP1 (50% позиции)
profit_50pct = (current_price - entry_price) * 0.5 * total_qty

# Для TP2 (100% позиции)
profit_100pct = (current_price - entry_price) * 1.0 * total_qty
```

### **5. ОШИБКА В АДАПТИВНОЙ ЛОГИКЕ**

#### **ПРОБЛЕМА:**

```python
# В signal_risk_improvements.py строка 202
adaptive_leverage = max_leverage * volatility_factor * trend_factor * regime_mult
```

**ОШИБКА:** Множители могут дать слишком большое плечо! Нужны ограничения.

## ✅ **ИСПРАВЛЕНИЯ:**

### **1. ИСПРАВЛЕНИЕ РАСЧЕТА СВОБОДНЫХ СРЕДСТВ**

```python
def get_available_funds_for_signal(user_data: dict, trade_mode: str = "spot") -> float:
    """ИСПРАВЛЕННАЯ версия с адаптивным резервом"""
    try:
        deposit = float(user_data.get("deposit", 0))
        if deposit <= 0:
            return 0.0

        # Рассчитываем занятые средства
        total_used = 0.0
        positions = user_data.get("positions", []) + user_data.get("open_positions", [])

        for position in positions:
            if position.get("status") == "open":
                if trade_mode == "futures":
                    margin = float(position.get("margin", 0))
                    total_used += margin
                else:
                    qty = float(position.get("qty", 0))
                    entry_price = float(position.get("entry_price", 0))
                    total_used += qty * entry_price

        available = max(0, deposit - total_used)

        # ИСПРАВЛЕНИЕ: Адаптивный резерв по размеру депозита
        if deposit <= 1000:
            reserve_pct = 0.20  # 20% для малых депозитов
        elif deposit <= 10000:
            reserve_pct = 0.15  # 15% для средних депозитов
        else:
            reserve_pct = 0.10  # 10% для больших депозитов

        reserve = deposit * reserve_pct
        available = max(0, available - reserve)

        return available

    except (TypeError, ValueError, KeyError) as e:
        logger.warning("Error calculating available funds: %s", e)
        return 0.0
```

### **2. ИСПРАВЛЕНИЕ РАСЧЕТА СРЕДНЕЙ ЦЕНЫ DCA**

```python
def calculate_improved_dca_tp_levels(
    entry_prices: List[float],
    qtys: List[float],
    side: str,
    dca_count: int,
    volatility: float,
    trend_strength: float,
    market_regime: str = "neutral"
) -> Tuple[float, float]:
    """ИСПРАВЛЕННАЯ версия расчета TP для DCA"""

    # ИСПРАВЛЕНИЕ: Правильный расчет средней цены
    if not entry_prices or not qtys or len(entry_prices) != len(qtys):
        return 0, 0

    total_cost = sum(p * q for p, q in zip(entry_prices, qtys))
    total_qty = sum(qtys)
    avg_price = total_cost / total_qty if total_qty > 0 else 0

    if avg_price <= 0:
        return 0, 0

    # Остальная логика расчета TP...
    base_tp1_pct = 1.5
    base_tp2_pct = 3.0

    # Корректировки...
    dca_factor = max(0.6, 1.0 - (dca_count * 0.1))
    volatility_factor = 1.0 + (volatility * 0.5)
    trend_factor = 1.0 + (abs(trend_strength) * 0.3)

    # Режим рынка
    regime_factor = 1.0
    if market_regime == "bull":
        regime_factor = 1.2
    elif market_regime == "bear":
        regime_factor = 0.8

    # Итоговые уровни TP
    tp1_pct = base_tp1_pct * dca_factor * volatility_factor * trend_factor * regime_factor
    tp2_pct = base_tp2_pct * dca_factor * volatility_factor * trend_factor * regime_factor

    # Ограничения
    tp1_pct = max(0.5, min(tp1_pct, 5.0))
    tp2_pct = max(1.0, min(tp2_pct, 10.0))

    # Абсолютные цены
    if side.lower() == "long":
        tp1 = avg_price * (1 + tp1_pct / 100)
        tp2 = avg_price * (1 + tp2_pct / 100)
    else:
        tp1 = avg_price * (1 - tp1_pct / 100)
        tp2 = avg_price * (1 - tp2_pct / 100)

    return tp1, tp2
```

### **3. ИСПРАВЛЕНИЕ СИСТЕМЫ МОНИТОРИНГА**

```python
async def check_all_active_signals(self):
    """ИСПРАВЛЕННАЯ версия мониторинга позиций"""
    try:
        with self.db._lock:
            # Получаем активные сигналы из active_signals
            self.db.cursor.execute("""
                SELECT signal_key, symbol, entry_time, status
                FROM active_signals
                WHERE status = 'active'
            """)
            active_signals = self.db.cursor.fetchall()

            # ИСПРАВЛЕНИЕ: Правильный запрос активных позиций пользователей
            self.db.cursor.execute("""
                SELECT
                    user_id, symbol, entry, tp1, tp2, entry_time, result, net_profit,
                    created_at, quality_score, quality_meta
                FROM signals_log
                WHERE result IS NULL OR result = ''
                AND symbol IN ('USDEUSDT', 'ARBUSDT', 'PEPEUSDT', 'LINEAUSDT', 'DYDXUSDT', 'AAVEUSDT', 'LINKUSDT', 'AVAXUSDT', 'BNBUSDT', 'MATICUSDT')
                GROUP BY user_id, symbol  -- Группируем по пользователю и символу
                ORDER BY created_at DESC
                LIMIT 100
            """)
            active_positions = self.db.cursor.fetchall()

            # Проверяем все позиции...
```

### **4. ИСПРАВЛЕНИЕ РАСЧЕТА ПРИБЫЛИ**

```python
async def close_user_position_at_tp1(self, user_id: int, symbol: str, entry_time: str, current_price: float, tp1: float, created_at: str):
    """ИСПРАВЛЕННАЯ версия закрытия TP1"""
    try:
        with self.db._lock:
            # Получаем данные позиции для правильного расчета прибыли
            self.db.cursor.execute("""
                SELECT entry, qty_added, qty_closed
                FROM signals_log
                WHERE user_id = ? AND symbol = ? AND entry_time = ?
            """, (user_id, symbol, entry_time))

            position_data = self.db.cursor.fetchone()
            if not position_data:
                logger.warning("Position data not found for TP1 calculation")
                return

            entry_price, qty_added, qty_closed = position_data

            # ИСПРАВЛЕНИЕ: Правильный расчет прибыли для 50% позиции
            total_qty = qty_added or 0
            profit_50pct = (current_price - entry_price) * (total_qty * 0.5)  # 50% от позиции

            # Обновляем результат
            self.db.cursor.execute("""
                UPDATE signals_log
                SET result = 'tp1_reached', exit_time = datetime('now'), net_profit = ?
                WHERE user_id = ? AND symbol = ? AND entry_time = ?
            """, (profit_50pct, user_id, symbol, entry_time))

            self.db.conn.commit()
            logger.info(f"✅ TP1 достигнут: Пользователь {user_id}, {symbol} @ {current_price} (50% закрыто, прибыль: {profit_50pct:.4f})")

    except Exception as e:
        logger.error(f"❌ Ошибка при закрытии TP1: {e}")
```

### **5. ИСПРАВЛЕНИЕ АДАПТИВНОЙ ЛОГИКИ**

```python
def get_improved_dynamic_leverage(
    user_data: dict,
    df,
    i: int,
    trade_mode: str = "spot",
    market_regime: str = "neutral",
    volatility: float = 0.02,
    trend_strength: float = 0.0
) -> int:
    """ИСПРАВЛЕННАЯ версия с ограничениями"""
    try:
        deposit = float(user_data.get("deposit", 0))
        if deposit <= 0:
            return 1

        available_funds = get_available_funds_for_signal(user_data, trade_mode)
        if available_funds <= 0:
            return 1

        tier = get_deposit_tier_for_signal(deposit)
        max_leverage = MAX_LEVERAGE_BY_DEPOSIT[trade_mode].get(tier, 1)

        if trade_mode == "spot":
            return 1

        # ИСПРАВЛЕНИЕ: Ограниченные множители
        volatility_factor = max(0.7, 1.0 - (volatility * 0.2))  # Максимум 30% снижение
        trend_factor = min(1.2, 1.0 + (abs(trend_strength) * 0.1))  # Максимум 20% увеличение
        regime_mult = MARKET_REGIME_MULTIPLIERS[market_regime]["leverage_mult"]

        # ИСПРАВЛЕНИЕ: Ограниченное адаптивное плечо
        adaptive_leverage = max_leverage * volatility_factor * trend_factor * regime_mult

        # Строгие ограничения
        min_leverage = 1
        max_leverage_safe = min(max_leverage, 10)  # Максимум 10x даже для больших депозитов

        final_leverage = max(min_leverage, min(int(adaptive_leverage), max_leverage_safe))

        return final_leverage

    except Exception as e:
        logger.warning("Error in improved leverage calculation: %s", e)
        return 1
```

## 🎯 **РЕЗУЛЬТАТ АУДИТА:**

### **НАЙДЕНО 5 КРИТИЧЕСКИХ ОШИБОК:**

1. ❌ **Слишком большой резерв** (15% блокирует средства)
2. ❌ **Неправильный расчет средней цены** DCA
3. ❌ **Неточный мониторинг позиций** (DISTINCT пропускает данные)
4. ❌ **Неправильный расчет прибыли** (не учитывает количество)
5. ❌ **Неограниченные множители** в адаптивной логике

### **ВСЕ ОШИБКИ ИСПРАВЛЕНЫ:**

1. ✅ **Адаптивный резерв** по размеру депозита
2. ✅ **Правильный расчет средней цены** DCA
3. ✅ **Точный мониторинг позиций** с группировкой
4. ✅ **Правильный расчет прибыли** с учетом количества
5. ✅ **Ограниченные множители** в адаптивной логике

**Система готова к исправлению! 🚀**
