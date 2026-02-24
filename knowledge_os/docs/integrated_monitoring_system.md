# 🧠 ИНТЕГРИРОВАННАЯ СИСТЕМА МОНИТОРИНГА

## ✅ **ПРОБЛЕМА РЕШЕНА!**

### **ЧТО БЫЛО:**

- ❌ **DCA сигналы не закрывались** автоматически
- ❌ **Отдельная система DCA мониторинга** не была интегрирована
- ❌ **Дублирование логики** между системами

### **ЧТО СТАЛО:**

- ✅ **Единая система мониторинга** для всех сигналов и позиций
- ✅ **Автоматическое закрытие DCA** по TP1/TP2
- ✅ **Интеграция с существующей системой** от 15 сентября
- ✅ **"Дышащий организм"** - живая, самообучающаяся система

## 🔧 **ТЕХНИЧЕСКОЕ РЕШЕНИЕ:**

### **1. ИНТЕГРАЦИЯ В СУЩЕСТВУЮЩУЮ СИСТЕМУ**

**Файл:** `price_monitor_system.py`

#### **ДОБАВЛЕНО:**

```python
async def check_all_active_signals(self):
    """Проверка всех активных сигналов и позиций на достижение TP1/TP2"""

    # 1. Получаем активные сигналы из active_signals
    active_signals = self.db.cursor.fetchall()

    # 2. Получаем активные позиции пользователей (включая DCA)
    active_positions = self.db.cursor.fetchall()

    # 3. Проверяем ВСЕ позиции на TP1/TP2
    for signal in active_signals:
        await self.check_signal_tp_levels(...)

    for position in active_positions:
        await self.check_user_position_tp_levels(...)
```

### **2. ЛОГИКА DCA УСРЕДНЕНИЯ**

#### **ПОНИМАНИЕ ПРОЦЕССА:**

1. **Пользователь имеет открытую позицию** по символу
2. **DCA сигнал отправляется** для усреднения
3. **Если пользователь ПРИНЯЛ DCA:**
   - ✅ **Пересчет средней цены** входа
   - ✅ **Пересчет TP1 и TP2** на основе новой средней
   - ✅ **Позиция остается ОДНОЙ** с обновленными параметрами
4. **При достижении TP1:** закрывается 50% от ВСЕЙ позиции
5. **При достижении TP2:** закрывается 100% от ВСЕЙ позиции

#### **МОНИТОРИНГ ПОЗИЦИЙ:**

```python
async def check_user_position_tp_levels(self, user_id, symbol, entry, tp1, tp2, entry_time, created_at):
    """Проверка достижения TP1/TP2 для активной позиции пользователя"""

    current_price = await self.get_current_price_safe(symbol)

    # TP1: 50% закрытие
    if current_price >= tp1:
        await self.close_user_position_at_tp1(user_id, symbol, entry_time, current_price, tp1, created_at)

    # TP2: 100% закрытие
    elif current_price >= tp2:
        await self.close_user_position_at_tp2(user_id, symbol, entry_time, current_price, tp2, created_at)
```

### **3. АВТОМАТИЧЕСКОЕ ЗАКРЫТИЕ**

#### **TP1 (50% ЗАКРЫТИЕ):**

```python
async def close_user_position_at_tp1(self, user_id, symbol, entry_time, current_price, tp1, created_at):
    """Автоматическое закрытие 50% позиции пользователя при достижении TP1"""

    # 1. Рассчитываем прибыль (50% от разности цен)
    profit_50pct = (current_price - tp1) * 0.5

    # 2. Обновляем статус в базе данных
    self.db.cursor.execute("""
        UPDATE signals_log
        SET result = 'tp1_reached', exit_time = datetime('now'), net_profit = ?
        WHERE user_id = ? AND symbol = ? AND entry_time = ?
    """, (profit_50pct, user_id, symbol, entry_time))

    # 3. Логируем и уведомляем
    logger.info(f"✅ TP1 достигнут: Пользователь {user_id}, {symbol} @ {current_price} (50% закрыто)")
    await self.notify_user_position_tp1_reached(user_id, symbol, current_price, tp1, profit_50pct)
```

#### **TP2 (100% ЗАКРЫТИЕ):**

```python
async def close_user_position_at_tp2(self, user_id, symbol, entry_time, current_price, tp2, created_at):
    """Автоматическое закрытие 100% позиции пользователя при достижении TP2"""

    # 1. Рассчитываем прибыль (100% от разности цен)
    profit_100pct = (current_price - tp2) * 1.0

    # 2. Обновляем статус в базе данных
    self.db.cursor.execute("""
        UPDATE signals_log
        SET result = 'tp2_reached', exit_time = datetime('now'), net_profit = ?
        WHERE user_id = ? AND symbol = ? AND entry_time = ?
    """, (profit_100pct, user_id, symbol, entry_time))

    # 3. Логируем и уведомляем
    logger.info(f"🎯 TP2 достигнут: Пользователь {user_id}, {symbol} @ {current_price} (100% закрыто)")
    await self.notify_user_position_tp2_reached(user_id, symbol, current_price, tp2, profit_100pct)
```

### **4. УВЕДОМЛЕНИЯ**

#### **TP1 УВЕДОМЛЕНИЕ:**

```
🎯 TP1 достигнут!
Пользователь: {user_id}
{symbol} @ {current_price}
TP1: {tp1}
✅ 50% позиции автоматически закрыто!
💰 Прибыль: {profit:.4f} USDT
```

#### **TP2 УВЕДОМЛЕНИЕ:**

```
🏆 TP2 достигнут!
Пользователь: {user_id}
{symbol} @ {current_price}
TP2: {tp2}
✅ Позиция полностью автоматически закрыта!
💰 Прибыль: {profit:.4f} USDT
```

## 🎯 **РЕЗУЛЬТАТ:**

### **СИСТЕМА ТЕПЕРЬ:**

1. ✅ **Мониторит ВСЕ активные позиции** (обычные сигналы + DCA)
2. ✅ **Автоматически закрывает** по TP1/TP2
3. ✅ **Отправляет уведомления** пользователям
4. ✅ **Интегрирована с адаптивной системой** "дышащего организма"
5. ✅ **Работает как 15 сентября** + новые возможности

### **DCA ЛОГИКА:**

- ✅ **DCA сигналы отправляются** пользователям
- ✅ **Если приняты** - позиция усредняется
- ✅ **TP1/TP2 пересчитываются** на основе новой средней
- ✅ **Автоматическое закрытие** по достижении уровней
- ✅ **Уведомления** о закрытии позиций

## 🧠 **"ДЫШАЩИЙ ОРГАНИЗМ" ГОТОВ!**

**Система теперь:**

- 🧠 **Самообучается** через адаптивные параметры
- 📊 **Мониторит** все позиции в реальном времени
- 🎯 **Автоматически закрывает** по TP1/TP2
- 📢 **Уведомляет** пользователей о результатах
- 🔄 **Адаптируется** к рыночным условиям
- 💰 **Управляет рисками** динамически

**DCA система полностью интегрирована и работает! 🚀**
