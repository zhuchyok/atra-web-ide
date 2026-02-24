# 🚚 Миграция Docker с Mac Studio на Mac Studio

**Дата:** 2026-01-25  
**Цель:** Перенести все Docker контейнеры и данные с Mac Studio на Mac Studio

---

## ⚠️ ВАЖНО

- **Docker на Mac Studio и Mac Studio - это разные системы!**
- После миграции Docker на Mac Studio можно выключить
- Все данные (volumes, базы данных) будут перенесены

---

## 📋 ЧТО ПЕРЕНОСИТСЯ

1. **Docker Volumes (ВСЕ):**
   - `postgres_data` - база данных Knowledge OS
   - Все данные экспертов, знаний, задач
   - Все volumes связанные с atra, knowledge, postgres
   - **ВСЕ volumes** найденные в Docker

2. **Docker Образы (Images):**
   - Victoria Agent образы
   - Veronica Agent образы
   - Knowledge OS образы
   - PostgreSQL образы
   - Все образы связанные с проектом

3. **Конфигурация:**
   - `docker-compose.yml` (корневой и knowledge_os)
   - Все `.env` файлы
   - Конфигурация контейнеров

4. **Контейнеры:**
   - Victoria Agent
   - Veronica Agent
   - Knowledge OS Database
   - Knowledge OS API
   - И все другие сервисы проекта

---

## 🚀 ПРОЦЕСС МИГРАЦИИ

### Шаг 1: На Mac Studio - Экспорт данных

**Вариант А: Полная миграция (рекомендуется):**

```bash
cd ~/Documents/atra-web-ide
bash scripts/full_migration_Mac Studio_to_macstudio.sh
```

**Вариант Б: Только экспорт:**

```bash
cd ~/Documents/atra-web-ide
bash scripts/migrate_docker_to_mac_studio.sh
```

**Что делает:**

1. ✅ Останавливает ВСЕ контейнеры на Mac Studio (knowledge_os и корневые)
2. ✅ Экспортирует ВСЕ Docker volumes
3. ✅ Экспортирует ВСЕ Docker образы (images)
4. ✅ Копирует всю конфигурацию
5. ✅ Копирует все на Mac Studio через SCP

---

### Шаг 2: На Mac Studio - Импорт данных

```bash
cd ~/Documents/atra-web-ide
bash scripts/import_docker_from_Mac Studio.sh
```

**Что делает:**

1. ✅ Импортирует Docker volumes
2. ✅ Копирует конфигурацию
3. ✅ Создает Docker сеть
4. ✅ Запускает все контейнеры

---

### Шаг 3: Проверка на Mac Studio

```bash
# Проверка Victoria
curl http://localhost:8010/health

# Проверка Veronica
curl http://localhost:8011/health

# Проверка Ollama/MLX
curl http://localhost:11434/api/tags

# Проверка Knowledge OS
curl http://localhost:8000/health
```

---

### Шаг 4: Выключение Docker на Mac Studio (опционально)

После успешной миграции на Mac Studio:

```bash
# На Mac Studio
docker-compose -f knowledge_os/docker-compose.yml down
# Docker Desktop можно закрыть
```

---

## 🔍 РУЧНАЯ МИГРАЦИЯ (если скрипты не работают)

### 1. Экспорт volumes на Mac Studio

```bash
# Список volumes
docker volume ls

# Экспорт каждого volume
docker run --rm -v <volume_name>:/data -v $(pwd):/backup alpine \
  tar czf /backup/<volume_name>.tar.gz -C /data .
```

### 2. Копирование на Mac Studio

```bash
scp -r /tmp/atra-docker-migration-* bikos@192.168.1.64:~/Documents/atra-web-ide/backups/migration/
```

### 3. Импорт на Mac Studio

```bash
# Создание volume
docker volume create <volume_name>

# Импорт данных
docker run --rm -v <volume_name>:/data -v $(pwd):/backup alpine \
  tar xzf /backup/<volume_name>.tar.gz -C /data
```

---

## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ

1. **База данных:** Все данные экспертов, знаний, задач будут перенесены
2. **Конфигурация:** `.env` файлы будут скопированы
3. **Volumes:** Все Docker volumes будут экспортированы и импортированы
4. **Сеть:** Docker сеть `atra-network` будет создана на Mac Studio

---

## 🐛 УСТРАНЕНИЕ ПРОБЛЕМ

### Ошибка подключения к Mac Studio

```bash
# Проверьте SSH
ssh bikos@192.168.1.64

# Проверьте, что Mac Studio в сети
ping 192.168.1.64
```

### Volumes не импортируются

```bash
# Проверьте права доступа
ls -la backups/migration/

# Импортируйте вручную (см. выше)
```

### Контейнеры не запускаются

```bash
# Проверьте логи
docker-compose -f knowledge_os/docker-compose.yml logs

# Проверьте конфигурацию
docker-compose -f knowledge_os/docker-compose.yml config
```

---

## ✅ ПОСЛЕ МИГРАЦИИ

После успешной миграции:

1. ✅ Все сервисы работают на Mac Studio
2. ✅ Все данные перенесены
3. ✅ Docker на Mac Studio можно выключить
4. ✅ Доступ с Mac Studio: `http://192.168.1.64:8010` (Victoria), и т.д.

---

_Документ создан 2026-01-25_
