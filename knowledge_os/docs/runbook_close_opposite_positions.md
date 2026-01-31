# Runbook: Закрытие старых позиций перед сменой направления

## Обзор
Этот runbook описывает процедуру закрытия старых позиций перед открытием противоположных позиций, чтобы избежать наложения направлений и неожиданных стоп-ордеров.

## Автоматическая процедура

### Текущая реализация
Система **автоматически** закрывает противоположные позиции перед открытием новых через `auto_execution.py`:

```python
# Автозакрытие противоположных позиций (строки 234-300)
if opposite_positions:
    # Автоматическое закрытие через market ордер
    close_order = await close_adapter.create_market_order(symbol, close_side, pos_size)
    # Обновление статуса в БД
    await self.acceptance_db.close_active_position_by_symbol(user_id, symbol)
```

### Когда срабатывает
- Перед открытием новой позиции система проверяет существующие позиции
- Если найдены противоположные позиции (BUY при открытии SELL или наоборот)
- Система автоматически закрывает их через market ордер
- Затем открывает новую позицию в нужном направлении

## Ручная процедура (если автоматика не сработала)

### Шаг 1: Проверка активных позиций
```bash
# Проверить активные позиции в БД
sqlite3 trading.db "SELECT symbol, direction, entry_price, entry_time FROM active_positions WHERE status='open' ORDER BY symbol;"

# Проверить позиции на Bitget
cd /root/atra
python3 -c "
import asyncio
from exchange_adapter import ExchangeAdapter
from key_encryption import load_encrypted_keys

async def check_positions():
    keys = load_encrypted_keys('bitget', user_id=556251171)
    adapter = ExchangeAdapter('bitget', keys=keys, sandbox=False, trade_mode='futures')
    positions = await adapter.fetch_positions()
    for pos in positions:
        if float(pos.get('contracts', 0) or 0) > 0:
            print(f\"{pos['symbol']}: {pos['side']} {pos['contracts']} @ {pos['entryPrice']}\")
    await adapter.client.close()

asyncio.run(check_positions())
"
```

### Шаг 2: Закрытие противоположных позиций

#### Вариант A: Через Telegram бота
```
/close_position <symbol> <direction>
```

#### Вариант B: Через Python скрипт
```python
import asyncio
from exchange_adapter import ExchangeAdapter
from key_encryption import load_encrypted_keys
from acceptance_database import AcceptanceDatabase

async def close_opposite_position(symbol: str, user_id: int, direction: str):
    """Закрывает противоположную позицию"""
    keys = load_encrypted_keys('bitget', user_id=user_id)
    adapter = ExchangeAdapter('bitget', keys=keys, sandbox=False, trade_mode='futures')
    
    # Получаем позиции
    positions = await adapter.fetch_positions()
    for pos in positions:
        if pos['symbol'].replace('/', '').replace(':USDT', '').upper() == symbol.upper():
            pos_side = pos['side'].lower()
            close_side = 'buy' if pos_side == 'sell' else 'sell'
            pos_size = float(pos.get('contracts', 0) or 0)
            
            if pos_size > 0:
                # Закрываем через market ордер
                order = await adapter.create_market_order(symbol, close_side, pos_size)
                if order:
                    print(f"✅ Позиция {symbol} {pos_side} закрыта")
                    
                    # Обновляем БД
                    adb = AcceptanceDatabase()
                    await adb.close_active_position_by_symbol(user_id, symbol)
                else:
                    print(f"❌ Ошибка закрытия позиции {symbol}")
    
    await adapter.client.close()

# Использование
asyncio.run(close_opposite_position('DASHUSDT', 556251171, 'SELL'))
```

### Шаг 3: Проверка закрытия
```bash
# Проверить, что позиция закрыта
sqlite3 trading.db "SELECT * FROM active_positions WHERE symbol='DASHUSDT' AND status='open';"

# Проверить на Bitget
# (использовать скрипт из Шага 1)
```

