# Исправление проблем с Telegram ботом

## 🎯 Проблема

Команды Telegram бота не отвечают на сервере.

## 🚀 Быстрое решение

### 1. Запустите диагностику на сервере:

```bash
# Перейдите в директорию проекта
cd /root/atra

# Запустите диагностику
python debug_telegram_bot.py
```

### 2. Запустите автоматическое исправление:

```bash
# Запустите скрипт исправления
./fix_telegram_bot.sh
```

### 3. Если автоматическое исправление не работает, выполните вручную:

```bash
# Проверьте статус сервиса
sudo systemctl status myproject.service

# Перезапустите сервис
sudo systemctl restart myproject.service

# Проверьте логи
journalctl -u myproject.service -f
```

## 🔍 Диагностика проблем

### Проверьте статус сервиса:

```bash
sudo systemctl status myproject.service
```

**Ожидаемый результат:**

```
● myproject.service - Trading bot
   Active: active (running)
```

### Проверьте логи:

```bash
journalctl -u myproject.service -n 20
```

**Ищите ошибки:**

- `❌ Ошибка подключения к Telegram API`
- `❌ Ошибка токена бота`
- `❌ Ошибка webhook`
- `❌ Ошибка обработчиков`

### Проверьте конфигурацию:

```bash
# Проверьте токен бота
grep -i "token" config.py

# Проверьте настройки
cat config.py | grep -i "telegram"
```

## 🛠️ Частые проблемы и решения

### 1. Сервис не запускается

**Проблема:** `systemctl status myproject.service` показывает `inactive`

**Решение:**

```bash
# Запустите сервис
sudo systemctl start myproject.service

# Проверьте статус
sudo systemctl status myproject.service
```

### 2. Ошибка токена бота

**Проблема:** `❌ Ошибка токена бота`

**Решение:**

```bash
# Проверьте токен в config.py
grep -i "token" config.py

# Если токен неправильный, обновите его
nano config.py
```

### 3. Ошибка webhook

**Проблема:** `❌ Ошибка webhook`

**Решение:**

```bash
# Очистите webhook
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/deleteWebhook"

# Перезапустите сервис
sudo systemctl restart myproject.service
```

### 4. Ошибка обработчиков

**Проблема:** `❌ Ошибка обработчиков`

**Решение:**

```bash
# Проверьте файлы
ls -la telegram_handlers.py telegram_commands.py

# Проверьте синтаксис
python -m py_compile telegram_handlers.py
python -m py_compile telegram_commands.py
```

## 📊 Проверка работы

### 1. Проверьте, что бот отвечает:

Отправьте команду `/start` боту в Telegram.

**Ожидаемый результат:**

- Бот должен ответить приветственным сообщением
- Должны появиться кнопки меню

### 2. Проверьте логи:

```bash
journalctl -u myproject.service -f
```

**Ищите сообщения:**

- `✅ Бот запущен`
- `✅ Обработчики зарегистрированы`
- `✅ Команды зарегистрированы`

### 3. Проверьте команды:

Попробуйте команды:

- `/start` - запуск бота
- `/help` - помощь
- `/status` - статус системы
- `/balance` - баланс

## 🚨 Критические ошибки

### Если бот полностью не отвечает:

1. **Проверьте токен:**

   ```bash
   python -c "import requests; print(requests.get('https://api.telegram.org/bot<YOUR_TOKEN>/getMe').json())"
   ```

2. **Проверьте интернет:**

   ```bash
   ping api.telegram.org
   ```

3. **Проверьте порты:**
   ```bash
   netstat -tlnp | grep python
   ```

### Если сервис не запускается:

1. **Проверьте логи:**

   ```bash
   journalctl -u myproject.service -n 50
   ```

2. **Проверьте зависимости:**

   ```bash
   source .venv/bin/activate
   pip list | grep -i telegram
   ```

3. **Проверьте права:**
   ```bash
   ls -la main.py
   sudo chown root:root main.py
   ```

## 📅 Дата создания

6 октября 2025

## ✅ Статус

- ✅ Диагностический скрипт создан
- ✅ Скрипт исправления создан
- ✅ Инструкции созданы
- ⏳ Требуется тестирование на сервере
