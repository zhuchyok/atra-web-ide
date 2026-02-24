# МОНИТОРИНГ АКТИВНОСТИ БОТА

## 🤔 ПОЧЕМУ НЕТ АКТИВНОСТИ В ТЕРМИНАЛЕ?

Это **НОРМАЛЬНО**! Бот работает в фоновом режиме и не выводит информацию в терминал.

## 🔍 КАК ПРОВЕРИТЬ, ЧТО БОТ РАБОТАЕТ

### 1. Автоматическая проверка:

```bash
cd ~/atra
git pull
python3 check_bot_activity.py
```

### 2. Ручная проверка:

#### Проверьте процессы:

```bash
ps aux | grep -E "(signal_live|main\.py)"
```

#### Проверьте логи:

```bash
# Основной лог
tail -f signal_live.log

# Системный лог
tail -f system_improved.log

# Все логи
tail -f *.log
```

#### Проверьте активность в базе данных:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

# Сигналы за последний час
cursor.execute('SELECT COUNT(*) FROM signals WHERE datetime(ts) > datetime(\"now\", \"-1 hour\")')
print(f'📈 Сигналов за час: {cursor.fetchone()[0]}')

# Активные сигналы
cursor.execute('SELECT COUNT(*) FROM active_signals WHERE status = \"active\"')
print(f'🎯 Активных сигналов: {cursor.fetchone()[0]}')

# Последние сигналы
cursor.execute('SELECT symbol, ts FROM signals ORDER BY datetime(ts) DESC LIMIT 3')
recent = cursor.fetchall()
print('📋 Последние сигналы:')
for symbol, ts in recent:
    print(f'   {symbol} - {ts}')

conn.close()
"
```

## 📱 ПРОВЕРКА TELEGRAM

### Отправьте команды боту в Telegram:

- `/start` - проверка работы
- `/status` - статус бота
- `/stats` - статистика
- `/help` - список команд

### Если бот отвечает в Telegram:

✅ **Бот работает!** Просто он работает в фоновом режиме.

## 🔄 МОНИТОРИНГ В РЕАЛЬНОМ ВРЕМЕНИ

### Следите за логами:

```bash
# В одном терминале
tail -f signal_live.log

# В другом терминале
tail -f system_improved.log
```

### Следите за активностью:

```bash
# Каждые 10 секунд
watch -n 10 "python3 -c \"
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM signals WHERE datetime(ts) > datetime(\\\"now\\\", \\\"-1 hour\\\")')
print(f'Сигналов за час: {cursor.fetchone()[0]}')
conn.close()
\""
```

## ✅ ПРИЗНАКИ РАБОТАЮЩЕГО БОТА

1. **Процесс запущен**: `ps aux | grep python` показывает процесс
2. **Telegram отвечает**: бот отвечает на команды
3. **Логи обновляются**: `tail -f signal_live.log` показывает новую активность
4. **База данных активна**: новые записи появляются в БД
5. **Нет ошибок**: логи не содержат критических ошибок

## 🚨 ЕСЛИ БОТ НЕ РАБОТАЕТ

### Перезапустите бота:

```bash
# Остановите процесс
ps aux | grep python
kill -9 <PID>

# Запустите заново
python3 signal_live.py &
```

### Проверьте после перезапуска:

```bash
ps aux | grep python
tail -f signal_live.log
```

## 💡 ОБЪЯСНЕНИЕ

**Бот работает в фоновом режиме** - это нормально! Он:

- ✅ Обрабатывает сигналы
- ✅ Отвечает в Telegram
- ✅ Сохраняет данные в БД
- ✅ Работает без вывода в терминал

**Для мониторинга используйте логи**, а не терминал!

---

_Инструкция создана: 2025-10-07_
