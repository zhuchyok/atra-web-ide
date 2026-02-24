# 🌐 КАК ОБРАТИТЬСЯ К VICTORIA С ТЕРМИНАЛА С ЛЮБОЙ ТОЧКИ МИРА

**Дата:** 2026-01-26  
**Статус:** ✅ **Victoria доступна из любой точки мира!**

---

## 🎯 БЫСТРЫЙ СТАРТ

### Из любого терминала в мире:

```bash
# Проверка доступности
curl http://185.177.216.15:8010/health

# Отправка задачи Victoria
curl -X POST http://185.177.216.15:8010/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Привет! Расскажи о себе",
    "project_context": "atra-web-ide"
  }'
```

---

## 📊 URL ДЛЯ ДОСТУПА

### ✅ Victoria Agent (ОБЩИЙ для всех проектов):

**Порт:** `8010` (общий для всех проектов)  
**URL:** `http://185.177.216.15:8010`

**Важно:** Теперь Victoria один экземпляр для всех проектов!  
Контекст проекта передается через параметр `project_context` в запросе.

---

## 🔧 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### 1. Простой запрос (health check):

```bash
curl http://185.177.216.15:8010/health
```

**Ответ:**

```json
{
  "status": "online",
  "agent": "Victoria",
  "knowledge_size": 150
}
```

---

### 2. Отправка задачи (atra-web-ide):

```bash
curl -X POST http://185.177.216.15:8010/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Покажи список файлов проекта",
    "project_context": "atra-web-ide",
    "max_steps": 10
  }'
```

---

### 3. Отправка задачи (atra):

```bash
curl -X POST http://185.177.216.15:8010/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Проверь статус торговой системы",
    "project_context": "atra",
    "max_steps": 10
  }'
```

---

### 4. Отправка задачи (новый проект):

```bash
curl -X POST http://185.177.216.15:8010/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Создай новый компонент",
    "project_context": "new-project",
    "max_steps": 10
  }'
```

---

## 🐍 Python пример:

```python
import requests

# URL Victoria
VICTORIA_URL = "http://185.177.216.15:8010"

# Health check
response = requests.get(f"{VICTORIA_URL}/health")
print(response.json())

# Отправка задачи
task = {
    "goal": "Покажи список файлов проекта",
    "project_context": "atra-web-ide",
    "max_steps": 10
}

response = requests.post(
    f"{VICTORIA_URL}/run",
    json=task
)

result = response.json()
print(f"Статус: {result['status']}")
print(f"Результат: {result['output']}")
```

---

## 📝 Node.js пример:

```javascript
const fetch = require("node-fetch");

const VICTORIA_URL = "http://185.177.216.15:8010";

// Health check
async function checkHealth() {
  const response = await fetch(`${VICTORIA_URL}/health`);
  const data = await response.json();
  console.log("Health:", data);
}

// Отправка задачи
async function sendTask(goal, projectContext = "atra-web-ide") {
  const response = await fetch(`${VICTORIA_URL}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      goal,
      project_context: projectContext,
      max_steps: 10,
    }),
  });

  const result = await response.json();
  console.log("Результат:", result);
  return result;
}

// Использование
checkHealth();
sendTask("Покажи список файлов", "atra-web-ide");
```

---

## 🔄 С ИСТОРИЕЙ ЧАТА (новое):

```bash
curl -X POST http://185.177.216.15:8010/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Продолжи предыдущий разговор",
    "project_context": "atra-web-ide",
    "session_id": "session_123",
    "chat_history": [
      {"user": "Привет", "assistant": "Привет! Чем могу помочь?"},
      {"user": "Расскажи о проекте", "assistant": "Проект ATRA Web IDE..."}
    ],
    "max_steps": 10
  }'
