# Диагностика проблем Telegram бота на сервере

## 🎯 Проблема

На сервере сигналы приходят, но кнопки не нажимаются и команды не реагируют.

## 🔍 Диагностика

### 1. Запустите тест на сервере:

```bash
# Перейдите в директорию проекта
cd /root/atra

# Запустите тест
python3 test_server_telegram.py
```

### 2. Проверьте статус сервиса:

```bash
# Проверьте статус
sudo systemctl status myproject.service

# Проверьте логи
journalctl -u myproject.service -f
```

### 3. Проверьте конфигурацию:

```bash
# Проверьте токен
grep -i "token" config.py

# Проверьте .env файл
cat .env
```

## 🚨 Частые проблемы на сервере

### 1. Сервис не запускается

**Симптомы:**

- `systemctl status myproject.service` показывает `inactive`
- Логи показывают ошибки запуска

**Решение:**

```bash
# Запустите сервис
sudo systemctl start myproject.service

# Проверьте статус
sudo systemctl status myproject.service
```

### 2. Ошибка токена бота

**Симптомы:**

- `❌ Ошибка токена бота`
- `❌ HTTP ошибка: 401`

**Решение:**

```bash
# Проверьте токен в .env
cat .env | grep TELEGRAM_TOKEN

# Обновите токен если нужно
nano .env
```

### 3. Ошибка webhook

**Симптомы:**

- `❌ Ошибка webhook`
- `❌ Описание ошибки: ...`

**Решение:**

```bash
# Очистите webhook
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/deleteWebhook"

# Перезапустите сервис
sudo systemctl restart myproject.service
```

### 4. Ошибка обработчиков

**Симптомы:**

- `❌ Ошибка обработчиков`
- `❌ Ошибка импорта telegram_handlers`

**Решение:**

```bash
# Проверьте файлы
ls -la telegram_handlers.py telegram_commands.py

# Проверьте синтаксис
python3 -m py_compile telegram_handlers.py
python3 -m py_compile telegram_commands.py
```

### 5. Ошибка callback кнопок

**Симптомы:**

- Кнопки не нажимаются
- `❌ Callback функции не найдены`

**Решение:**

```bash
# Проверьте функции в telegram_handlers.py
grep -n "def button" telegram_handlers.py
grep -n "def handle_close_button" telegram_handlers.py
grep -n "def handle_accept_button" telegram_handlers.py
```

## 🔧 Автоматическое исправление

### Запустите скрипт исправления:

```bash
# Запустите автоматическое исправление
./fix_telegram_bot.sh
```

### Если скрипт не работает, выполните вручную:

```bash
# 1. Остановите сервис
sudo systemctl stop myproject.service

# 2. Проверьте конфигурацию
python3 -c "from config import TOKEN; print('Token:', TOKEN[:10] + '...' if TOKEN else 'None')"

# 3. Проверьте обработчики
python3 -c "import telegram_handlers; print('Handlers OK')"

# 4. Запустите сервис
sudo systemctl start myproject.service

# 5. Проверьте статус
sudo systemctl status myproject.service
```

## 📊 Сравнение с локальной средой

### Локальная среда (работает):

- ✅ main.py запущен
- ✅ Бот подключен
- ✅ Команды зарегистрированы (24 шт.)
- ✅ Обработчики работают
- ✅ Callback функции работают

### Серверная среда (проблемы):

- ❌ Требуется диагностика
- ❌ Кнопки не нажимаются
- ❌ Команды не реагируют

## 🚀 Пошаговое исправление

### Шаг 1: Диагностика

```bash
cd /root/atra
python3 test_server_telegram.py
```

### Шаг 2: Проверка сервиса

```bash
sudo systemctl status myproject.service
journalctl -u myproject.service -n 20
```

### Шаг 3: Проверка конфигурации

```bash
# Проверьте токен
python3 -c "from config import TOKEN; print('Token:', TOKEN[:10] + '...' if TOKEN else 'None')"

# Проверьте .env
cat .env
```

### Шаг 4: Перезапуск

```bash
sudo systemctl restart myproject.service
sleep 10
sudo systemctl status myproject.service
```

### Шаг 5: Тестирование

```bash
# Отправьте команду /start боту
# Проверьте, что бот отвечает
# Попробуйте нажать кнопки
```

## 📋 Чек-лист для сервера

- [ ] Сервис активен (`systemctl is-active myproject.service`)
- [ ] Нет ошибок в логах (`journalctl -u myproject.service`)
- [ ] Токен бота валиден
- [ ] Команды зарегистрированы
- [ ] Webhook работает
- [ ] Обработчики импортируются
- [ ] Callback функции найдены
- [ ] Бот отвечает на команды
- [ ] Кнопки нажимаются

## 📅 Дата создания

6 октября 2025

## ✅ Статус

- ✅ Локальная среда работает корректно
- ✅ Диагностические скрипты созданы
- ✅ Инструкции созданы
- ⏳ Требуется тестирование на сервере
