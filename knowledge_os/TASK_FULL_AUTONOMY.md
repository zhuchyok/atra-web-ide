# ATRA Corporation: Full Multi-Agent Autonomy — Master Plan

**Дата:** 2026-09-02
**Статус:** IN PROGRESS
**Приоритет:** CRITICAL

---

## Executive Summary

Система ATRA имеет зрелую мультиагентную архитектуру с 32 экспертами, но работает на 60% автономности. Основные пробелы: изолированные агенты, отсутствие collective memory в hot path, мёртвый код который нужно интегрировать, и нет feedback loops.

**Цель:** Довести автономность до 95% за 5 фаз.

---

## Текущее состояние (Что УЖЕ работает)

### Активные компоненты (CORE)
| Компонент | Статус | Доказательство |
|-----------|--------|----------------|
| `event_bus.py` + `event_bus_redis_bridge.py` | CORE | 10+ модулей зависят |
| `smart_worker_autonomous.py` (3267 строк) | CORE | Основной worker |
| `enhanced_orchestrator.py` (3016 строк) | CORE | 18 фаз, запуск каждые 5мин |
| `agent_messaging.py` | ACTIVE | Используется expert_worker (3 места) |
| `consensus_agent.py` | ACTIVE | ai_core, dialogue, swarm |
| `self_check_system.py` | ACTIVE | 4 точки импорта |
| `medic/` (watchdog + repair + main) | ACTIVE | Независимый процесс |
| `nightly_learner.py` | ACTIVE | Background daemon |
| `department_heads_system.py` | ACTIVE | 5+ модулей |
| `resource_manager.py` | ACTIVE | 5 модулей (distributed locking) |
| `recursive_evolution.py` + `perpetual_evolution.py` | ACTIVE | Генетический алгоритм |

### Мёртвый код (требует интеграции)
| Файл | Строк | Что делает | Причина мёртвости |
|------|-------|------------|-------------------|
| `streaming_orchestrator.py` | 614 | Event-driven оркестрация через Redis Streams | 0 импортов |
| `autonomous_policy_enforcer.py` | 72 | Динамические права по KPI | 0 импортов |
| `autonomous_tester.py` | 121 | Ночной QA: pytest + auto-fix | 0 импортов |
| `hierarchical_orchestration.py` | 578 | Иерархические goal trees | Только тесты |
| `intelligence_consensus.py` | 115 | Dual-model consensus | Только тесты |
| `collective_memory.py` | 488 | Stigmergy-based shared memory | Только v2_swarm variant |

---

## PHASE 1: Wire Collective Memory into Hot Path (Неделя 1)

**Цель:** Эксперты начинают делиться знаниями через stigmergy traces.

### Задачи:
1. **Интегрировать `collective_memory.py` в `smart_worker_autonomous.py`**
   - При завершении задачи: записать trace (что сделано, что узнали)
   - При старте задачи: читать relevant traces из той же "location"
   - Добавить memory lookup в task routing

2. **Добавить collective memory в `enhanced_orchestrator.py`**
   - Перед.assigning задачей: проверить есть ли traces от других экспертов
   - Если expert A уже решал похожую задачу — дать expert B его инсайты

3. **Создать `memory_bridge.py`**
   - Мост между EventBus и collective_memory
   - При событии TASK_COMPLETED → создать trace
   - При событии TASK_STARTED → найти relevant traces

### Метрика успеха:
- Каждая завершённая задача создаёт trace
- Каждая новая задача ищет relevant traces
- Время решения повторяющихся задач снижается на 20%+

---

## PHASE 2: Revive Dead Code — Inter-Process Communication (Неделя 1-2)

**Цель:** Агенты общаются через Redis Streams, а не через PostgreSQL.

### Задачи:
1. **Интегрировать `streaming_orchestrator.py`**
   - Заменить polling-based оркестрацию на event-driven
   - Expert workers подписываются на streams
   - Оркестратор публикует события через streams

2. **Интегрировать `autonomous_policy_enforcer.py`**
   - При каждом task assignment: проверить policy permissions
   - Expert с низким KPI не получает сложные задачи
   - Expert с высоким KPI получает доступ к мутациям кода

3. **Интегрировать `autonomous_tester.py`**
   - Запускать pytest каждую ночь
   - При failures: auto-generate fix tasks для экспертов
   - Логировать результаты в collective memory

