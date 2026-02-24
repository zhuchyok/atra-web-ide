# 🧹 Анализ Docker ресурсов — что лишнее?

**Дата:** 2026-01-25  
**Вопрос:** Есть ли в Docker что-то лишнее?

---

## 📊 ТЕКУЩЕЕ СОСТОЯНИЕ

### Использование дискового пространства:

```
Images:      38.67GB (31.59GB можно освободить - 81%)
Containers:  1.925MB (16.38kB можно освободить - 0%)
Volumes:     482MB (1.037kB можно освободить - 0%)
Build Cache: 20.64GB (всё можно освободить!)
```

**Итого можно освободить: ~52GB**

---

## 🔍 НАЙДЕННЫЕ ПРОБЛЕМЫ

### 1. ❌ Дублирующиеся контейнеры БД

**Проблема:** Три контейнера PostgreSQL, но используется только один!

- ✅ `atra-knowledge-os-db` — **РАБОТАЕТ** (используется)
- ❌ `knowledge_os_db` — **Created** (не запущен, лишний)
- ❌ `knowledge-os-db` — **Created** (не запущен, лишний)

**Решение:** Удалить два лишних контейнера.

---

### 2. ❌ Дублирующиеся образы агентов

**Проблема:** Старые и новые образы агентов одновременно.

#### Victoria:

- ✅ `atra-web-ide-victoria:latest` (3.64GB) — **ИСПОЛЬЗУЕТСЯ**
- ❌ `knowledge_os-victoria-agent:latest` (1.15GB) — **НЕ ИСПОЛЬЗУЕТСЯ** (старый)

#### Veronica:

- ✅ `atra-web-ide-veronica:latest` (3.46GB) — **ИСПОЛЬЗУЕТСЯ**
- ❌ `knowledge_os-veronica-agent:latest` (1.15GB) — **НЕ ИСПОЛЬЗУЕТСЯ** (старый)

**Решение:** Удалить старые образы (`knowledge_os-*`), освободить ~2.3GB.

---

### 3. ❌ Неиспользуемые образы (Elasticsearch/Kibana)

**Проблема:** Образы установлены, но не используются.

- ❌ `docker.elastic.co/elasticsearch/elasticsearch:8.11.0` (1.27GB)
- ❌ `docker.elastic.co/kibana/kibana:8.11.0` (1.79GB)

**Итого:** ~3GB неиспользуемого пространства.

**Решение:** Удалить, если не планируется использование.

---

### 4. ⚠️ Grafana (возможно не используется)

- ⚠️ `grafana/grafana:latest` (932MB)

**Проверка:** Нужно проверить, используется ли Grafana.

---

### 5. ❌ Build Cache (20.64GB!)

**Проблема:** Огромный кэш сборки, который можно безопасно очистить.

**Решение:** Очистить build cache — освободить 20.64GB.

---

### 6. ⚠️ Дублирующиеся сети

- ✅ `atra-network` — используется
- ❌ `atra_atra-network` — возможно дубликат
- ⚠️ `knowledge_os_default` — возможно не используется

**Решение:** Проверить и удалить неиспользуемые сети.

---

### 7. ✅ Контейнеры atra-web-ide-backend/frontend (используются)

- ✅ `atra-web-ide-backend` (Up) — **ИСПОЛЬЗУЕТСЯ** (Web IDE Backend)
- ✅ `atra-web-ide-frontend` (Up) — **ИСПОЛЬЗУЕТСЯ** (Web IDE Frontend)

**Примечание:** Это Web IDE (браузерная оболочка), не часть корпорации, но используется для работы.

### 8. ❌ Дублирующиеся volumes

**Проблема:** Несколько volumes для одних и тех же данных.

- ✅ `atra-postgres-data` — используется
- ❌ `knowledge_os_postgres_data` — возможно не используется
- ✅ `atra-redis-data` — используется
- ❌ `atra_redis-data` — возможно дубликат
- ✅ `atra-workspace-data` — используется
- ❌ `atra_knowledge-os-data` — возможно не используется

**Решение:** Проверить и удалить неиспользуемые volumes.

