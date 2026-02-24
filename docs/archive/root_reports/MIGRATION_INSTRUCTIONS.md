# 🚚 Инструкция по миграции Docker с Mac Studio на Mac Studio

**Дата:** 2026-01-25  
**IP Mac Studio:** 192.168.1.64  
**Пользователь Mac Studio:** bikos

---

## ⚡ БЫСТРЫЙ СТАРТ

### На Mac Studio:

```bash
cd ~/Documents/atra-web-ide
bash scripts/full_migration_Mac Studio_to_macstudio.sh
```

### На Mac Studio:

```bash
cd ~/Documents/atra-web-ide
bash scripts/import_docker_from_Mac Studio.sh
```

Или автоматически (если бэкап уже скопирован):

```bash
bash scripts/start_all_on_mac_studio.sh
```

---

## 📋 ЧТО ПЕРЕНОСИТСЯ

### ✅ Docker Volumes (ВСЕ)

- `postgres_data` - база данных Knowledge OS
- Все данные экспертов, знаний, задач
- Все volumes связанные с проектом

### ✅ Docker Образы (Images)

- Victoria Agent образы
- Veronica Agent образы
- Knowledge OS образы
- PostgreSQL образы
- Все образы проекта

### ✅ Конфигурация

- `docker-compose.yml` (корневой и knowledge_os)
- Все `.env` файлы
- Настройки контейнеров

---

## 🚀 ПРОЦЕСС МИГРАЦИИ

### Шаг 1: На Mac Studio - Экспорт

```bash
cd ~/Documents/atra-web-ide
bash scripts/full_migration_Mac Studio_to_macstudio.sh
```

**Что происходит:**

1. ✅ Останавливает все контейнеры
2. ✅ Экспортирует ВСЕ Docker volumes
3. ✅ Экспортирует ВСЕ Docker образы
4. ✅ Копирует всю конфигурацию
5. ✅ Копирует все на Mac Studio через SCP

**Время:** ~5-15 минут (зависит от размера данных)

---

### Шаг 2: На Mac Studio - Импорт

```bash
cd ~/Documents/atra-web-ide
bash scripts/import_docker_from_Mac Studio.sh
```

**Что происходит:**

1. ✅ Импортирует Docker образы
2. ✅ Импортирует все volumes
3. ✅ Копирует конфигурацию
4. ✅ Создает Docker сеть
5. ✅ Запускает все контейнеры

**Время:** ~5-10 минут

---

### Шаг 3: Проверка

```bash
# Проверка Victoria
curl http://localhost:8010/health

# Проверка Veronica
curl http://localhost:8011/health

# Проверка Ollama/MLX
curl http://localhost:11434/api/tags

# Проверка Knowledge OS
curl http://localhost:8000/health

# Проверка контейнеров
docker-compose -f knowledge_os/docker-compose.yml ps
```

---

## ⚠️ ВАЖНО

1. **Docker на Mac Studio и Mac Studio - это разные системы!**
2. После миграции Docker на Mac Studio можно выключить
3. Все данные будут перенесены
4. Контейнеры на Mac Studio будут остановлены во время экспорта

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

# Проверьте логи импорта
bash scripts/import_docker_from_Mac Studio.sh 2>&1 | tee import.log
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
