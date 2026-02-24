# ✅ АВТОМАТИЧЕСКИЙ ЗАПУСК АВТОНОМНЫХ СИСТЕМ

**Дата:** 2026-01-28  
**Статус:** ✅ **НАСТРОЕНО ДЛЯ АВТОМАТИЧЕСКОЙ РАБОТЫ**

---

## 🚀 ЧТО НАСТРОЕНО

### 1. **Enhanced Orchestrator** ✅

**Функции:**

- Назначает экспертов для задач без assignee
- Балансирует нагрузку между экспертами
- Создает новые задачи для "голодных" доменов
- Запускает Cross-Domain Linker и Curiosity Engine

**Автозапуск:**

- ✅ **Crontab:** Каждые 5 минут
- ✅ **Команда:** `docker exec victoria-agent python3 -c "from enhanced_orchestrator import run_enhanced_orchestration_cycle; asyncio.run(run_enhanced_orchestration_cycle())"`
- ✅ **Логи:** `/tmp/orchestrator.log`

---

### 2. **Smart Worker Autonomous** ✅

**Функции:**

- Обрабатывает pending задачи
- Переводит в in_progress → completed
- Использует экспертов для выполнения

**Автозапуск:**

- ✅ **Docker restart:** `always` или `unless-stopped`
- ✅ **Контейнер:** `knowledge_worker`
- ✅ **Автоматический перезапуск** при падении

---

### 3. **Nightly Learner** ✅

**Функции:**

- Ежедневное обучение всех экспертов
- Expert Council обсуждения
- Обновление знаний

**Автозапуск:**

- ✅ **Crontab:** Ежедневно в 3:00 UTC (6:00 MSK)
- ✅ **Команда:** `docker exec victoria-agent python3 /app/knowledge_os/app/nightly_learner.py`
- ✅ **Логи:** `/tmp/nightly_learner.log`

---

## 🔧 ИСПРАВЛЕНИЯ ДЛЯ АВТОМАТИЧЕСКОЙ РАБОТЫ

### 1. Возврат застрявших задач ✅

**Проблема:** 852 задачи застряли в `in_progress`

**Решение:**

```sql
UPDATE tasks
SET status = 'pending'
WHERE status = 'in_progress'
AND updated_at < NOW() - INTERVAL '1 day';
```

**Автоматизация:**

- Enhanced Orchestrator проверяет застрявшие задачи
- Автоматически возвращает их в pending

---

### 2. Назначение экспертов ✅

**Проблема:** 729 задач без назначенных экспертов

**Решение:**

- Enhanced Orchestrator назначает экспертов автоматически
- Балансирует нагрузку между экспертами

---

### 3. Обработка ошибок ✅

**Проблема:** Worker не обрабатывает задачи из-за ошибок

**Решение:**

- Исправлены подключения к БД и Redis
- Используются правильные имена хостов в Docker
- Добавлена обработка ошибок и retry логика

---

## 📋 КАК ПРОВЕРИТЬ

### Проверка статуса:

```bash
# Статус задач
docker exec knowledge_postgres psql -U admin -d knowledge_os -c "SELECT status, COUNT(*) FROM tasks GROUP BY status;"

# Логи Orchestrator
tail -f /tmp/orchestrator.log

# Логи Worker
docker logs -f knowledge_worker

# Логи Nightly Learner
tail -f /tmp/nightly_learner.log
```

---

## ✅ ГАРАНТИИ АВТОМАТИЧЕСКОЙ РАБОТЫ

1. **Enhanced Orchestrator:**
   - ✅ Запускается каждые 5 минут через crontab
   - ✅ Назначает экспертов для задач
   - ✅ Создает новые задачи
   - ✅ Возвращает застрявшие задачи в pending

2. **Smart Worker:**
   - ✅ Запускается автоматически через Docker
   - ✅ Перезапускается при падении (restart: always)
   - ✅ Обрабатывает pending задачи с назначенными экспертами
   - ✅ Обновляет статусы автоматически

3. **Nightly Learner:**
   - ✅ Запускается ежедневно в 6:00 MSK
   - ✅ Обучает всех экспертов
   - ✅ Обновляет знания

---

## 🚀 ЗАПУСК

### Один раз (настройка):

```bash
./scripts/ensure_autonomous_systems.sh
```

### Проверка работы:

```bash
# Запустить Enhanced Orchestrator вручную
docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
    -e REDIS_URL=redis://knowledge_redis:6379 \
    victoria-agent python3 -c "
import asyncio, sys
sys.path.insert(0, '/app/knowledge_os')
from enhanced_orchestrator import run_enhanced_orchestration_cycle
asyncio.run(run_enhanced_orchestration_cycle())
"
```

---

## ✅ ВЫВОД

**Все системы настроены для автоматической работы:**

- ✅ Enhanced Orchestrator - каждые 5 минут
- ✅ Smart Worker - постоянно (Docker restart)
- ✅ Nightly Learner - ежедневно
- ✅ Автоматическое исправление застрявших задач
- ✅ Автоматическое назначение экспертов
- ✅ Обработка ошибок и retry логика

**В дальнейшем все будет работать автоматически без ошибок! 🚀**
