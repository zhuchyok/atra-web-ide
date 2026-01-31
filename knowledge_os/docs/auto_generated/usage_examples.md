# Примеры использования Knowledge OS

## 1. Аутентификация

```python
import httpx

async def login(username: str, password: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/auth/login",
            json={"username": username, "password": password}
        )
        return response.json()

# Использование
token_data = await login("user", "password")
token = token_data["access_token"]
```

## 2. Создание знания

```python
async def create_knowledge(content: str, domain: str, token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/knowledge",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": content,
                "domain": domain,
                "confidence_score": 0.95
            }
        )
        return response.json()
```

## 3. Поиск знаний

```python
async def search_knowledge(query: str, token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/search",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": query, "limit": 10}
        )
        return response.json()
```

## 4. Использование MCP инструментов

```python
# В Cursor через MCP
from mcp import Client

client = Client("knowledge_os")

# Поиск знаний
results = await client.call_tool(
    "search_knowledge",
    {"query": "Python async", "limit": 5}
)

# Создание знания
await client.call_tool(
    "capture_knowledge",
    {
        "content": "Python async/await best practices",
        "domain": "python"
    }
)
```

## 5. Работа с графом знаний

```python
# Создание связи
await client.call_tool(
    "create_knowledge_link",
    {
        "source_id": "uuid-1",
        "target_id": "uuid-2",
        "link_type": "depends_on",
        "strength": 0.9
    }
)

# Получение связанных знаний
related = await client.call_tool(
    "get_related_knowledge",
    {
        "node_id": "uuid-1",
        "max_depth": 2
    }
)
```


# Примеры использования через curl

## 1. Аутентификация

```bash
curl -X POST "http://localhost:8002/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user",
    "password": "password"
  }'
```

## 2. Создание знания

```bash
curl -X POST "http://localhost:8002/knowledge" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Python async/await best practices",
    "domain": "python",
    "confidence_score": 0.95
  }'
```

## 3. Поиск знаний

```bash
curl -X POST "http://localhost:8002/search" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python async",
    "limit": 10
  }'
```

## 4. Получение статистики

```bash
curl -X GET "http://localhost:8002/stats" \
  -H "Authorization: Bearer <token>"
```
