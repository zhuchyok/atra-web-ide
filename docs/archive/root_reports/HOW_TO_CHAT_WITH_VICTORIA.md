# 💬 Как общаться с Victoria через Telegram

**Дата:** 2026-01-27  
**Бот:** @vikoria_atra_bot

---

## ✅ ТЕКУЩИЙ СТАТУС

- ✅ Бот создан и настроен
- ✅ Токен добавлен в .env
- ✅ Бот готов к работе

---

## 🚀 ЗАПУСК БОТА

### Вариант 1: Локальный запуск (для тестирования)

```bash
cd /Users/bikos/Documents/atra-web-ide
python3 -m src.agents.bridge.victoria_telegram_bot
```

Бот будет работать пока вы не закроете терминал (Ctrl+C).

### Вариант 2: Запуск в фоне

```bash
cd /Users/bikos/Documents/atra-web-ide
nohup python3 -m src.agents.bridge.victoria_telegram_bot > victoria_bot.log 2>&1 &
```

Бот будет работать в фоне, логи в `victoria_bot.log`.

---

## 💬 КАК ОБЩАТЬСЯ

### В личных сообщениях (Private Chat)

1. **Найдите бота в Telegram:**
   - Откройте Telegram
   - Найдите: `@vikoria_atra_bot`
   - Или перейдите: https://t.me/vikoria_atra_bot

2. **Начните диалог:**
   - Нажмите "Start" или отправьте `/start`
   - Бот приветствует вас

3. **Отправьте сообщение:**
   - Просто напишите Victoria как обычному контакту
   - Например: "Виктория, привет! Как дела?"
   - Victoria ответит через несколько секунд

### В группе Bikos_Corporation

**⚠️ ВАЖНО:** Сначала нужно добавить бота в группу и узнать Chat ID!

1. **Добавьте бота в группу:**
   - Откройте группу Bikos_Corporation
   - Добавьте участника: `@vikoria_atra_bot`
   - Дайте боту права на чтение сообщений

2. **Узнайте Chat ID группы:**
   - Добавьте в группу бота `@getidsbot`
   - Отправьте `/start` в группе
   - Скопируйте Chat ID (начинается с `-100`)

3. **Обновите .env:**

   ```env
   TELEGRAM_CHAT_ID=-1001234567890
   ```

   (замените на ваш реальный Chat ID)

4. **Перезапустите бота:**

   ```bash
   pkill -f victoria_telegram_bot
   python3 -m src.agents.bridge.victoria_telegram_bot
   ```

5. **Общайтесь в группе:**
   - Просто упомяните Victoria или напишите сообщение
   - Victoria будет отвечать в группе

---

## 📋 ДОСТУПНЫЕ КОМАНДЫ

- `/start` - Начать работу с Victoria
- `/help` - Показать справку
- `/status` - Статус Victoria
- `/health` - Проверка здоровья системы

---

## 🔍 ПРОВЕРКА РАБОТЫ

### 1. Проверьте, что бот запущен:

```bash
ps aux | grep victoria_telegram_bot | grep -v grep
```

### 2. Проверьте логи (если запущен в фоне):

```bash
tail -f victoria_bot.log
```

### 3. Проверьте Victoria API:

```bash
curl http://localhost:8010/health
```

### 4. Отправьте тестовое сообщение:

- В Telegram напишите боту: "Привет, Victoria!"
- Должен прийти ответ

---

## ⚠️ ВОЗМОЖНЫЕ ПРОБЛЕМЫ

### Бот не отвечает

1. **Проверьте, что бот запущен:**

   ```bash
   ps aux | grep victoria_telegram_bot
   ```

2. **Проверьте, что Victoria работает:**

   ```bash
   curl http://localhost:8010/health
   ```

3. **Проверьте логи:**
   ```bash
   tail -f victoria_bot.log
   ```

### "Victoria недоступна"

- Victoria сервер не запущен или недоступен
- Проверьте: `curl http://localhost:8010/health`
- Запустите Victoria через Docker:
  ```bash
  docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent
  ```

### Бот не видит сообщения в группе

- Убедитесь, что `TELEGRAM_CHAT_ID` установлен в .env
- Убедитесь, что бот добавлен в группу
- Перезапустите бота после изменения .env

---

## 🎯 БЫСТРЫЙ СТАРТ

```bash
# 1. Перейдите в проект
cd /Users/bikos/Documents/atra-web-ide

# 2. Убедитесь, что Victoria работает
curl http://localhost:8010/health

# 3. Запустите бота
python3 -m src.agents.bridge.victoria_telegram_bot

# 4. Откройте Telegram и найдите @vikoria_atra_bot
# 5. Отправьте /start
# 6. Начните общаться!
```

---

**Готово! Теперь вы можете общаться с Victoria через Telegram!** 🎉
