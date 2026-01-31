# Интерактивные туториалы Knowledge OS

## Туториал 1: Первые шаги

### Шаг 1: Регистрация

```python
import httpx

async def register():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/auth/register",
            json={
                "username": "newuser",
                "password": "securepassword",
                "email": "user@example.com"
            }
        )
        print(response.json())
```

### Шаг 2: Вход

```python
async def login():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/auth/login",
            json={
                "username": "newuser",
                "password": "securepassword"
            }
        )
        token = response.json()["access_token"]
        return token
```

### Шаг 3: Создание первого знания

```python
async def create_first_knowledge(token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/knowledge",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": "Мое первое знание",
                "domain": "general",
                "confidence_score": 1.0
            }
        )
        print(response.json())
```

## Туториал 2: Работа с графом знаний

### Шаг 1: Создание знаний

```python
# Создаем несколько связанных знаний
knowledge1 = await create_knowledge(
    "Python основы",
    "python",
    token
)

knowledge2 = await create_knowledge(
    "Python async/await",
    "python",
    token
)
```

### Шаг 2: Создание связей

```python
# Связываем знания
await client.call_tool(
    "create_knowledge_link",
    {
        "source_id": knowledge2["id"],
        "target_id": knowledge1["id"],
        "link_type": "depends_on",
        "strength": 0.9
    }
)
```

### Шаг 3: Навигация по графу

```python
# Находим связанные знания
related = await client.call_tool(
    "get_related_knowledge",
    {
        "node_id": knowledge1["id"],
        "max_depth": 2
    }
)
```

## Туториал 3: Использование контекстной памяти

### Шаг 1: Поиск похожих паттернов

```python
patterns = await client.call_tool(
    "find_similar_patterns",
    {
        "query": "Как оптимизировать ML модель?",
        "pattern_type": "query_pattern",
        "min_success": 0.7
    }
)
```

### Шаг 2: Получение предпочтений пользователя

```python
preferences = await client.call_tool(
    "get_user_preferences",
    {
        "user_identifier": "user123"
    }
)
```

### Шаг 3: Прогнозирование потребностей

```python
predictions = await client.call_tool(
    "predict_user_needs",
    {
        "user_identifier": "user123",
        "recent_interactions": 10
    }
)
```
