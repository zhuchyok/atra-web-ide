# Как использовать Victoria Initiative and Self-Extension

**Дата:** 2026-01-26  
**Статус:** ✅ Все компоненты реализованы и готовы к использованию

---

## 🚀 Быстрый старт

### 1. Активация мониторинга и Event-Driven Architecture

Victoria Enhanced теперь поддерживает автоматический запуск всех компонентов мониторинга.

#### Вариант 1: Автоматический запуск (рекомендуется)

Victoria автоматически запустит все компоненты при инициализации, если установлена переменная окружения:

```bash
export USE_VICTORIA_ENHANCED=true
export ENABLE_EVENT_MONITORING=true
```

#### Вариант 2: Ручной запуск

```python
from knowledge_os.app.victoria_enhanced import VictoriaEnhanced

# Создаем Victoria Enhanced
victoria = VictoriaEnhanced()

# Запускаем все компоненты мониторинга
await victoria.start()

# Теперь Victoria:
# ✅ Реагирует на изменения файлов
# ✅ Мониторит сервисы (Docker, HTTP)
# ✅ Отслеживает дедлайны
# ✅ Автоматически обновляет skills
# ✅ Использует LangGraph state machines
```

### 2. Проверка статуса

```python
# Проверяем статус всех компонентов
status = await victoria.get_status()

print(status)
# {
#   "event_bus_available": True,
#   "skill_registry_available": True,
#   "skills_count": 5,
#   "monitoring_started": True,
#   "file_watcher_available": True,
#   "service_monitor_available": True,
#   ...
# }
```

---

## 📋 Что теперь умеет Victoria

### 1. Проактивные действия (без команд)

Victoria теперь **сама реагирует** на события:

#### Реакция на создание файла

```
1. Вы создаете файл test.py
2. File Watcher обнаруживает изменение
3. Victoria автоматически:
   - Анализирует файл
   - Проверяет синтаксис (если Python)
   - Предлагает улучшения
   - Использует базу знаний для анализа
```

#### Реакция на падение сервиса

```
1. MLX API Server падает
2. Service Monitor обнаруживает проблему
3. Victoria автоматически:
   - Пытается перезапустить сервис
   - Уведомляет о проблеме
   - Использует SelfCheckSystem для восстановления
```

#### Реакция на дедлайн

```
1. Дедлайн задачи через 6 часов
2. Deadline Tracker обнаруживает приближение
3. Victoria автоматически:
   - Проверяет статус задачи
   - Предлагает помощь
   - Перераспределяет ресурсы
```

### 2. Саморасширение (динамические skills)

Victoria теперь **сама создает новые skills**:

#### Пример: Нужен skill для Gmail API

```
1. Вы просите: "отправь email через Gmail API"
2. Victoria определяет, что нужен skill
3. Skill Discovery:
   - Ищет библиотеку в PyPI
   - Ищет API документацию
   - Генерирует SKILL.md в формате AgentSkills
   - Генерирует код handler
   - Сохраняет в базу знаний
   - Добавляет в реестр
4. Victoria использует новый skill
```

#### Использование skills

```python
# Victoria автоматически использует skills из реестра
# Список доступных skills:
from knowledge_os.app.skill_registry import get_skill_registry

registry = get_skill_registry()
skills = registry.list_skills()

for skill in skills:
    print(f"- {skill.name}: {skill.description}")
```

### 3. LangGraph State Machines

Victoria использует state machines для сложных workflows:

```python
# State machines автоматически используются в event handlers
# Проверяем историю состояний:
from knowledge_os.app.skill_state_machine import SkillStateMachine

machine = SkillStateMachine()
history = machine.get_state_history("event_id_123")

# Восстанавливаем из checkpoint:
checkpoint = machine.restore_from_checkpoint("checkpoint_id")
```

---

## 🔧 Настройка

### 1. Переменные окружения