---

## ✅ ЧТО НУЖНО (активные ресурсы)

### Контейнеры (8 активных):

1. ✅ `atra-knowledge-os-db` — база данных
2. ✅ `atra-victoria-agent` — Victoria Agent
3. ✅ `atra-veronica-agent` — Veronica Agent
4. ✅ `knowledge_os_api` — Knowledge OS API
5. ✅ `knowledge_os_worker` — Worker
6. ✅ `atra-redis` — Redis
7. ⚠️ `atra-web-ide-backend` — нужно проверить
8. ⚠️ `atra-web-ide-frontend` — нужно проверить

### Образы (нужные):

1. ✅ `pgvector/pgvector:pg16` — PostgreSQL с pgvector
2. ✅ `atra-web-ide-victoria:latest` — Victoria
3. ✅ `atra-web-ide-veronica:latest` — Veronica
4. ✅ `knowledge_os-api:latest` — API
5. ✅ `knowledge_os-worker:latest` — Worker
6. ✅ `redis:7-alpine` — Redis

---

## 🧹 ПЛАН ОЧИСТКИ

### Безопасная очистка (можно делать сразу):

1. **Удалить остановленные контейнеры:**

   ```bash
   docker rm knowledge_os_db knowledge-os-db
   ```

2. **Удалить старые образы агентов:**

   ```bash
   docker rmi knowledge_os-victoria-agent:latest knowledge_os-veronica-agent:latest
   ```

3. **Очистить build cache:**

   ```bash
   docker builder prune -f
   ```

4. **Удалить неиспользуемые сети:**
   ```bash
   docker network prune -f
   ```

**Освободит:** ~24GB

---

### Осторожная очистка (проверить перед удалением):

1. **Elasticsearch/Kibana:**
   - Проверить, используются ли
   - Если нет — удалить (~3GB)

2. **Grafana:**
   - Проверить, используется ли
   - Если нет — удалить (~932MB)

3. **atra-web-ide-backend/frontend:**
   - Проверить, нужны ли для корпорации
   - Если нет — остановить и удалить

---

## 🚀 АВТОМАТИЧЕСКАЯ ОЧИСТКА

Создан скрипт для безопасной очистки:

```bash
bash scripts/docker_cleanup.sh
```

Скрипт:

- ✅ Показывает что можно удалить
- ✅ Спрашивает подтверждение перед удалением
- ✅ Безопасно удаляет только неиспользуемые ресурсы

---

## 📋 РЕКОМЕНДУЕМЫЕ ДЕЙСТВИЯ

### 1. Немедленно (безопасно):

```bash
# Удалить дублирующиеся контейнеры БД
docker rm knowledge_os_db knowledge-os-db

# Удалить старые образы агентов
docker rmi knowledge_os-victoria-agent:latest knowledge_os-veronica-agent:latest

# Очистить build cache
docker builder prune -f
```

**Освободит:** ~24GB

### 2. Удалить неиспользуемые образы (Elasticsearch/Kibana/Grafana):

```bash
# Elasticsearch/Kibana не запущены - можно удалить
docker rmi docker.elastic.co/elasticsearch/elasticsearch:8.11.0
docker rmi docker.elastic.co/kibana/kibana:8.11.0

# Grafana не запущен - можно удалить (если не планируется использовать)
docker rmi grafana/grafana:latest
```

**Освободит:** ~4GB

### 3. Итого можно освободить:

**~24GB** (быстрая очистка: контейнеры, старые образы, build cache)  
**~28GB** (полная очистка: + Elasticsearch/Kibana/Grafana)

---

## ✅ ИТОГ

**Да, есть лишнее в Docker!**

**Основные проблемы:**

1. ❌ Дублирующиеся контейнеры БД (2 лишних)
2. ❌ Старые образы агентов (~2.3GB)
3. ❌ Build cache (20.64GB!)
4. ❌ Неиспользуемые образы Elasticsearch/Kibana (~3GB)

**Рекомендация:** Запустить `scripts/docker_cleanup.sh` для безопасной очистки.

---

_Анализ выполнен 2026-01-25_
