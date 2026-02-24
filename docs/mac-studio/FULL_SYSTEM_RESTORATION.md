# 🔄 Полное восстановление корпорации ATRA

**Дата:** 2026-01-25  
**Цель:** Восстановить все автоматические системы как на сервере

---

## 🎯 ЧТО БЫЛО НА СЕРВЕРЕ

### Автоматические системы (из `restart_all.py`):

1. **Dashboard** - Streamlit dashboard (порт 5002)
2. **MCP Server** - `main_enhanced.py` (порт 8000)
3. **Vector Core** - векторные эмбеддинги
4. **Telegram Gateway** - `telegram_simple.py`
5. **Nightly Learner** - обучение всех экспертов ежедневно
6. **Enhanced Orchestrator** - автоматический цикл каждые 5 минут (300 сек)
7. **Smart Worker Autonomous** - обработка задач

---

## ✅ ЧТО ВОССТАНОВЛЕНО

### 1. Исправлена ошибка в `semantic_cache.py`

- **Проблема:** `Optional` не был импортирован
- **Решение:** Добавлен `from typing import Optional`

### 2. Создан скрипт полного запуска

- **Файл:** `scripts/start_full_corporation.sh`
- **Функции:**
  - Запускает всю инфраструктуру
  - Настраивает Enhanced Orchestrator (каждые 5 минут)
  - Настраивает Nightly Learner (ежедневно в 6:00 MSK)
  - Настраивает Smart Worker Autonomous

---

## 🚀 ЗАПУСК

### Полный запуск всех систем:

```bash
cd /Users/zhuchyok/Documents/atra-web-ide
bash scripts/start_full_corporation.sh
```

### Что запускается:

1. **Базовая инфраструктура:**
   - PostgreSQL (Knowledge OS DB)
   - Knowledge OS API

2. **Агенты:**
   - Victoria Agent (порт 8010)
   - Veronica Agent (порт 8011)

3. **Автоматические системы:**
   - **Enhanced Orchestrator** - каждые 5 минут:
     - Назначает задачи экспертам
     - Балансирует нагрузку
     - Создает связи между знаниями
     - Обрабатывает гипотезы
   - **Nightly Learner** - ежедневно в 6:00 MSK (3:00 UTC):
     - Обучает всех активных экспертов
     - Проводит дебаты (Expert Council)
     - Валидирует знания (LM Judge)
     - Стресс-тесты (Adversarial Critic)
     - Контекстное обучение
     - Эволюция экспертов
   - **Smart Worker Autonomous** - постоянно:
     - Обрабатывает pending задачи
     - Приоритизирует по bug_probability
     - Обновляет статусы задач
     - Сохраняет результаты в knowledge_nodes

---

## 📊 КАК ЭТО РАБОТАЕТ

### Enhanced Orchestrator (каждые 5 минут):

1. **Фаза 1:** Ассоциативный мозг (cross-domain linking)
2. **Фаза 2:** Назначение задач экспертам
3. **Фаза 3:** Перебалансировка нагрузки
4. **Фаза 4:** Голодные домены (desert domains)
5. **Фаза 5:** Global Scout (валидация)
6. **Фаза 6:** Auto-link detection
7. **Фаза 7:** Knowledge Distillation
8. **Фаза 8:** Self-Repair Engine

### Nightly Learner (ежедневно):

1. Синхронизация OKR
2. Обучение всех активных экспертов
3. Expert Council (дебаты между экспертами)
4. LM Judge (верификация знаний)
5. Adversarial Critic (стресс-тесты)
6. Contextual Learning
7. Enhanced Expert Evolution

### Smart Worker Autonomous (постоянно):

1. Ищет pending задачи с назначенными экспертами
2. Приоритизирует по bug_probability
3. Обрабатывает задачи через AI
4. Обновляет статусы (pending → in_progress → completed)
5. Сохраняет результаты в knowledge_nodes

---

## 🔍 МОНИТОРИНГ

### Логи:

```bash
# Orchestrator
tail -f /tmp/orchestrator.log

# Nightly Learner
tail -f /tmp/nightly_learner.log

# Worker
docker logs -f knowledge_os_worker

# Victoria
docker logs -f atra-victoria-agent

# Veronica
docker logs -f atra-veronica-agent
```

### Проверка статуса:

```bash
# Статус задач
docker exec -i atra-knowledge-os-db psql -U admin -d knowledge_os -c "
SELECT status, COUNT(*) as count
FROM tasks
GROUP BY status
ORDER BY count DESC;
"

# Распределение задач по экспертам
docker exec -i atra-knowledge-os-db psql -U admin -d knowledge_os -c "
SELECT e.name, COUNT(*) as tasks
FROM tasks t
JOIN experts e ON t.assignee_expert_id = e.id
WHERE t.status = 'pending'
GROUP BY e.name
ORDER BY tasks DESC
LIMIT 10;
"
```

---

## 🛠️ РУЧНОЙ ЗАПУСК (если нужно)

### Запуск Orchestrator вручную:

```bash
docker exec knowledge_os_api python /app/enhanced_orchestrator.py
```

### Запуск Nightly Learner вручную:

```bash
docker exec knowledge_os_api python /app/nightly_learner.py
```

### Запуск Worker вручную:

```bash
docker exec knowledge_os_worker python smart_worker_autonomous.py
```

---

## 📝 СЛЕДУЮЩИЕ ШАГИ

1. ✅ Запустить полную систему: `bash scripts/start_full_corporation.sh`
2. ⏳ Подождать 5-10 минут для первого цикла Orchestrator
3. 📊 Проверить логи и статус задач
4. 🔄 Система будет работать автоматически:
   - Orchestrator каждые 5 минут
   - Nightly Learner ежедневно в 6:00 MSK
   - Worker постоянно обрабатывает задачи

---

## 🎉 РЕЗУЛЬТАТ

После запуска корпорация будет работать полностью автономно:

- ✅ Задачи автоматически назначаются экспертам
- ✅ Задачи автоматически обрабатываются
- ✅ Эксперты автоматически обучаются
- ✅ Проводятся дебаты и валидация знаний
- ✅ Система развивается и улучшается сама

**Всё как на сервере!** 🚀

---

_Восстановление выполнено 2026-01-25_
