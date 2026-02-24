# 🔌 Подключение Victoria к БД - ИНСТРУКЦИЯ

**Дата:** 2026-01-27  
**Проблема:** Victoria не может подключиться к БД

---

## 🔍 ТЕКУЩАЯ КОНФИГУРАЦИЯ

### В `knowledge_os/docker-compose.yml`:

```yaml
DATABASE_URL: postgresql://admin:secret@knowledge_postgres:5432/knowledge_os
```

### В `.env`:

```env
DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os
```

### Проблема:

- Docker Compose использует `knowledge_postgres` (имя контейнера)
- `.env` использует `db` (не существует)
- БД закомментирована в docker-compose.yml

---

## ✅ РЕШЕНИЕ

### Вариант 1: Использовать существующую БД `knowledge_postgres`

Если БД уже запущена в другом проекте (atra), используйте:

```yaml
# В knowledge_os/docker-compose.yml для victoria-agent:
DATABASE_URL: postgresql://admin:secret@knowledge_postgres:5432/knowledge_os
```

**Проверка:**

```bash
# Проверить, запущена ли БД
docker ps | grep knowledge_postgres

# Проверить подключение из контейнера Victoria
docker exec victoria-agent python -c "
import os
import asyncpg
import asyncio

async def test():
    db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@knowledge_postgres:5432/knowledge_os')
    try:
        conn = await asyncpg.connect(db_url)
        result = await conn.fetchval('SELECT COUNT(*) FROM experts')
        print(f'✅ Подключение успешно! Экспертов в БД: {result}')
        await conn.close()
    except Exception as e:
        print(f'❌ Ошибка: {e}')

asyncio.run(test())
"
```

---

### Вариант 2: Использовать локальную БД (localhost)

Если БД запущена на хосте (не в Docker):

```yaml
# В knowledge_os/docker-compose.yml для victoria-agent:
DATABASE_URL: postgresql://admin:secret@host.docker.internal:5432/knowledge_os
```

**Проверка:**

```bash
# Проверить, доступна ли БД на хосте
psql -h localhost -U admin -d knowledge_os -c "SELECT COUNT(*) FROM experts;"
```

---

### Вариант 3: Раскомментировать БД в docker-compose.yml

Если нужна отдельная БД для atra-web-ide:

1. Раскомментировать секцию `db:` в `knowledge_os/docker-compose.yml`
2. Изменить имя контейнера на `knowledge_os_db` (чтобы не конфликтовать с atra)
3. Обновить `DATABASE_URL` в Victoria:

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: knowledge_os_db # ← Изменить имя!
    # ... остальная конфигурация

  victoria-agent:
    environment:
      DATABASE_URL: postgresql://admin:secret@knowledge_os_db:5432/knowledge_os
```

---

## 🔧 БЫСТРОЕ ИСПРАВЛЕНИЕ

### Если БД `knowledge_postgres` уже запущена:

1. **Обновить `.env`:**

```bash
# В .env файле изменить:
DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os
```

2. **Или установить переменную окружения для Victoria:**

```bash
# В knowledge_os/docker-compose.yml уже правильно:
DATABASE_URL: postgresql://admin:secret@knowledge_postgres:5432/knowledge_os
```

3. **Перезапустить Victoria:**

```bash
cd /Users/bikos/Documents/atra-web-ide
docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent
```

4. **Проверить подключение:**

```bash
# Проверить логи Victoria
docker logs victoria-agent | grep -i "database\|DATABASE_URL\|эксперты"

# Проверить статус
curl http://localhost:8010/status | jq '.victoria_enhanced'
```

---

## 📋 ПРОВЕРКА ПОДКЛЮЧЕНИЯ

### 1. Проверить, какая БД запущена:

```bash
docker ps --filter "name=postgres\|knowledge" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### 2. Проверить переменные окружения Victoria:

```bash
docker exec victoria-agent env | grep DATABASE_URL
```

### 3. Проверить подключение из Victoria:

```bash
docker exec victoria-agent python -c "
import os
print('DATABASE_URL:', os.getenv('DATABASE_URL', 'НЕ УСТАНОВЛЕН'))
"
```

### 4. Проверить логи Victoria:

```bash
docker logs victoria-agent 2>&1 | grep -E "DATABASE_URL|эксперты|fallback" | tail -20
```

---

## 🚨 ЧАСТЫЕ ПРОБЛЕМЫ

### Проблема 1: "asyncpg или DATABASE_URL недоступны"

**Решение:** Проверить, что:

- БД запущена: `docker ps | grep knowledge_postgres`
- DATABASE_URL правильный: `docker exec victoria-agent env | grep DATABASE_URL`
- Сеть Docker правильная: оба контейнера в одной сети `atra-network`

### Проблема 2: "connection refused"

**Решение:**

- Проверить имя контейнера БД: должно быть `knowledge_postgres`
- Проверить сеть: `docker network inspect atra-network`

### Проблема 3: "authentication failed"

**Решение:**

- Проверить пароль: должен быть `secret` (или изменить в обоих местах)
- Проверить пользователя: должен быть `admin`

---

## 📝 ИТОГОВАЯ КОНФИГУРАЦИЯ

### Для Victoria (в `knowledge_os/docker-compose.yml`):

```yaml
victoria-agent:
  environment:
    DATABASE_URL: postgresql://admin:secret@knowledge_postgres:5432/knowledge_os
    # ... остальные переменные
```

### Для локального запуска (в `.env`):

```env
DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os
```

### Для Docker Compose (в `docker-compose.yml`):

```yaml
backend:
  environment:
    DATABASE_URL: postgresql://admin:secret@knowledge_postgres:5432/knowledge_os
```

---

## ✅ ПРОВЕРКА РАБОТЫ

После исправления проверьте:

```bash
# 1. Victoria доступна
curl http://localhost:8010/health

# 2. Victoria использует БД (не fallback)
curl http://localhost:8010/status | jq '.victoria_enhanced'

# 3. Логи без ошибок БД
docker logs victoria-agent 2>&1 | tail -50 | grep -i "database\|fallback"
```

---

**Если проблема не решена, проверьте:**

1. Имя контейнера БД: `docker ps | grep postgres`
2. Сеть Docker: `docker network ls | grep atra`
3. Логи Victoria: `docker logs victoria-agent 2>&1 | tail -100`
