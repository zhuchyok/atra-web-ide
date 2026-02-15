# Архитектура подключения экспертов

**Цель:** единый источник истины, предсказуемая цепочка от добавления сотрудника до использования в оркестрации и промптах, с заделом на рост системы и нагрузки.

**Обновлено:** 2026-02-09

---

## 1. Источник истины и цепочка данных

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ЕДИНЫЙ ИСТОЧНИК: configs/experts/employees.json                             │
│  (name, role, department; при добавлении — один файл, один коммит)           │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  СИНХРОНИЗАЦИЯ: python scripts/sync_employees.py                             │
│  Обновляет: _known_names_generated.py, seed_experts.json, employees.md       │
│  (при коммите — опционально pre-commit: install_git_hooks.sh)               │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          ▼                             ▼                             ▼
┌──────────────────┐    ┌──────────────────────────────┐    ┌──────────────────┐
│ seed_experts.json │    │ БД в Docker (knowledge_     │    │ .cursor/rules/   │
│ (role, department,│    │ postgres): таблица experts  │    │ team.md         │
│ system_prompt)    │    │ 86+ экспертов — оркестратор,│    │ Роли ↔ файлы    │
│                   │    │ дашборд, назначение задач   │    │ правил          │
└──────────────────┘    └──────────────────────────────┘    └──────────────────┘
          │                             │
          │   (применение seed в БД:    │
          │   server_knowledge_sync,     │
          │   или ручной UPSERT из      │
          │   seed_experts.json)        │
          └────────────────────────────┘
```

**Где эксперты в рантайме:** таблица `experts` живёт в **PostgreSQL в Docker** (контейнер `knowledge_postgres`, БД `knowledge_os`). Сервисы Knowledge OS (API, оркестратор, воркер, Victoria-agent) в Docker подключаются к этой БД по `DATABASE_URL` и читают/пишут экспертов и задачи там. То есть **эксперты в рантайме — в Docker** (БД); репозиторий (employees.json, seed) — источник для синхронизации в эту БД.

**Правило:** новый сотрудник добавляется **только** в `employees.json`, затем запускается `sync_employees.py`. Остальные артефакты (seed, KNOWN_NAMES, employees.md) генерируются. В БД (Docker) эксперты попадают через применение seed или синк (server_knowledge_sync / золотой образ).

---

## 2. Кто и как использует экспертов (consumers)

| Потребитель | Что нужно | Откуда берёт | Масштаб при росте |
|-------------|-----------|--------------|-------------------|
| **Промпты, планы, Swarm/Consensus** | Список имён и ролей для вставки в промпт | **expert_services** (get_all_expert_names, get_expert_services_text) = employees.json + БД, кэш БД 60 с | Один модуль, TTL конфигурируемый |
| **Department Heads** | Глава отдела по имени отдела | **department_heads_system.py** (DEPARTMENT_HEADS dict; при росте — можно грузить из JSON/БД) | Сейчас константа; при 50+ отделах — загрузка из seed/БД |
| **Назначение задач, workload** | Лучший эксперт по домену/категории, нагрузка | **БД** (experts, tasks): enhanced_orchestrator (get_best_expert_for_domain, assign_task_to_best_expert), **ExpertMatchingEngine** (find_best_expert_for_task) | Запросы к БД; при росте — пул, индексы, опционально кэш нагрузки |
| **Victoria Enhanced** | Имена для swarm (до 16), consensus (до 10) | **expert_services.get_all_expert_names(max_count=…)** | Уже ограничено max_count |
| **IntegrationBridge (orchestrator)** | Рекомендация исполнителя | **ExpertMatchingEngine** по категории задачи | Один вызов на задачу |
| **Воркер (smart_worker_autonomous)** | system_prompt, role по имени | **БД** (SELECT FROM experts WHERE name = $1) | По имени; кэш по имени при необходимости |
| **Expert council / discussion** | Список по отделу, по релевантности | **БД** (expert_council_discussion, get_experts_by_department) | Отдельные запросы |

**Единая точка входа для «список для промптов»:** только **expert_services**. Для «назначить задачу / workload» — только **БД** (оркестратор, ExpertMatchingEngine, воркер). Дублирования источников для одного и того же использования нет.

---

## 3. Кэширование и нагрузка

- **expert_services:** загрузка из БД кэшируется на **60 с** по умолчанию; TTL настраивается через env **EXPERT_SERVICES_DB_TTL** (секунды). Файл employees.json кэшируется на время жизни процесса.
- **Рост нагрузки:** при высокой нагрузке уменьшить TTL или добавить слой (например Redis) по необходимости.
- **БД:** оркестратор и ExpertMatchingEngine ходят в PostgreSQL; при росте числа задач — пул соединений (уже есть), индексы по experts(department), experts(role), tasks(assignee_expert_id).

---

## 4. Добавление нового эксперта (runbook)

1. Добавить запись в **configs/experts/employees.json** в массив `employees`: `{"name": "Имя", "role": "Роль", "department": "Отдел"}`.
2. Запустить **`python scripts/sync_employees.py`** (или положиться на pre-commit после `./scripts/install_git_hooks.sh`).
3. При необходимости добавить роль в **.cursor/rules/** и связь в **configs/experts/team.md** (таблица «Связь с .cursor/rules»).
4. **БД:** применить seed в окружение (server_knowledge_sync, или скрипт применения seed_experts.json к PostgreSQL), чтобы оркестратор и воркер видели нового эксперта.

После этого эксперта видят: Victoria (через expert_services), оркестратор и воркер (через БД), Department Heads (если его отдел уже есть в DEPARTMENT_HEADS или загружается из данных).

---

## 5. Связь с другими документами

- **configs/experts/team.md** — роли, алиасы, связь с .cursor/rules; оттуда же ссылка на этот документ.
- **docs/TEAM_PERSONALITIES.md** — характеры и стиль экспертов для промптов.
- **VERIFICATION_CHECKLIST_OPTIMIZATIONS.md** — при изменениях в оркестрации/назначении экспертов проверять тесты и этот документ.
- **MASTER_REFERENCE.md** — раздел про экспертов и команду ссылается сюда.

При изменении цепочки (новый источник экспертов, новый потребитель) — обновить этот документ и при необходимости §5 «При следующих изменениях» в VERIFICATION_CHECKLIST.
