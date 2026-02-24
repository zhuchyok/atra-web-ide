# 📝 Шаблон для настройки Telegram бота Victoria

**После создания бота через @BotFather, заполните эти значения:**

---

## 🔑 ЗНАЧЕНИЯ ДЛЯ .env

Скопируйте эти строки и замените на ваши реальные значения:

```env
# Telegram Bot для Victoria (НОВЫЙ БОТ)
TELEGRAM_BOT_TOKEN=ЗАМЕНИТЕ_НА_ТОКЕН_ОТ_BOTFATHER
TELEGRAM_USER_ID=ЗАМЕНИТЕ_НА_ВАШ_USER_ID
TELEGRAM_CHAT_ID=ЗАМЕНИТЕ_НА_CHAT_ID_ГРУППЫ
```

---

## 📋 ГДЕ ВЗЯТЬ ЗНАЧЕНИЯ

### 1. TELEGRAM_BOT_TOKEN

- Получите у @BotFather после создания бота
- Формат: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

### 2. TELEGRAM_USER_ID

- Узнайте у @userinfobot в Telegram
- Отправьте `/start` боту
- Формат: `556251171` (положительное число)

### 3. TELEGRAM_CHAT_ID

- Узнайте через @getidsbot в группе Bikos_Corporation
- Отправьте `/start` в группе
- Формат: `-1001234567890` (отрицательное число, начинается с `-100`)

---

## ✅ ПРИМЕР ЗАПОЛНЕННОГО .env

```env
# Telegram Bot для Victoria
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_USER_ID=556251171
TELEGRAM_CHAT_ID=-1001234567890
```

---

## 🚀 ПОСЛЕ ЗАПОЛНЕНИЯ

1. Сохраните файл .env
2. Перезапустите бота:
   ```bash
   pkill -f victoria_telegram_bot
   cd /Users/bikos/Documents/atra-web-ide
   python3 -m src.agents.bridge.victoria_telegram_bot
   ```
3. Проверьте в группе Bikos_Corporation
