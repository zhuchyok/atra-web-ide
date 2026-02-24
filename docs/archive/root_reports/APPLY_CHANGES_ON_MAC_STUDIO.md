# 🔄 Применение изменений на Mac Studio

**Дата:** 2026-01-25  
**Статус:** Требуется применение изменений из этого чата

---

## 📋 Изменения, которые нужно применить

### 1. ✅ `src/agents/bridge/victoria_mcp_server.py`

- **Изменение:** Автоматическое определение URL Victoria
- **Статус:** ✅ Уже применено локально
- **Что сделать:** Скопировать файл на Mac Studio

### 2. ✅ `knowledge_os/app/victoria_enhanced.py`

- **Изменение:** Инициализация observability с безопасной проверкой
- **Статус:** ✅ Уже применено локально
- **Что сделать:** Скопировать файл на Mac Studio

### 3. ✅ `backend/app/routers/chat.py`

- **Изменение:** Принудительное использование Victoria Enhanced
- **Статус:** ✅ Применено локально
- **Что сделать:** Применить на Mac Studio (строки 254-255)

---

## 🔧 Инструкция для применения на Mac Studio

### Вариант 1: Через Cursor на Mac Studio (рекомендуется)

1. **Откройте проект на Mac Studio:**

   ```bash
   cd ~/Documents/atra-web-ide
   ```

2. **Примените изменения в `backend/app/routers/chat.py`:**

   Найдите строки 254-255:

   ```python
   # Умный роутинг: простые сообщения -> Ollama, сложные -> Victoria
   use_ollama_direct = is_simple_message(message.content) or not message.use_victoria
   ```

   Замените на:

   ```python
   # Victoria Enhanced: всегда используем Victoria Enhanced, если use_victoria=True
   use_ollama_direct = not message.use_victoria
   ```

3. **Скопируйте обновленные файлы:**

   ```bash
   # Файлы уже обновлены локально, просто проверьте что они на Mac Studio
   # Если нужно, скопируйте с Mac Studio:
   # scp src/agents/bridge/victoria_mcp_server.py zhuchyok@192.168.1.43:~/Documents/atra-web-ide/src/agents/bridge/
   # scp knowledge_os/app/victoria_enhanced.py zhuchyok@192.168.1.43:~/Documents/atra-web-ide/knowledge_os/app/
   ```

4. **Перезапустите сервисы:**

   ```bash
   # Victoria контейнер
   docker restart victoria-agent

   # MCP сервер (если запущен)
   pkill -f "victoria_mcp_server"
   export PYTHONPATH=~/Documents/atra-web-ide:$PYTHONPATH
   nohup python3 -m src.agents.bridge.victoria_mcp_server > /tmp/victoria_mcp.log 2>&1 &
   ```

---

## ✅ Проверка после применения

```bash
# Victoria
curl http://localhost:8010/health

# MCP сервер
curl http://localhost:8012/sse

# Статус контейнеров
docker ps | grep victoria
```

---

## 📝 Что изменилось

1. **Victoria MCP Server** - автоматически определяет URL Victoria (localhost:8010 или Mac Studio)
2. **Victoria Enhanced** - безопасная инициализация observability
3. **Chat Router** - принудительное использование Victoria Enhanced для всех сообщений

---

## 🎯 Результат

После применения всех изменений:

- ✅ Все сообщения в чате на `localhost:3000` будут обрабатываться через Victoria Enhanced
- ✅ Victoria Enhanced автоматически выберет оптимальный метод (ReAct, Extended Thinking, Swarm и т.д.)
- ✅ Veronica Enhanced доступна через выбор эксперта "Veronica"
