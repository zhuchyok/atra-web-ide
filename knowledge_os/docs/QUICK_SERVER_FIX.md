# Быстрое исправление сервера

## 🚨 Проблема

На сервере не приходят сообщения в Telegram, проблемы с базой данных и TP колонками.

## 🔧 Быстрое решение

### 1. Запустить комплексное исправление:

```bash
python3 fix_server_complete.py
```

### 2. Или пошагово:

#### Шаг 1: Проверить и исправить базу данных

```bash
python3 check_database_structure.py
```

#### Шаг 2: Проверить Telegram бота

```bash
python3 check_telegram_bot.py
```

#### Шаг 3: Применить исправления DCA

```bash
python3 manual_dca_fix.py
```

#### Шаг 4: Перезапустить сервер

```bash
pkill -f "python.*main.py"
nohup python3 main.py > server.log 2>&1 &
```

## 🔍 Проверка результатов

### Проверить статус сервера:

```bash
ps aux | grep python | grep main.py
```

### Проверить логи:

```bash
tail -f server.log
```

### Проверить базу данных:

```bash
sqlite3 atra.db "SELECT COUNT(*) FROM signals_log;"
```

## 📊 Ожидаемые результаты

После исправления:

- ✅ База данных содержит все необходимые колонки
- ✅ Telegram бот отправляет сообщения
- ✅ DCA расчеты работают корректно
- ✅ Сервер стабильно работает

## 🚨 В случае проблем

### Откат к резервной копии:

```bash
# Найти резервную копию
ls -la | grep backup

# Восстановить файлы
cp server_complete_backup_*/signal_live.py ./
cp server_complete_backup_*/telegram_utils.py ./
cp server_complete_backup_*/atra.db ./

# Перезапустить сервер
pkill -f "python.*main.py"
nohup python3 main.py > server.log 2>&1 &
```

## 📞 Поддержка

Если проблемы остаются:

1. Проверьте логи: `tail -f server.log`
2. Проверьте статус: `ps aux | grep python`
3. Проверьте БД: `sqlite3 atra.db ".schema signals_log"`
4. Обратитесь за помощью
