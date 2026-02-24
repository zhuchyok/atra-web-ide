# Интеграция Knowledge OS Database в чат

**Дата:** 26.01.2026  
**Изменение:** Чат теперь использует Knowledge OS Database (аналог Clawdbot) напрямую

---

## ✅ Что изменилось

### Подключение через Knowledge OS Database

**Раньше:**

- Чат → Victoria HTTP API → Victoria Agent → Knowledge OS Database

**Теперь:**

- Чат → Knowledge OS Client (прямое подключение) ✅
- Чат → Victoria HTTP API → Victoria Agent → Knowledge OS Database (через connection pool)

---

## 🔧 Как это работает

### 1. Connection Pool

В `backend/app/main.py` создается connection pool при старте:

```python
pool = await asyncpg.create_pool(
    settings.database_url,  # postgresql://admin:secret@localhost:5432/knowledge_os
    min_size=settings.database_pool_min_size,  # 2
    max_size=settings.database_pool_max_size,  # 10
)
app.state.knowledge_os_pool = pool
```

### 2. Knowledge OS Client

`backend/app/services/knowledge_os.py` использует этот pool:

```python
class KnowledgeOSClient:
    async def get_expert_by_name(self, name: str):
        # Прямой запрос к PostgreSQL через connection pool
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM experts WHERE name ILIKE $1", ...)
```

### 3. Интеграция в чат

В `backend/app/routers/chat.py`:

```python
async def sse_generator(
    message: ChatMessage,
    victoria: VictoriaClient,
    mlx: MLXClient,
    knowledge_os: KnowledgeOSClient  # ✅ Добавлен
):
    # Проверяем эксперта в Knowledge OS перед отправкой в Victoria
    if message.expert_name:
        expert_data = await knowledge_os.get_expert_by_name(message.expert_name)
        if expert_data:
            logger.info(f"✅ Эксперт найден в Knowledge OS: {expert_data.get('role')}")
```

---

## 🎯 Преимущества

1. **Прямой доступ к базе:**
   - Не нужно ждать Victoria Agent
   - Быстрая проверка экспертов
   - Прямые SQL запросы

2. **Connection Pool:**
   - Переиспользование соединений
   - Эффективное использование ресурсов
   - Автоматическое управление соединениями

3. **Надежность:**
   - Если Victoria недоступна, можем использовать Knowledge OS напрямую
   - Fallback на MLX если и Victoria, и Knowledge OS недоступны

---

## 📊 Структура Knowledge OS Database

### Таблицы:

- `experts` - 58+ экспертов
- `knowledge_nodes` - 50,926+ знаний
- `domains` - 35+ доменов

### Подключение:

- **URL:** `postgresql://admin:secret@localhost:5432/knowledge_os`
- **Pool:** `app.state.knowledge_os_pool` (asyncpg.Pool)
- **Min size:** 2 соединения
- **Max size:** 10 соединений

---

## 🔄 Логика работы

1. **Пользователь отправляет сообщение** с `expert_name`
2. **Чат проверяет эксперта** в Knowledge OS Database напрямую
3. **Если эксперт найден** - логируем информацию
4. **Отправляем запрос в Victoria** (Victoria тоже использует Knowledge OS через свой pool)
5. **Victoria использует эксперта** из Knowledge OS для ответа

---

## 🧪 Тестирование

После перезапуска backend:

1. Откройте чат
2. Отправьте сообщение с `expert_name` (например, "Python Developer")
3. В логах должно быть: `✅ Эксперт 'Python Developer' найден в Knowledge OS`
4. Victoria получит правильного эксперта из базы

---

## 📝 Связь с Clawdbot

**Clawdbot** - это паттерн для:

- File watching
- Skill discovery
- Proactive actions
- Knowledge management

**Knowledge OS Database** - это наша реализация:

- PostgreSQL база данных
- 58+ экспертов
- 50,926+ знаний
- Connection pooling
- Прямой доступ из чата

---

_Интеграция применена: 26.01.2026_