```bash
# Включить Victoria Enhanced
export USE_VICTORIA_ENHANCED=true

# Включить мониторинг событий
export ENABLE_EVENT_MONITORING=true

# Настройки File Watcher
export FILE_WATCHER_ENABLED=true
export FILE_WATCHER_PATHS=/path/to/project

# Настройки Service Monitor
export SERVICE_MONITOR_ENABLED=true
export SERVICE_MONITOR_INTERVAL=30  # секунд

# Настройки Deadline Tracker
export DEADLINE_TRACKER_ENABLED=true
export DEADLINE_NOTIFICATION_HOURS=24,12,6,1  # за сколько часов уведомлять

# Настройки Skills
export SKILLS_WATCHER_ENABLED=true
export SKILLS_WATCHER_DEBOUNCE_MS=250

# Настройки State Machines
export STATE_MACHINE_PERSISTENCE=true
export STATE_MACHINE_PERSISTENCE_PATH=~/.atra/state_machines
```

### 2. Конфигурация через код

```python
from knowledge_os.app.victoria_enhanced import VictoriaEnhanced
from knowledge_os.app.skill_state_machine import StateMachineConfig

# Настройка State Machine
config = StateMachineConfig(
    max_retries=3,
    checkpoint_interval=5,
    enable_persistence=True,
    persistence_path="~/.atra/state_machines"
)

victoria = VictoriaEnhanced()
# State machines настраиваются автоматически
```

---

## 📊 Мониторинг и отладка

### 1. Проверка логов

```bash
# Логи Victoria Enhanced
tail -f logs/victoria_enhanced.log

# Логи Event Bus
tail -f logs/event_bus.log

# Логи File Watcher
tail -f logs/file_watcher.log

# Логи Service Monitor
tail -f logs/service_monitor.log
```

### 2. Проверка событий

```python
from knowledge_os.app.event_bus import get_event_bus, EventType

bus = get_event_bus()

# Подписываемся на события
async def event_handler(event):
    print(f"Событие: {event.event_type.value}")
    print(f"Payload: {event.payload}")

bus.subscribe(EventType.FILE_CREATED, event_handler)
bus.subscribe(EventType.SERVICE_DOWN, event_handler)
bus.subscribe(EventType.SKILL_ADDED, event_handler)
```

### 3. Статистика

```python
# Статистика File Watcher
stats = await victoria.file_watcher.get_stats()
print(f"Файлов обработано: {stats['files_processed']}")

# Статистика Service Monitor
stats = await victoria.service_monitor.get_stats()
print(f"Проверок выполнено: {stats['checks_performed']}")

# Статистика Skills
stats = victoria.skill_registry.get_stats()
print(f"Skills загружено: {stats['total_skills']}")
```

---

## 🗄️ База данных

### 1. Применение миграции

```bash
# Применить миграцию для skills
cd knowledge_os
python scripts/apply_migrations.py

# Или вручную через psql
psql -U postgres -d knowledge_os -f db/migrations/add_skills_tables.sql
```

### 2. Проверка таблиц

```sql
-- Проверяем таблицы skills
SELECT COUNT(*) FROM skills;
SELECT name, version, source FROM skills LIMIT 10;

-- Статистика использования skills
SELECT skill_id, COUNT(*) as usage_count
FROM skill_usage
GROUP BY skill_id
ORDER BY usage_count DESC
LIMIT 10;
```

---

## 🧪 Тестирование

### 1. Запуск тестов

```bash
cd knowledge_os

# Все тесты
pytest tests/ -v

# Конкретный тест
pytest tests/test_file_watcher.py -v
pytest tests/test_skill_registry.py -v
pytest tests/test_victoria_event_handlers.py -v
```

### 2. Интеграционные тесты

```python
# Тест полного цикла
import asyncio
from knowledge_os.app.victoria_enhanced import VictoriaEnhanced

async def test_full_cycle():
    victoria = VictoriaEnhanced()
    await victoria.start()

    # Создаем тестовый файл
    with open("/tmp/test.py", "w") as f:
        f.write("print('test')")

    # Ждем обработки
    await asyncio.sleep(2)

    # Проверяем результат
    status = await victoria.get_status()
    assert status["monitoring_started"] == True

    await victoria.stop()

asyncio.run(test_full_cycle())
```

