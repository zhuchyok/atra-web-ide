# 🤖 Подключение Telegram к Victoria - Инструкция

**Дата:** 2026-01-27  
**Цель:** Подключить Telegram бот к Victoria (как в Clawdbot)

---

## 📋 ЧТО НУЖНО

1. **Telegram Bot Token** - токен бота от @BotFather
2. **Ваш Telegram User ID** - ваш ID в Telegram

---

## 🔑 ШАГ 1: Получить Telegram Bot Token

1. Откройте Telegram
2. Найдите бота **@BotFather**
3. Отправьте команду: `/newbot`
4. Следуйте инструкциям:
   - Придумайте имя бота (например: "Victoria ATRA Bot")
   - Придумайте username бота (должен заканчиваться на `bot`, например: `victoria_atra_bot`)
5. BotFather пришлет вам токен вида: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
6. **Скопируйте токен!**

---

## 👤 ШАГ 2: Узнать свой Telegram User ID

### Вариант 1: Через @userinfobot

1. Откройте Telegram
2. Найдите бота **@userinfobot**
3. Отправьте любое сообщение
4. Бот пришлет ваш ID (например: `556251171`)

### Вариант 2: Через @getidsbot

1. Откройте Telegram
2. Найдите бота **@getidsbot**
3. Отправьте любое сообщение
4. Бот пришлет ваш ID

---

## ⚙️ ШАГ 3: Настроить переменные окружения

Добавьте в файл `.env`:

```env
# Telegram Bot для Victoria
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_USER_ID=your_user_id_here
```

**Пример:**

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_USER_ID=556251171
```

---

## 🚀 ШАГ 4: Запустить Telegram бот

### Вариант 1: Локально (для тестирования)

```bash
cd /Users/bikos/Documents/atra-web-ide
python3 -m src.agents.bridge.victoria_telegram_bot
```

### Вариант 2: В Docker (через docker-compose)

Добавьте в `knowledge_os/docker-compose.yml`:

```yaml
victoria-telegram-bot:
  build:
    context: ..
    dockerfile: infrastructure/docker/agents/Dockerfile
  container_name: victoria-telegram-bot
  restart: always
  networks:
    - atra-network
  environment:
    PYTHONPATH: /app
    TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
    TELEGRAM_USER_ID: ${TELEGRAM_USER_ID}
    VICTORIA_URL: http://victoria-agent:8000
  command: python -m src.agents.bridge.victoria_telegram_bot
```

Затем:

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-telegram-bot
```

---

## 📱 ШАГ 5: Использование

### Команды бота:

- `/start` или `/help` - показать справку
- `/status` - статус Victoria
- `/health` - проверка здоровья системы

### Обычные сообщения:

Просто напишите задачу, и Victoria её выполнит!

**Примеры:**

- "Создай файл test.py"
- "Покажи список файлов"
- "Виктория, помоги с кодом"
- "Проверь статус проекта"

---

## ✅ ПРОВЕРКА

1. **Проверьте, что бот запущен:**

   ```bash
   # Локально
   ps aux | grep victoria_telegram_bot

   # В Docker
   docker ps | grep victoria-telegram-bot
   ```

2. **Проверьте логи:**

   ```bash
   # Локально - логи в консоли

   # В Docker
   docker logs victoria-telegram-bot
   ```

3. **Отправьте сообщение боту в Telegram:**
   - Найдите вашего бота в Telegram
   - Отправьте `/start`
   - Должно прийти приветственное сообщение

---

## 🔧 УСТРАНЕНИЕ ПРОБЛЕМ

### Проблема 1: "TELEGRAM_BOT_TOKEN не установлен"

**Решение:** Проверьте, что токен добавлен в `.env` и файл загружен

### Проблема 2: "TELEGRAM_USER_ID не установлен"

**Решение:** Проверьте, что ваш ID добавлен в `.env`

### Проблема 3: Бот не отвечает

**Решение:**

- Проверьте, что бот запущен
- Проверьте логи на ошибки
- Убедитесь, что Victoria доступна по адресу `VICTORIA_URL`

### Проблема 4: "Доступ запрещен"

**Решение:** Убедитесь, что `TELEGRAM_USER_ID` соответствует вашему реальному ID

---

## 📝 ПРИМЕР .env

```env
# Telegram Bot для Victoria
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_USER_ID=556251171

# Victoria URL (для Docker используйте victoria-agent:8000)
VICTORIA_URL=http://localhost:8010
```

---

## 🎉 ГОТОВО!

После настройки вы сможете общаться с Victoria через Telegram, как в Clawdbot!

**Файлы:**

- `src/agents/bridge/victoria_telegram_bot.py` - основной код бота
- `.env` - конфигурация (добавьте токен и ID)
