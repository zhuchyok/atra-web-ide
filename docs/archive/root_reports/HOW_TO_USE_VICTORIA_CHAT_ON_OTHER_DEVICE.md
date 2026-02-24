# 🌐 КАК ИСПОЛЬЗОВАТЬ VICTORIA CHAT НА ДРУГОМ УСТРОЙСТВЕ

**Дата:** 2026-01-26  
**Проблема:** Скрипт не работает на другом устройстве

---

## 🎯 БЫСТРОЕ РЕШЕНИЕ

### Вариант 1: Standalone версия (рекомендуется)

```bash
# 1. Скачайте файл на другое устройство
# Скопируйте scripts/victoria_chat_standalone.py на другое устройство

# 2. Установите requests (если нет)
pip3 install requests
# или
pip install requests

# 3. Запустите
VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 victoria_chat_standalone.py
```

---

## 🔧 ДИАГНОСТИКА ПРОБЛЕМ

### Проблема 1: Скрипт ничего не выводит

**Причина:** Скрипт может падать молча из-за отсутствия зависимостей или проблем с путями.

**Решение:**

```bash
# Проверьте Python
python3 --version

# Проверьте requests
python3 -c "import requests; print('OK')"
# Если ошибка:
pip3 install requests

# Запустите с диагностикой
VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 -u scripts/victoria_chat.py 2>&1
```

---

### Проблема 2: Скрипт не находит проект

**Причина:** `find_project_root()` не работает на другом устройстве.

**Решение:** Используйте standalone версию:

```bash
# Standalone версия не требует проекта
VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 victoria_chat_standalone.py
```

---

### Проблема 3: Connection Error

**Причина:** Victoria недоступна через удаленный URL.

**Решение:**

```bash
# 1. Проверьте доступность сервера
ping 185.177.216.15

# 2. Проверьте порт
curl http://185.177.216.15:8010/health

# 3. Если не работает, проверьте SSH туннель на Mac Studio
# SSH туннель должен быть запущен на Mac Studio
```

---

## 📋 ПОШАГОВАЯ ИНСТРУКЦИЯ

### Шаг 1: Подготовка на другом устройстве

```bash
# 1. Установите Python 3.7+ (если нет)
python3 --version

# 2. Установите requests
pip3 install requests

# 3. Проверьте доступность Victoria
curl http://185.177.216.15:8010/health
# Должен вернуть: {"status":"online",...}
```

---

### Шаг 2: Получение скрипта

**Вариант A: Копирование файла**

```bash
# На Mac Studio
scp ~/Documents/atra-web-ide/scripts/victoria_chat_standalone.py user@other-device:~/victoria_chat.py

# На другом устройстве
chmod +x ~/victoria_chat.py
```

**Вариант B: Создание файла вручную**

Скопируйте содержимое `scripts/victoria_chat_standalone.py` в файл на другом устройстве.

---

### Шаг 3: Запуск

```bash
# Простой запуск
VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 victoria_chat.py

# С указанием проекта
VICTORIA_REMOTE_URL=http://185.177.216.15:8010 PROJECT_CONTEXT=atra python3 victoria_chat.py
```

---

## 🐛 УСТРАНЕНИЕ ПРОБЛЕМ

### Ошибка: "No module named 'requests'"

```bash
pip3 install requests
# или
pip install requests
```

---

### Ошибка: "Connection refused"

```bash
# Проверьте доступность
curl http://185.177.216.15:8010/health

# Если не работает:
# 1. Проверьте SSH туннель на Mac Studio
# 2. Проверьте firewall
# 3. Проверьте доступность сервера 185.177.216.15
```

---

### Ошибка: "Timeout"

```bash
# Увеличьте timeout в скрипте или проверьте сеть
ping 185.177.216.15
```

---

### Скрипт ничего не выводит

```bash
# Запустите с явным выводом
VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 -u victoria_chat.py 2>&1 | tee output.log

# Проверьте логи
cat output.log
```

---

## ✅ ПРОВЕРКА РАБОТОСПОСОБНОСТИ

### Тест 1: Проверка Victoria

```bash
curl http://185.177.216.15:8010/health
```

**Ожидаемый результат:**

```json
{ "status": "online", "agent": "Victoria", "knowledge_size": 150 }
```

---

### Тест 2: Простой запрос

```bash
curl -X POST http://185.177.216.15:8010/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "Привет", "project_context": "atra-web-ide"}'
```

**Ожидаемый результат:**

```json
{"status":"success","output":"Привет! Я Виктория...","knowledge":{...}}
```

---

### Тест 3: Запуск чата

```bash
VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 victoria_chat_standalone.py
```

**Ожидаемый вывод:**

```
============================================================
🤖 VICTORIA CHAT - Интерактивный чат с Victoria
============================================================

🔍 Поиск доступной Victoria...

🌐 Использование удаленной Victoria: http://185.177.216.15:8010
🔍 Проверяю http://185.177.216.15:8010/health... ✅
✅ Подключено к удаленной Victoria: http://185.177.216.15:8010

📁 Проект: atra-web-ide
🔑 Сессия: terminal_12345

💬 Введите ваше сообщение (или 'exit' для выхода):
💡 Команды: /status, /health, /project <name>, /help
------------------------------------------------------------

👤 Вы:
```

---

## 📝 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### Пример 1: Базовое использование

```bash
VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 victoria_chat_standalone.py
```

```
👤 Вы: Привет!
🤔 Victoria думает...
   (это может занять некоторое время...)

============================================================
🤖 Victoria:
============================================================
Привет! Я Виктория, Team Lead корпорации ATRA...
============================================================
```

---

### Пример 2: Смена проекта

```
👤 Вы: /project atra
📁 Проект изменен на: atra

👤 Вы: Покажи статус торговой системы
🤔 Victoria думает...
...
```

---

### Пример 3: Проверка статуса

```
👤 Вы: /status

📊 Статус Victoria: {
  "status": "ok",
  "agent": "Виктория",
  "knowledge_size": 150
}
```

---

## 🔗 АЛЬТЕРНАТИВНЫЕ СПОСОБЫ

### Вариант 1: Прямой curl

```bash
# Простой запрос
curl -X POST http://185.177.216.15:8010/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "Привет", "project_context": "atra-web-ide"}'
```

---

### Вариант 2: Python скрипт

```python
import requests

response = requests.post(
    "http://185.177.216.15:8010/run",
    json={
        "goal": "Привет!",
        "project_context": "atra-web-ide"
    }
)

print(response.json())
```

---

### Вариант 3: Node.js

```javascript
const fetch = require("node-fetch");

fetch("http://185.177.216.15:8010/run", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    goal: "Привет!",
    project_context: "atra-web-ide",
  }),
})
  .then((r) => r.json())
  .then(console.log);
```

---

## ✅ ИТОГ

**Для использования на другом устройстве:**

1. ✅ Используйте `victoria_chat_standalone.py` (не требует проекта)
2. ✅ Установите `requests`: `pip3 install requests`
3. ✅ Запустите: `VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 victoria_chat_standalone.py`

**Если не работает:**

- Проверьте доступность: `curl http://185.177.216.15:8010/health`
- Проверьте SSH туннель на Mac Studio
- Используйте прямой curl для тестирования

---

_Обновлено: 2026-01-26_