---

## 📝 Примеры использования

### Пример 1: Автоматический анализ нового файла

```python
# 1. Создаем файл
with open("new_feature.py", "w") as f:
    f.write("def hello(): pass")

# 2. Victoria автоматически:
#    - Обнаруживает файл (File Watcher)
#    - Анализирует через базу знаний
#    - Предлагает улучшения
#    - Создает события для обработки
```

### Пример 2: Создание нового skill

```python
from knowledge_os.app.skill_discovery import SkillDiscovery

discovery = SkillDiscovery()

# Victoria автоматически создаст skill для Gmail API
skill = await discovery.discover_skill("отправка email через Gmail API")

if skill:
    print(f"✅ Skill создан: {skill.name}")
    print(f"   Путь: {skill.skill_path}")
    print(f"   Описание: {skill.description}")
```

### Пример 3: Мониторинг сервисов

```python
# Service Monitor автоматически проверяет:
# - Victoria Agent (8020)
# - Veronica Agent (8021)
# - MLX API Server (11435)
# - Backend (8080)
# - Frontend (3002)
# - PostgreSQL (5432)
# - Redis (6379)

# При падении сервиса Victoria автоматически:
# - Публикует событие SERVICE_DOWN
# - Пытается перезапустить через SelfCheckSystem
# - Уведомляет о проблеме
```

---

## 🛑 Остановка

```python
# Graceful shutdown всех компонентов
await victoria.stop()

# Останавливает:
# - File Watcher
# - Service Monitor
# - Deadline Tracker
# - Skills Watcher
# - Event Bus
```

---

## ❓ Часто задаваемые вопросы

### Q: Как проверить, что все работает?

A: Проверьте статус:

```python
status = await victoria.get_status()
assert status["monitoring_started"] == True
assert status["event_bus_available"] == True
assert status["skill_registry_available"] == True
```

### Q: Как добавить свой skill?

A: Создайте директорию с `SKILL.md`:

```bash
mkdir -p ~/.atra/skills/my-skill
cat > ~/.atra/skills/my-skill/SKILL.md << EOF
---
name: my-skill
description: Мой skill
version: 1.0.0
---

# My Skill

Описание skill...
EOF
```

Victoria автоматически загрузит его при следующем запуске.

### Q: Как отключить мониторинг?

A: Установите переменные окружения:

```bash
export ENABLE_EVENT_MONITORING=false
export FILE_WATCHER_ENABLED=false
export SERVICE_MONITOR_ENABLED=false
```

### Q: Где хранятся checkpoints state machines?

A: По умолчанию: `~/.atra/state_machines/`

Можно изменить через:

```python
config = StateMachineConfig(
    persistence_path="/custom/path"
)
```

---

## 📚 Дополнительная документация

- **Полная реализация:** `VICTORIA_INITIATIVE_AND_SELF_EXTENSION_COMPLETE.md`
- **План:** `.cursor/plans/victoria_initiative_and_self-extension_6e6341e6.plan.md`
- **Event Bus:** `knowledge_os/app/event_bus.py`
- **Skill Registry:** `knowledge_os/app/skill_registry.py`
- **State Machines:** `knowledge_os/app/skill_state_machine.py`

---

## ✅ Чеклист активации

- [ ] Применить миграцию БД (`add_skills_tables.sql`)
- [ ] Установить зависимости (`pip install watchdog`)
- [ ] Установить переменные окружения
- [ ] Запустить Victoria Enhanced с `await victoria.start()`
- [ ] Проверить статус через `await victoria.get_status()`
- [ ] Проверить логи на ошибки
- [ ] Протестировать создание файла (должен сработать File Watcher)
- [ ] Протестировать падение сервиса (должен сработать Service Monitor)

---

**Готово! Victoria теперь проактивный агент с инициативой и саморасширением!** 🎉
