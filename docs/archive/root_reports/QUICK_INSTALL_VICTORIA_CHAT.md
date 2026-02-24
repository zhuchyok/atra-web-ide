# 🚀 БЫСТРАЯ УСТАНОВКА VICTORIA CHAT

**Проблема:** curl не может записать файл (директория не существует)

---

## ✅ РЕШЕНИЕ

### Вариант 1: Создать директорию сначала

```bash
# Создать директорию
mkdir -p ~/.local/bin

# Затем загрузить (если есть URL)
curl -sSL https://raw.githubusercontent.com/.../victoria_chat_standalone.py -o ~/.local/bin/victoria_chat

# Или скопировать локально
cp ~/Documents/atra-web-ide/scripts/victoria_chat_standalone.py ~/.local/bin/victoria_chat

# Сделать исполняемым
chmod +x ~/.local/bin/victoria_chat

# Запустить
~/.local/bin/victoria_chat
```

---

### Вариант 2: Использовать локальный файл (РЕКОМЕНДУЕТСЯ)

```bash
# Просто скопируйте файл
cp ~/Documents/atra-web-ide/scripts/victoria_chat_standalone.py ~/victoria_chat

# Сделать исполняемым
chmod +x ~/victoria_chat

# Запустить
VICTORIA_REMOTE_URL=http://185.177.216.15:8010 ~/victoria_chat
```

---

### Вариант 3: Запустить напрямую из проекта

```bash
# Если вы на Mac Studio, просто запустите из проекта
cd ~/Documents/atra-web-ide
VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 scripts/victoria_chat_standalone.py
```

---

### Вариант 4: Одна команда (создает директорию)

```bash
mkdir -p ~/.local/bin && cp ~/Documents/atra-web-ide/scripts/victoria_chat_standalone.py ~/.local/bin/victoria_chat && chmod +x ~/.local/bin/victoria_chat && ~/.local/bin/victoria_chat
```

---

## 🔧 ДЛЯ ДРУГОГО УСТРОЙСТВА

### Шаг 1: Скопируйте файл

```bash
# На Mac Studio
scp ~/Documents/atra-web-ide/scripts/victoria_chat_standalone.py user@other-device:~/victoria_chat

# На другом устройстве
chmod +x ~/victoria_chat
```

### Шаг 2: Запустите

```bash
VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 ~/victoria_chat
```

---

## ✅ ПРОВЕРКА

```bash
# Проверьте, что файл скопирован
ls -lh ~/.local/bin/victoria_chat
# или
ls -lh ~/victoria_chat

# Проверьте права
chmod +x ~/.local/bin/victoria_chat  # если нужно

# Запустите
~/.local/bin/victoria_chat
```

---

## 💡 САМЫЙ ПРОСТОЙ СПОСОБ

```bash
# Просто запустите из проекта (если на Mac Studio)
cd ~/Documents/atra-web-ide
python3 scripts/victoria_chat_standalone.py
```

Скрипт автоматически:

- ✅ Установит requests если нужно
- ✅ Найдет доступную Victoria
- ✅ Начнет чат

---

_Обновлено: 2026-01-26_
