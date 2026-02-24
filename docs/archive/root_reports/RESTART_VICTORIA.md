# 🔄 Перезапуск Victoria - Инструкция

**Дата:** 2026-01-27  
**Цель:** Перезапустить Victoria с обновленной конфигурацией БД

---

## ✅ ПЕРЕД ПЕРЕЗАПУСКОМ

Убедитесь, что:

- ✅ Docker Desktop запущен
- ✅ БД `knowledge_postgres` запущена
- ✅ Конфигурация обновлена (см. `DATABASE_FIX_SUMMARY.md`)

---

## 🚀 ПЕРЕЗАПУСК VICTORIA

### 1. Проверить статус Docker:

```bash
docker ps
```

### 2. Перезапустить Victoria:

```bash
cd /Users/bikos/Documents/atra-web-ide
docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent
```

### 3. Проверить статус:

```bash
# Проверить health
curl http://localhost:8010/health

# Проверить статус с деталями
curl http://localhost:8010/status | jq '.victoria_enhanced'
```

### 4. Проверить логи:

```bash
# Проверить подключение к БД
docker logs victoria-agent 2>&1 | grep -i "database\|DATABASE_URL\|эксперты\|fallback"

# Последние 50 строк логов
docker logs victoria-agent 2>&1 | tail -50
```

---

## ✅ ПРОВЕРКА УСПЕШНОГО ПОДКЛЮЧЕНИЯ

### Признаки успешного подключения:

1. **В логах должно быть:**

   ```
   🔌 Использую DATABASE_URL для подключения к экспертам корпорации
   ✅ Подключение к БД успешно
   ```

2. **НЕ должно быть:**

   ```
   ⚠️ DATABASE_URL не настроен
   ⚠️ asyncpg или DATABASE_URL недоступны, используем fallback
   ```

3. **В статусе:**
   ```json
   {
     "victoria_enhanced": {
       "enabled": true,
       "monitoring_started": true,
       "event_bus_available": true,
       "skill_registry_available": true
     }
   }
   ```

---

## 🔧 ЕСЛИ ПРОБЛЕМЫ

### Проблема 1: Docker не запущен

```bash
# Запустить Docker Desktop вручную
open -a Docker
# Подождать 30-60 секунд
```

### Проблема 2: БД не доступна

```bash
# Проверить, запущена ли БД
docker ps | grep knowledge_postgres

# Если не запущена, запустить из проекта atra
cd ~/Documents/atra
docker-compose up -d knowledge_postgres
```

### Проблема 3: Victoria не подключается к БД

```bash
# Проверить переменные окружения
docker exec victoria-agent env | grep DATABASE_URL

# Должно быть:
# DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os
```

### Проблема 4: Сеть Docker

```bash
# Проверить сеть
docker network ls | grep atra

# Если сети нет, создать
docker network create atra-network
```

---

## 📋 ПОЛНАЯ ПЕРЕЗАГРУЗКА

Если простой перезапуск не помог:

```bash
# 1. Остановить Victoria
docker-compose -f knowledge_os/docker-compose.yml stop victoria-agent

# 2. Удалить контейнер
docker-compose -f knowledge_os/docker-compose.yml rm -f victoria-agent

# 3. Запустить заново
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent

# 4. Проверить логи
docker logs -f victoria-agent
```

---

## ✅ РЕЗУЛЬТАТ

После успешного перезапуска:

- ✅ Victoria должна подключаться к БД `knowledge_postgres`
- ✅ Использовать экспертов из базы знаний (не fallback)
- ✅ Все компоненты Victoria Enhanced должны работать

---

**Если проблемы остаются, см. `VICTORIA_DATABASE_CONNECTION.md`**
