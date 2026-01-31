# Команды для исправления сервера

## 🔗 Подключение к серверу
```bash
ssh root@185.177.216.15
# Пароль: u44Ww9NmtQj,XG
```

## 📋 Команды для выполнения на сервере

### 1. Перейти в директорию проекта
```bash
cd /root/atra
```

### 2. Остановить сервер
```bash
pkill -f 'python.*main.py'
```

### 3. Проверить и исправить базу данных
```bash
python3 check_database_structure.py
```

### 4. Применить исправления DCA
```bash
python3 manual_dca_fix.py
```

### 5. Проверить Telegram бота
```bash
python3 check_telegram_bot.py
```

### 6. Запустить сервер
```bash
nohup python3 main.py > server.log 2>&1 &
```

### 7. Проверить статус сервера
```bash
ps aux | grep python | grep main.py
```

### 8. Проверить логи
```bash
tail -f server.log
```

## 🔧 Альтернативный способ - комплексное исправление
```bash
python3 fix_server_complete.py
```

## 📊 Проверка результатов

### Проверить базу данных
```bash
sqlite3 trading.db "SELECT COUNT(*) FROM signals_log;"
```

### Проверить последние записи
```bash
sqlite3 trading.db "SELECT symbol, entry, tp1, tp2, entry_time, result FROM signals_log ORDER BY created_at DESC LIMIT 5;"
```

### Проверить структуру таблицы
```bash
sqlite3 trading.db ".schema signals_log"
```

## 🚨 В случае проблем

### Откат к резервной копии
```bash
# Найти резервную копию
ls -la | grep backup

# Восстановить файлы
cp server_complete_backup_*/signal_live.py ./
cp server_complete_backup_*/telegram_utils.py ./
cp server_complete_backup_*/trading.db ./
```

### Перезапуск сервера
```bash
pkill -f 'python.*main.py'
nohup python3 main.py > server.log 2>&1 &
```

## 📞 Поддержка

Если проблемы остаются:
1. Проверьте логи: `tail -f server.log`
2. Проверьте статус: `ps aux | grep python`
3. Проверьте БД: `sqlite3 trading.db ".schema signals_log"`
4. Обратитесь за помощью