### Метрика успеха:
- Expert workers получают tasks через Redis streams (не polling)
- Policy violations блокируются автоматически
- Автоматические тесты запускаются nightly и создают tasks при failures

---

## PHASE 3: Feedback Loops — Learning from Outcomes (Неделя 2-3)

**Цель:** Система учится на ошибках и меняет стратегию.

### Задачи:
1. **Создать `feedback_engine.py`**
   - Следить за success/failure rates по типам задач
   - Если тип X проваливается 3+ раза → изменить подход
   - Автоматически обновлять expert weights в consensus_agent

2. **Интегрировать `intelligence_consensus.py`**
   - Для критических решений: dual-model verification
   - Local + Cloud модели сравнивают ответы
   - Disagreement → escalation to Victoria

3. **Создать `strategy_adjuster.py`**
   - Анализировать что работает, что нет
   - Динамически менять: model selection, timeout values, retry policies
   - Публиковать изменения через EventBus

### Метрика успеха:
- Error rate по типам задач снижается на 30%+
- Strategy changes происходят автоматически
- Expert weights обновляются на основе реальных KPI

---

## PHASE 4: Autonomous Task Initiation (Неделя 3-4)

**Цель:** Корпорация сама инициирует работу без человека.

### Задачи:
1. **Расширить `autonomous_overseer.py`**
   - Мониторить Prometheus/Grafana alerts
   - При anomaly detection → создавать tasks
   - При knowledge gap → запускать research tasks

2. **Создать `webhook_receiver.py`**
   - HTTP endpoint для external triggers
   - GitHub webhooks → code review tasks
   - Monitoring alerts → incident response tasks

3. **Интегрировать `hierarchical_orchestration.py`**
   - Decompose goals into subtasks
   - Track dependencies between tasks
   - Visualize hierarchy

### Метрика успеха:
- 50%+ tasks генерируются autonomous (без человека)
- External triggers обрабатываются автоматически
- Goal decomposition работает для complex tasks

---

## PHASE 5: Full Integration — The Corporation Comes Alive (Неделя 4-5)

**Цель:** Все компоненты работают вместе как единая система.

### Задачи:
1. **Unified EventBus Pipeline**
   - Все процессы публикуют и слушают события
   - Medic публикует repair events
   - Orchestrator реагирует на все события
   - Collective memory обновляется от всех событий

2. **Expert Emotion System**
   - Интегрировать `emotion_detector.py`, `curiosity_engine.py`, `mentorship_engine.py`
   - Experts имеют persistent emotional states
   - Emotions влияют на decision-making

3. **Autonomous Corporation Dashboard**
   - Real-time status всех компонентов
   - Expert activity feed
   - Collective memory visualization
   - Strategy adjustment timeline

### Метрика успеха:
- Все компоненты связаны через EventBus
- Experts имеют эмоции и влияют на решения
- Dashboard показывает реальное состояние корпорации

---

## Implementation Notes

### Не трогать (working as-is):
- `ai_core.py` — core LLM pipeline
- `ai_pipeline.py` — prompt engineering
- `dialogue_controller.py` — expert routing
- `mlx_api_server.py` — model serving
- `local_router.py` — model routing

### Осторожно рефакторить:
- `enhanced_orchestrator.py` — 3016 строк, core brain
- `smart_worker_autonomous.py` — 3267 строк, main worker
- `expert_worker.py` — worker process

### Мёртвый код — кандидаты на удаление:
- `singularity_autonomous.py` — заменён shell scripts
- Дублирующие модули (проверить перед удалением)

---

## Risk Mitigation

1. **Каждое изменение через PR + tests**
2. **Постепенная интеграция (не все сразу)**
3. **Rollback plan для каждого phase**
4. **Мониторинг после каждого изменения**
5. **Medic следит за здоровьем системы**

---

## Success Criteria

| Метрика | Сейчас | Цель |
|---------|--------|------|
| Autonomous task initiation | ~10% | 50%+ |
| Expert communication | 0% (isolated) | 80%+ tasks use collective memory |
| Dead code utilization | 0% | 80%+ wired in |
| Error recovery | Manual restart | Auto-repair + learning |
| Strategy adaptation | Static | Dynamic based on outcomes |
| Inter-process messaging | PostgreSQL polling | Redis Streams |
