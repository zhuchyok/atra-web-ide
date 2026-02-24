# 🚀 РАЗВЕРТЫВАНИЕ ATRA НА СЕРВЕРЕ

## 📋 Быстрый старт

### 1. Клонирование и настройка

```bash
# Клонируйте репозиторий
git clone <your-repo-url>
cd atra

# Запустите автоматическую настройку
python3 setup_server.py
```

### 2. Настройка конфигурации

```bash
# Отредактируйте файл .env
nano .env

# Добавьте ваш Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 3. Запуск бота

```bash
# Запустите основное приложение
python3 main.py

# Или запустите в фоне
nohup python3 main.py > bot.log 2>&1 &
```

## 🔧 Ручная настройка базы данных

### Автоматическая инициализация (рекомендуется)

```bash
# Полная инициализация с данными
python3 db_init.py

# Только структура без данных
python3 db_init.py --structure-only
```

### Инициализация через оригинальный скрипт

```bash
python3 init_db.py
```

## 📁 Структура проекта

```
atra/
├── main.py              # Главный файл запуска
├── setup_server.py      # Скрипт настройки сервера
├── db_init.py           # Улучшенная инициализация БД
├── init_db.py           # Оригинальная инициализация БД
├── db.py                # Работа с базой данных
├── config.py            # Конфигурация
├── .env                 # Секретные переменные
├── trading.db           # База данных SQLite
├── user_data.json       # Данные пользователей (создается автоматически)
├── backups/             # Резервные копии БД
├── logs/                # Логи приложения
└── locales/             # Файлы локализации
```

## 🗄️ База данных

### Автоматическое создание

База данных автоматически создается при первом запуске с:

- ✅ Проверкой целостности
- ✅ Созданием всех необходимых таблиц
- ✅ Загрузкой торговых пар с бирж
- ✅ Настройкой комиссий

### Ручное управление

```bash
# Проверка целостности
sqlite3 trading.db "PRAGMA integrity_check;"

# Просмотр таблиц
sqlite3 trading.db ".tables"

# Создание бэкапа
cp trading.db backups/trading_backup_$(date +%Y%m%d_%H%M%S).db
```

## 🔍 Диагностика проблем

### Проверка логов

```bash
# Основные логи
tail -f system_improved.log

# Логи бота
tail -f bot.log

# Логи системы
journalctl -u atra-bot -f
```

### Проверка состояния

```bash
# Проверка здоровья системы
python3 main.py health

# Проверка базы данных
python3 -c "from db import Database; db = Database(); print('DB OK' if db.is_connected() else 'DB ERROR')"

# Проверка файла user_data.json
python3 -c "import json, os; print('user_data.json OK' if os.path.exists('user_data.json') and json.load(open('user_data.json')) else 'user_data.json ERROR')"
```

### Восстановление базы данных

```bash
# Автоматическое восстановление
python3 db_init.py

# Ручное восстановление из бэкапа
cp backups/trading.db_YYYYMMDD_HHMMSS trading.db
```

## 🛡️ Безопасность

### Переменные окружения

- `TELEGRAM_BOT_TOKEN` - токен бота (обязательно)
- `ATRA_ENV` - режим работы (dev/prod)
- `BINANCE_API_KEY` - API ключ Binance (опционально)
- `BINANCE_SECRET_KEY` - секретный ключ Binance (опционально)

### Права доступа

```bash
# Установите правильные права
chmod 600 .env
chmod 644 trading.db
chmod 755 *.py
```

## 🔄 Обновление

### Обновление кода

```bash
# Создайте бэкап
cp trading.db backups/trading_backup_$(date +%Y%m%d_%H%M%S).db

# Обновите код
git pull origin main

# Перезапустите бота
pkill -f "python3 main.py"
python3 main.py
```

### Миграция базы данных

```bash
# Запустите миграцию
python3 migrate_db.py
```

## 📊 Мониторинг

### Автоматические проверки

- ✅ Целостность базы данных при запуске
- ✅ Наличие всех необходимых таблиц
- ✅ Проверка зависимостей
- ✅ Автоматические бэкапы

### Ручной мониторинг

```bash
# Проверка статуса
ps aux | grep "python3 main.py"

# Проверка использования памяти
ps -o pid,ppid,cmd,%mem,%cpu --sort=-%mem | grep python3

# Проверка дискового пространства
df -h
```

## 🆘 Поддержка

### Частые проблемы

1. **Ошибка "database disk image is malformed"**

   ```bash
   python3 db_init.py
   ```

2. **Отсутствует Telegram Bot Token**

   ```bash
   nano .env
   # Добавьте: TELEGRAM_BOT_TOKEN=your_token
   ```

3. **Ошибки импорта модулей**

   ```bash
   pip install -r requirements.txt
   ```

4. **Проблемы с правами доступа**

   ```bash
   chmod +x *.py
   chmod 600 .env
   ```

5. **Отсутствует файл user_data.json**

   ```bash
   # Создание файла user_data.json
   python3 create_user_data.py

   # Или через систему инициализации
   python3 db_init.py --structure-only
   ```

### Контакты

- 📧 Email: support@atra-bot.com
- 💬 Telegram: @atra_support
- 🐛 Issues: GitHub Issues

---

**🎉 Готово! Ваш торговый бот ATRA готов к работе на сервере!**