### Шаг 4: Открытие новой позиции
После закрытия противоположной позиции можно открывать новую:
- Через Telegram бота: `/accept <signal_key>`
- Автоматически: система откроет позицию при следующем сигнале

## Аварийное закрытие всех позиций по символу

Если нужно закрыть все позиции по символу (и LONG, и SHORT):

```python
import asyncio
from exchange_adapter import ExchangeAdapter
from key_encryption import load_encrypted_keys
from acceptance_database import AcceptanceDatabase

async def close_all_positions_by_symbol(symbol: str, user_id: int):
    """Закрывает все позиции по символу"""
    keys = load_encrypted_keys('bitget', user_id=user_id)
    adapter = ExchangeAdapter('bitget', keys=keys, sandbox=False, trade_mode='futures')
    
    positions = await adapter.fetch_positions()
    closed_count = 0
    
    for pos in positions:
        pos_symbol = pos['symbol'].replace('/', '').replace(':USDT', '')
        if pos_symbol.upper() == symbol.upper():
            pos_side = pos['side'].lower()
            close_side = 'buy' if pos_side == 'sell' else 'sell'
            pos_size = float(pos.get('contracts', 0) or 0)
            
            if pos_size > 0:
                order = await adapter.create_market_order(symbol, close_side, pos_size)
                if order:
                    closed_count += 1
                    print(f"✅ Закрыта позиция {symbol} {pos_side} (size: {pos_size})")
    
    # Обновляем БД
    if closed_count > 0:
        adb = AcceptanceDatabase()
        await adb.close_active_position_by_symbol(user_id, symbol)
        print(f"✅ Закрыто позиций: {closed_count}")
    
    await adapter.client.close()

# Использование
asyncio.run(close_all_positions_by_symbol('DASHUSDT', 556251171))
```

## Мониторинг и алерты

### Автоматические алерты
Система автоматически логирует закрытие противоположных позиций:
```
✅ [AUTO] DASHUSDT: противоположная позиция SELL закрыта (size=12.29)
```

### Проверка логов
```bash
# Проверить логи автоисполнения
grep "противоположная позиция" /root/atra/logs/system.log

# Проверить логи risk_monitor
grep "opposite_positions" /root/atra/logs/pm_auto_fix.log
```

## Предотвращение проблем

### Рекомендации
1. **Всегда проверяйте активные позиции** перед открытием новых вручную
2. **Используйте автоматический режим** — система сама закроет противоположные позиции
3. **Мониторьте логи** на предмет предупреждений о противоположных позициях
4. **Проверяйте метрики** `limit_vs_market_ratio` для контроля качества исполнения

### Автоматические проверки
Система автоматически:
- ✅ Проверяет существующие позиции перед открытием
- ✅ Блокирует дубликаты (та же позиция по символу и направлению)
- ✅ Закрывает противоположные позиции перед открытием новых
- ✅ Логирует все действия в `order_audit_log`

## Troubleshooting

### Проблема: Позиция не закрылась автоматически
**Решение:**
1. Проверить логи: `grep "противоположная позиция" logs/system.log`
2. Проверить статус позиции на Bitget
3. Закрыть вручную через скрипт из Шага 2

### Проблема: Позиция закрылась, но осталась в БД
**Решение:**
```sql
-- Обновить статус вручную
UPDATE active_positions SET status='closed' WHERE symbol='DASHUSDT' AND status='open';
```

### Проблема: Множественные позиции по одному символу
**Решение:**
```python
# Использовать скрипт из раздела "Аварийное закрытие"
asyncio.run(close_all_positions_by_symbol('DASHUSDT', 556251171))
```

## Связанные документы
- `docs/incidents/2025-11-12_dashusdt.md` — описание инцидента
- `docs/runbook_bitget_stoploss.md` — runbook по SL/TP
- `auto_execution.py` (строки 234-300) — код автозакрытия

---

**Версия:** 1.0  
**Дата создания:** 2025-11-13  
**Статус:** Активен  
**Автор:** AI Project Manager

