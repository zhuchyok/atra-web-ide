# 🚀 ИНСТРУКЦИИ: Обновление и перезапуск на сервере

## 📋 БЫСТРЫЕ КОМАНДЫ

### 1. Обновить код с Git

```bash
cd /root/atra
git pull origin main  # или master, в зависимости от ветки
```

### 2. Проверить конфигурацию

```bash
cd /root/atra
echo "=== ПРОВЕРКА КОНФИГУРАЦИИ ==="
echo ""
echo "1. PROD бот (должен быть ATRA_ENV=prod):"
grep "^ATRA_ENV" env
echo ""
echo "2. Токены:"
grep "^TELEGRAM_TOKEN" env
echo ""
echo "3. Процессы:"
ps aux | grep "python.*main" | grep -v grep
```

### 3. Исправить ATRA_ENV (если нужно)

**Для PROD бота:**
```bash
cd /root/atra
sed -i 's/^ATRA_ENV=.*/ATRA_ENV=prod/' env
grep "^ATRA_ENV" env  # Проверяем
```

**Для DEV бота (если запущен отдельно):**
```bash
# Если DEV бот в отдельной директории
cd /root/atra-dev  # или другая директория
sed -i 's/^ATRA_ENV=.*/ATRA_ENV=dev/' env
grep "^ATRA_ENV" env  # Проверяем
```

### 4. Остановить боты

```bash
# Остановить все процессы main.py
pkill -f "python.*main"

# Подождать 5 секунд
sleep 5

# Проверить, что процессы остановлены
ps aux | grep "python.*main" | grep -v grep
```

### 5. Запустить PROD бот

```bash
cd /root/atra

# Убедитесь, что ATRA_ENV=prod
grep "^ATRA_ENV" env

# Запустить PROD бот
nohup python3 main.py > logs/prod_bot.log 2>&1 &

# Подождать 3 секунды
sleep 3

# Проверить запуск
ps aux | grep "python.*main" | grep -v grep
tail -20 logs/prod_bot.log
```

### 6. Запустить DEV бот (если нужен)

```bash
# Если DEV бот в отдельной директории
cd /root/atra-dev  # или другая директория

# Убедитесь, что ATRA_ENV=dev
grep "^ATRA_ENV" env

# Запустить DEV бот
nohup python3 main.py > logs/dev_bot.log 2>&1 &

# Подождать 3 секунды
sleep 3

# Проверить запуск
ps aux | grep "python.*main" | grep -v grep
tail -20 logs/dev_bot.log
```

## ✅ ПРОВЕРКА РАБОТЫ

### Проверить логи PROD бота

```bash
tail -f /root/atra/logs/prod_bot.log | grep -E "сигнал|SIGNAL|ATRA_ENV|TOKEN|started|запуск"
```

### Проверить, что используется правильный токен

```bash
cd /root/atra
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('env')

print('=== ПРОВЕРКА ===')
print(f'ATRA_ENV: {os.getenv(\"ATRA_ENV\")}')
from config import TOKEN, ATRA_ENV
print(f'TOKEN (первые 20 символов): {TOKEN[:20] if TOKEN else \"не установлен\"}...')
print(f'ATRA_ENV из config: {ATRA_ENV}')
"
```

### Проверить процессы

```bash
ps aux | grep "python.*main" | grep -v grep
```

## 🔍 ДИАГНОСТИКА ПРОБЛЕМ

### Если PROD бот не запускается

```bash
# Проверить ошибки в логах
tail -50 /root/atra/logs/prod_bot.log

# Проверить зависимости
cd /root/atra
python3 -c "import telegram; print('Telegram OK')"
```

### Если сигналы не приходят

```bash
# Проверить генерацию сигналов
tail -100 /root/atra/logs/prod_bot.log | grep -E "сигнал|SIGNAL|generate"

# Проверить отправку
tail -100 /root/atra/logs/prod_bot.log | grep -E "notify_user|send_message"
```

## 📝 ПОЛНЫЙ СКРИПТ ПЕРЕЗАПУСКА

```bash
#!/bin/bash
# Полный скрипт обновления и перезапуска

cd /root/atra

echo "🔄 Обновление кода..."
git pull origin main

echo "📋 Проверка конфигурации..."
grep "^ATRA_ENV" env
grep "^TELEGRAM_TOKEN" env | head -1

echo "🛑 Остановка ботов..."
pkill -f "python.*main"
sleep 5

echo "✅ Проверка остановки..."
ps aux | grep "python.*main" | grep -v grep || echo "Все процессы остановлены"

echo "🚀 Запуск PROD бота..."
nohup python3 main.py > logs/prod_bot.log 2>&1 &
sleep 3

echo "📊 Проверка запуска..."
ps aux | grep "python.*main" | grep -v grep
tail -20 logs/prod_bot.log

echo "✅ Готово!"
```

## ⚠️ ВАЖНО

- **PROD бот** должен иметь `ATRA_ENV=prod`
- **DEV бот** должен иметь `ATRA_ENV=dev`
- Если оба бота на одном сервере, используйте разные директории или разные `env` файлы

