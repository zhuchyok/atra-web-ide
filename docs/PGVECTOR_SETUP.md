# PostgreSQL + pgvector — настройка и проверка

**Дата:** 2026-01-31  
**Основано на:** анализе проекта atra-web-ide

---

## Текущая база данных

| Параметр | Значение |
|----------|----------|
| **Тип БД** | PostgreSQL 16 (pgvector/pgvector:pg16) |
| **Расширение** | pgvector |
| **Основная таблица** | `knowledge_nodes` |
| **Векторный столбец** | `embedding vector(768)` (nomic-embed-text) |
| **Индексы** | IVFFlat (из init.sql) + HNSW (migration) |

---

## Где находятся конфигурации

### 1. Подключение к БД
- **Единый источник:** переменная окружения `DATABASE_URL`
- **Фолбек:** `postgresql://admin:secret@localhost:5432/knowledge_os`
- **В Docker:** `postgresql://admin:secret@knowledge_postgres:5432/knowledge_os`
- **Модулей `knowledge_os/db/database.py` нет** — используется `asyncpg` напрямую в каждом модуле

### 2. Файлы
```
knowledge_os/db/init.sql                    # Схема БД, IVFFlat индекс
knowledge_os/db/migrations/
  add_hnsw_index_knowledge_nodes.sql        # HNSW индекс
scripts/apply_hnsw_index.py                 # Скрипт применения HNSW
knowledge_os/docker-compose.yml             # DATABASE_URL для сервисов
docker-compose.yml                          # Backend → knowledge_postgres
```

### 3. Контейнер PostgreSQL
- **Имя:** `knowledge_postgres`
- **Образ:** `pgvector/pgvector:pg16`
- **Сеть:** atra-network
- **Запуск:** из atra или вручную; Knowledge OS использует внешний контейнер

---

## SQL для проверки

```sql
-- Версия и расширение
SELECT version();
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Таблица knowledge_nodes
SELECT tablename, schemaname FROM pg_tables WHERE tablename = 'knowledge_nodes';

-- Индексы
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'knowledge_nodes';

-- Размер и количество строк
SELECT 
    pg_size_pretty(pg_total_relation_size('knowledge_nodes')) as total_size,
    COUNT(*) as row_count
FROM knowledge_nodes;
```

---

## HNSW индекс

```sql
-- Создание (уже в migration)
CREATE INDEX knowledge_nodes_embedding_hnsw_idx
ON knowledge_nodes
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Применить через скрипт:**
```bash
DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os python scripts/apply_hnsw_index.py
# или в Docker:
docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os atra-web-ide-backend python scripts/apply_hnsw_index.py
```

---

## Быстрая проверка (Python)

```python
import asyncio
import os
import asyncpg

async def check():
    url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(url)
    
    ext = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
    )
    print(f"pgvector: {'✅' if ext else '❌'}")
    
    idx = await conn.fetchval("""
        SELECT indexname FROM pg_indexes 
        WHERE tablename = 'knowledge_nodes' AND indexdef LIKE '%hnsw%'
    """)
    print(f"HNSW: {'✅' if idx else '❌'}")
    
    n = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes")
    print(f"Узлов: {n}")
    
    await conn.close()

asyncio.run(check())
```

---

## Бэкапы

| Действие | Команда |
|----------|---------|
| Создание дампа | `docker exec knowledge_postgres pg_dump -U admin -d knowledge_os > backup.sql` |
| Восстановление | `docker exec -i knowledge_postgres psql -U admin -d knowledge_os < backup.sql` |
| Импорт из дампа | `bash scripts/migrate_from_dump.sh` (если дамп в `~/migration/server2/` или проекте) |

---

## Известные расхождения

1. **vector(768)** — используется nomic-embed-text (768 dim), не 384.
2. **archive** — старые embedding могли быть 384 dim (`knowledge_nodes_archive`).
3. **database.py** — в проекте нет; подключение через asyncpg в модулях.
