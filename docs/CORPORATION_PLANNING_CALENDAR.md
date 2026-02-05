# Календарь автономных циклов корпорации

Единый обзор: **что**, **когда** и **куда пишет результат** для всех автономных процессов. Ссылка из [MASTER_REFERENCE](MASTER_REFERENCE.md) §5.

**Обновлено:** 2026-02-03

---

## Сводная таблица

| Компонент | Расписание | Что делает | Куда пишет результат |
|-----------|------------|------------|----------------------|
| **Enhanced Orchestrator** | Каждые 5 мин (cron) | Назначение, Phase 1.5 декомпозиция, Phase 1.6 batch_group (BATCH_SMALL_TASKS_ENABLED), Cross-Domain, Curiosity | tasks, domains |
| **Smart Worker** | Постоянно (Docker) | Обработка pending задач; при SMART_WORKER_BATCH_GROUP_LLM — батч по batch_group | tasks (completed/failed) |
| **Nightly Learner** | 6:00 MSK (3:00 UTC) | Обучение экспертов, Debate Processor, Dashboard Improver, Enhanced Expert Evolver | knowledge_nodes, expert_discussions, tasks |
| **Dashboard Daily Improver** | Внутри Nightly Learner | Анализ кода дашборда; при AUTO_APPLY_DASHBOARD=true — авто-патч max_entries; остальное — задачи | tasks |
| **Knowledge Applicator** | Внутри Nightly Learner | lessons→.cursorrules, ретроспективы→knowledge_nodes, инсайты→задачи Prompt Engineer | .cursorrules, knowledge_nodes, tasks |
| **Self-Check System** | По расписанию (start_autonomous_systems) | Проверка Victoria, Veronica, БД, Ollama/MLX, Redis; автофикс; Predictive Monitor (тренды) | Логи; при деградации — задачи; при порогах (stuck/pending) — predictive задачи |
| **Autonomous Tests (Phase 13)** | Внутри Nightly Learner | pytest test_json_fast_http_client, test_rest_api | knowledge_nodes; при провале — задача (assignee_hint: QA) |
| **Test Generation Tasks (Phase 14)** | Внутри Nightly Learner | git log 24h → изменённые .py без тестов → задачи «Сгенерировать pytest для модуля X» | tasks (assignee_hint: QA) |
| **Auto-Profiling (Phase 15)** | Внутри Nightly Learner (воскресенье) | cProfile json_fast roundtrip x500 → топ-15 функций → knowledge_nodes | knowledge_nodes (source_ref: auto_profiling) |
| **Doc Sync Task (Phase 16)** | Внутри Nightly Learner | git log --merges 24h → при merge → задача «Синхронизировать документацию» | tasks (assignee_hint: Technical Writer) |
| **system_auto_recovery** | Каждые 5 мин (launchd) | Wi‑Fi, Docker, MLX, Ollama, Victoria, Veronica | — |
| **MLX Monitor** | Каждые 30 с | Проверка процесса и health :11435; перезапуск при падении | ~/Library/Logs/atra-mlx-monitor.log |
| **cleanup_old_traces** | Раз в сутки (cron) | Удаление environmental_traces старше TRACES_RETENTION_DAYS (90) | — |

---

## Детали по компонентам

### Enhanced Orchestrator

- **Файл:** `knowledge_os/app/enhanced_orchestrator.py`
- **Запуск:** crontab или `scripts/ensure_autonomous_systems.sh`
- **Фазы:** приоритизация, Phase 1.5 декомпозиция сложных задач (Victoria → подзадачи с parent_task_id), назначение `assign_task_to_best_expert`, Cross-Domain Linker, Curiosity Engine

### Nightly Learner

- **Файл:** `knowledge_os/app/nightly_learner.py`
- **Запуск:** crontab 0 3 * * * (UTC) = 6:00 MSK
- **Фазы:** обучение экспертов, Expert Council (дебаты), Debate Processor, Dashboard Improver, Enhanced Expert Evolver, Knowledge Applicator

### Self-Check System

- **Файл:** `knowledge_os/app/self_check_system.py`
- **Запуск:** `scripts/start_autonomous_systems.sh`
- **Проверяет:** Victoria, Veronica, БД, Ollama, MLX, Redis, саму себя
- **Predictive Monitor (внутри Self-Check):** `predictive_monitor.run_predictive_check` — тренды: stuck in_progress (>15 мин), old pending (>1ч). Пороги: PREDICTIVE_STUCK_COUNT_THRESHOLD=5, PREDICTIVE_PENDING_COUNT_THRESHOLD=30. При превышении → задачи (assignee_hint: SRE). Living Organism §6.

---

### Auto-Profiling (Phase 15)

- **Файл:** `knowledge_os/app/nightly_learner.py`
- **Расписание:** только воскресенье (weekday==6)
- **Назначение:** cProfile на json_fast load/dump roundtrip (500 итераций), топ-15 функций по cumulative time → knowledge_nodes (source_ref=auto_profiling, domain Performance). Living Brain §6.3, AUTO_PROFILING_GUIDE.

### cleanup_old_traces (Retention)

- **Файл:** `knowledge_os/scripts/cleanup_old_traces.py`
- **Назначение:** Удаление environmental_traces старше N дней (TRACES_RETENTION_DAYS=90). OPTIMIZATION_AND_RUST_CANDIDATES, MEMORY_LEAK_FIX_56GB.
- **Cron:** `0 4 * * * cd /path/to/knowledge_os/scripts && python cleanup_old_traces.py`

## Настройка

```bash
# Один раз
bash scripts/setup_system_auto_recovery.sh
bash scripts/ensure_autonomous_systems.sh
```

---

## Связанные документы

- [MASTER_REFERENCE](MASTER_REFERENCE.md) §5 «Автоматика и восстановление»
- [AUTONOMOUS_SYSTEMS_AUTO_START](../AUTONOMOUS_SYSTEMS_AUTO_START.md)
- [HOW_CORPORATION_LEARNS](mac-studio/HOW_CORPORATION_LEARNS.md)
