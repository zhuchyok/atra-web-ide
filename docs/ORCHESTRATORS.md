# Оркестраторы (помимо Victoria)

**Victoria** — главный оркестратор пользовательского запроса (чат, делегирование, план).

Кратко по оркестраторам **помимо Victoria**:

---

## 1. Enhanced Orchestrator

**Файл:** `knowledge_os/app/enhanced_orchestrator.py`

- Фоновый цикл по таблице **tasks** (задачи без исполнителя).
- Назначает задачу лучшему эксперту (`assign_task_to_best_expert`), запускает **Smart Worker** → ai_core → Ollama/MLX.
- Использует блокировку `acquire_resource_lock("orchestrator")`.
- **Запуск:** по расписанию/cron или вручную (`scripts/start_enhanced_orchestrator.sh`), в docker-compose не поднят по умолчанию.

---

## 2. Streaming Orchestrator

**Файл:** `knowledge_os/app/streaming_orchestrator.py`

- Оркестрация по событиям (Redis Streams).
- Обрабатывает события типа INSIGHT_HYPOTHESIS, создаёт задачи на валидацию.
- **Запуск:** отдельный процесс (например, `python streaming_orchestrator.py`).

---

## 3. Orchestrator (базовый)

**Файл:** `knowledge_os/app/orchestrator.py`

- Ещё один оркестратор, использует `LocalAIRouter` и блокировку `acquire_resource_lock("orchestrator")`.
- Цикл `run_orchestration_cycle()`.

---

## 4. Swarm Orchestrator

**Файл:** `knowledge_os/app/swarm_orchestrator.py`

- «Рой» экспертов, консенсус (Swarm War-Room).
- Вызывается **изнутри** Enhanced Orchestrator, не отдельный сервис.

---

## 5. Hierarchical Orchestrator

**Модуль:** `knowledge_os/app/hierarchical_orchestration.py`

- Иерархическая оркестрация, корневой агент — Victoria.
- Используется в **Victoria Enhanced** (`victoria_enhanced.py`).

---

## 6. Query Orchestrator

**Файл:** `knowledge_os/app/query_orchestrator.py`

- В **ai_core**: нормализация запроса, выбор роли, сбор контекста (role-aware промпт).
- Не «оркестратор задач», а оркестрация обработки одного запроса.

---

## 7. Parallel Orchestrator

**Файл:** `knowledge_os/app/parallel_orchestrator.py`

- Разбивает сложные задачи на подзадачи и запускает экспертов **параллельно** (ai_core).
- Часть Singularity v4.1 (Performance Leap).

---

## Итого

| Оркестратор | Роль | Запуск |
|-------------|------|--------|
| **Victoria** | Чат, запросы, план, делегирование | Сервис (порт 8010) |
| **Enhanced Orchestrator** | Фон по tasks, назначение эксперту, Smart Worker | Cron / вручную |
| **Streaming Orchestrator** | События Redis, гипотезы → задачи | Отдельный процесс |
| **orchestrator.py** | Базовый цикл, LocalAIRouter | Вручную |
| **SwarmOrchestrator** | Консенсус экспертов | Внутри Enhanced |
| **HierarchicalOrchestrator** | Иерархия, Victoria корень | Внутри Victoria Enhanced |
| **QueryOrchestrator** | Один запрос: роль, контекст | В ai_core |
| **ParallelOrchestrator** | Параллельные подзадачи | По вызову |