```

---

## 🌍 ИЗ РАЗНЫХ СТРАН

### Из России:

```bash
curl http://185.177.216.15:8010/health
# ✅ Работает через SSH Reverse Tunnel
```

### Из США:

```bash
curl http://185.177.216.15:8010/health
# ✅ Работает через SSH Reverse Tunnel
```

### Из Европы:

```bash
curl http://185.177.216.15:8010/health
# ✅ Работает через SSH Reverse Tunnel
```

### Из Азии:

```bash
curl http://185.177.216.15:8010/health
# ✅ Работает через SSH Reverse Tunnel
```

**Важно:** Доступ работает из любой точки мира, где есть интернет!

---

## 🔐 БЕЗОПАСНОСТЬ

### Текущая конфигурация:

- ✅ SSH туннели используют ключи для аутентификации
- ✅ Доступ только через авторизованные SSH ключи
- ⚠️ Рекомендуется добавить API ключи для дополнительной защиты

### Рекомендация (будущее):

```bash
# Добавить API ключ в заголовки
curl -X POST http://185.177.216.15:8010/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{"goal": "...", "project_context": "atra-web-ide"}'
```

---

## 📊 ПАРАМЕТРЫ ЗАПРОСА

### TaskRequest:

```json
{
  "goal": "Текст задачи (обязательно)",
  "project_context": "atra-web-ide", // Опционально, по умолчанию "atra-web-ide"
  "max_steps": 30, // Опционально, по умолчанию 30
  "session_id": "session_123", // Опционально, для памяти чата
  "chat_history": [
    // Опционально, история чата
    { "user": "...", "assistant": "..." }
  ]
}
```

### TaskResponse:

```json
{
  "status": "success",
  "output": "Результат выполнения задачи",
  "knowledge": {
    "method": "enhanced",
    "metadata": {...},
    "project_context": "atra-web-ide"
  }
}
```

---

## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ

### 1. Порт изменился:

- ❌ Старый: `8020` (для atra-web-ide)
- ✅ Новый: `8010` (общий для всех проектов)

### 2. Контекст проекта:

- ✅ Передается через `project_context` в запросе
- ✅ По умолчанию: `"atra-web-ide"`
- ✅ Можно указать: `"atra"`, `"new-project"`, и т.д.

### 3. База знаний:

- ✅ Всегда доступна для всех проектов
- ✅ 58+ экспертов доступны всегда
- ✅ Глобальные знания доступны всегда

---

## 🔧 УСТРАНЕНИЕ ПРОБЛЕМ

### Проблема: Connection refused

```bash
# Проверьте, запущен ли туннель на Mac Studio
ssh user@mac-studio "ps aux | grep ssh.*8010"

# Перезапустите туннели
ssh user@mac-studio "bash ~/scripts/start_mac_studio_tunnels.sh"
```

### Проблема: Timeout

```bash
# Проверьте доступность сервера
ping 185.177.216.15

# Проверьте порт
telnet 185.177.216.15 8010
```

### Проблема: Victoria недоступна

```bash
# Проверьте локально на Mac Studio
curl http://localhost:8010/health

# Если локально работает, проблема в туннеле
# Перезапустите туннели
```

---

## 📋 ПОЛНЫЙ ПРИМЕР С ОБРАБОТКОЙ ОШИБОК

```bash
#!/bin/bash

VICTORIA_URL="http://185.177.216.15:8010"
PROJECT="atra-web-ide"
GOAL="Покажи список файлов проекта"

# Health check
echo "🔍 Проверка доступности Victoria..."
HEALTH=$(curl -s -w "\n%{http_code}" "$VICTORIA_URL/health")
HTTP_CODE=$(echo "$HEALTH" | tail -n1)
BODY=$(echo "$HEALTH" | head -n-1)

if [ "$HTTP_CODE" != "200" ]; then
  echo "❌ Victoria недоступна (HTTP $HTTP_CODE)"
  exit 1
fi

echo "✅ Victoria доступна: $BODY"

# Отправка задачи
echo "📤 Отправка задачи..."
RESPONSE=$(curl -s -X POST "$VICTORIA_URL/run" \
  -H "Content-Type: application/json" \
  -d "{
    \"goal\": \"$GOAL\",
    \"project_context\": \"$PROJECT\",
    \"max_steps\": 10
  }")

echo "📥 Ответ:"
echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
```

---

## ✅ ИТОГ

**Victoria доступна из любой точки мира через:**

```
http://185.177.216.15:8010
```

**Примеры использования:**

- ✅ `curl` из терминала
- ✅ Python `requests`
- ✅ Node.js `fetch`
- ✅ Любой HTTP клиент

**Важно:**

- Порт: `8010` (общий для всех проектов)
- Контекст проекта: через `project_context` в запросе
- База знаний: всегда доступна для всех проектов

**Готово к использованию!** 🎉

---

_Обновлено: 2026-01-26_
