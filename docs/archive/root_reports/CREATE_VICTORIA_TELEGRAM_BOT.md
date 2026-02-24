# 🤖 Создание отдельного Telegram бота для Victoria

**Дата:** 2026-01-27  
**Цель:** Создать нового бота специально для Victoria

---

## 📋 ШАГ 1: Создать нового бота через @BotFather

### 1.1. Откройте Telegram

- Откройте приложение Telegram

### 1.2. Найдите @BotFather

- В поиске Telegram найдите: **@BotFather**
- Откройте чат с ним

### 1.3. Создайте нового бота

**Отправьте команду:**

```
/newbot
```

**BotFather спросит имя бота:**

```
Alright, a new bot. How are we going to call it? Please choose a name for your bot.
```

**Напишите имя (например):**

```
Victoria ATRA Bot
```

**BotFather спросит username:**

```
Good. Now let's choose a username for your bot. It must end in `bot`. Like this, for example: TetrisBot or tetris_bot.
```

**Напишите username (должен заканчиваться на `bot`):**

```
victoria_atra_bot
```

или

```
victoria_atra_web_ide_bot
```

**BotFather пришлет токен:**

```
Done! Congratulations on your new bot. You will find it at t.me/victoria_atra_bot. Use this token to access the HTTP API:

8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU

Keep your token secure and store it safely, it can be used by anyone to control your bot.
```

**✅ СКОПИРУЙТЕ ТОКЕН!** (это длинная строка вида `8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU`)

---

## 📋 ШАГ 2: Настроить бота (опционально)

### 2.1. Установить описание бота

**Отправьте @BotFather:**

```
/setdescription
```

**Выберите вашего бота**, затем отправьте описание:

```
Victoria - Team Lead агент корпорации ATRA. Помогает с задачами разработки, планированием и координацией команды.
```

### 2.2. Установить команды бота

**Отправьте @BotFather:**

```
/setcommands
```

**Выберите вашего бота**, затем отправьте список команд:

```
start - Начать работу с Victoria
help - Показать справку
status - Статус Victoria
health - Проверка здоровья системы
```

---

## 📋 ШАГ 3: Добавить бота в группу Bikos_Corporation

### 3.1. Откройте группу Bikos_Corporation

- Найдите группу в Telegram
- Откройте её

### 3.2. Добавьте бота в группу

1. Нажмите на название группы (вверху)
2. Нажмите "Добавить участников" или "Add Members"
3. Найдите вашего нового бота (по username, например: `@victoria_atra_bot`)
4. Добавьте его в группу
5. Дайте боту права на чтение сообщений

---

## 📋 ШАГ 4: Узнать Chat ID группы

### 4.1. Добавьте бота @getidsbot в группу

- В группе Bikos_Corporation добавьте бота `@getidsbot`

### 4.2. Отправьте команду в группе

```
/start
```

### 4.3. Скопируйте Chat ID

Бот пришлет:

```
Chat ID: -1001234567890
```

**✅ СКОПИРУЙТЕ ЭТО ЧИСЛО!** (начинается с `-100`)

---

## 📋 ШАГ 5: Узнать ваш User ID

### 5.1. Найдите бота @userinfobot

- В поиске Telegram найдите: **@userinfobot**

### 5.2. Отправьте любое сообщение

- Отправьте: `/start` или любое сообщение

### 5.3. Скопируйте ваш ID

Бот пришлет ваш ID:

```
Your user ID: 556251171
```

**✅ СКОПИРУЙТЕ ЭТО ЧИСЛО!**

---

## 📋 ШАГ 6: Обновить .env файл

### 6.1. Откройте файл .env

- Путь: `/Users/bikos/Documents/atra-web-ide/.env`

### 6.2. Замените токен и ID

**Найдите эти строки:**

```env
TELEGRAM_BOT_TOKEN=8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU
TELEGRAM_USER_ID=556251171
```

**Замените на ваши новые значения:**

```env
TELEGRAM_BOT_TOKEN=ВАШ_НОВЫЙ_ТОКЕН_ОТ_BOTFATHER
TELEGRAM_USER_ID=ВАШ_USER_ID
TELEGRAM_CHAT_ID=ВАШ_CHAT_ID_ГРУППЫ
```

**Пример:**

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_USER_ID=556251171
TELEGRAM_CHAT_ID=-1001234567890
```

### 6.3. Сохраните файл

---

## 📋 ШАГ 7: Перезапустить бота

### 7.1. Остановите текущий бот

```bash
pkill -f victoria_telegram_bot
```

### 7.2. Запустите бот заново

```bash
cd /Users/bikos/Documents/atra-web-ide
python3 -m src.agents.bridge.victoria_telegram_bot
```

---

## ✅ ПРОВЕРКА

1. **Откройте группу Bikos_Corporation**
2. **Отправьте сообщение:**
   - `/start` — должно прийти приветствие
   - "Виктория, привет" — Victoria должна ответить

---

## 📝 ЧЕКЛИСТ

- [ ] Создан новый бот через @BotFather
- [ ] Скопирован токен бота
- [ ] Бот добавлен в группу Bikos_Corporation
- [ ] Узнан Chat ID группы (через @getidsbot)
- [ ] Узнан ваш User ID (через @userinfobot)
- [ ] Обновлен файл .env с новыми значениями
- [ ] Бот перезапущен
- [ ] Проверена работа в группе

---

## 💡 СОВЕТЫ

1. **Храните токен в безопасности** — не публикуйте его в открытом доступе
2. **Используйте отдельного бота** — так проще управлять и настраивать
3. **Проверьте права бота** — убедитесь, что бот может читать сообщения в группе

---

**Готово! Теперь у Victoria свой отдельный Telegram бот!** 🎉
