# Per-task isolation (overflow adopt + RAG namespace) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overflow-слот, принявший чужого эксперта, отвечает только на текущую задачу: без чужой памяти, без чужого RAG, без смешанных judge-оценок.

**Architecture:** Не выключаем `EXPERT_POOL_MODE` и не добавляем фреймворки. Расширяем уже доказанный паттерн v149.13 (`copy.copy` на run) на adopt-путь воркера и протаскиваем `task_id`/`expert_name` через `contextvars` в RAG/crystals/judge. Мозг остаётся `11434 victoria-qwen38`; руки `11437`.

**Tech Stack:** Python 3, `contextvars`, `expert_worker.py`, `ai_core.py`, `ai_pipeline.py`, PostgreSQL `knowledge_nodes`/`tasks`, Redis streams overflow, pytest.

## Global Constraints

- Мозг: Ollama `11434` / `victoria-qwen38:latest` (`VICTORIA_MLX_BRAIN=false`).
- Руки: Ollama `11437` / `phi3.5` + `nomic-embed-text`. Не слать эмбеды на 11434.
- Не ставить CrewAI/LangGraph/Weaver/NOMAD.
- Не выключать overflow-пул: без него 80+ экспертов сиротеют в dedicated streams.
- Env-гейты для отката: `WORKER_TASK_ISOLATION=true`, `RAG_NAMESPACE_FILTER=true`.
- Quality-first: задача может ждать мозг; не резать timeout ради скорости.
- Тесты сначала (TDD) на изоляцию adopt и RAG-фильтр.

---

## Approaches considered

| ID  | Подход                                           | Плюс                     | Минус                           | Решение          |
| --- | ------------------------------------------------ | ------------------------ | ------------------------------- | ---------------- |
| A   | contextvars + per-task clone на adopt (v149.13+) | KISS, уже есть прецедент | надо протащить через ai_core    | **Рекомендован** |
| B   | Выключить pool / по воркеру на эксперта          | идеальная изоляция       | 80 контейнеров, RAM, не влезает | Отклонён         |
| C   | Новый оркестратор (LangGraph/Weaver)             | красивая теория          | ломает STUB-GUARD/порты         | Отклонён         |

---

## File map

- `knowledge_os/app/task_isolation.py` _(новый)_ — `contextvars` + helpers `bind_task_context()` / `current_task_context()`.
- `knowledge_os/app/expert_worker.py` — adopt-путь: bind context, сброс skills/session cache, не оставлять `expert_name` процесса как state следующей задачи.
- `knowledge_os/app/ai_core.py` — RAG SQL: кроме `NOT (metadata ? 'task_id')` фильтр по `expert_id`/`domain_id`/source allowlist.
- `knowledge_os/app/ai_pipeline.py` — crystals: operational skip уже есть; добавить expert-scope если колонка есть, иначе deny-regex + skip.
- `knowledge_os/app/expert_worker.py` `judge_gate_score` — не судить, если question/answer из разных task_id.
- `knowledge_os/tests/test_task_isolation.py` _(новый)_ — adopt не тащит прошлый prompt.
- `knowledge_os/tests/test_ai_core_similarity_cutoff.py` — расширить namespace-фильтром.
- `docs/MASTER_REFERENCE.md` + `docs/CHANGES_FROM_OTHER_CHATS.md` — § после внедрения.

Волна GPU-priority (`bastion`/`ollama-queue-proxy` идеи) и `json_repair` — **отдельные планы**, не этот файл.

---

## Task 1: Baseline (факты до кода)

**Files:** none (ops)

- [x] Снять срез: `python3 scripts/scan_system_status.py`
- [x] `11434/api/ps` = только qwen38; `11437/api/ps` = phi+nomic
- [x] За 48ч: кто assignee, сколько overflow adopt в логах `🔄 [POOL] Adopting`
- [x] Сохранить JSON в `docs/audits/2026-11-02-isolation-baseline.json`

**Done when:** файл baseline есть, цифры не из памяти.

---

## Task 2: TDD — contextvar не протекает между задачами

**Files:** `knowledge_os/app/task_isolation.py`, `knowledge_os/tests/test_task_isolation.py`

- [x] Написать тест: bind task A, потом task B в том же «процессе» → `current_task_context().task_id == B`, A не виден.
- [x] Прогнать — красный.
- [x] Реализовать `TaskContext(task_id, expert_name, source, domain_id)` на `contextvars`.
- [x] Тест зелёный.

**Done when:** `pytest knowledge_os/tests/test_task_isolation.py -q` pass.

---

## Task 3: Adopt-путь не мутирует worker identity

**Files:** `knowledge_os/app/expert_worker.py` ~3965

Сейчас: `expert_name = payload_expert` **перезаписывает** имя воркера на всю оставшуюся жизнь цикла.

- [x] Тест: worker «Инна» adopt «Ксения» для task-1, затем task-2 без expert → не остаётся Ксения.
- [x] В adopt: `run_expert_name = payload_expert`, **не** присваивать в замыкание цикла навсегда.
- [x] `async with bind_task_context(...)` вокруг `process_task`.
- [x] После задачи: сброс локальных кэшей skills/description injection (не оставлять `_expert_skills_context` в payload следующего сообщения).

**Done when:** unit-тест adopt identity + лог `Adopting` содержит `task_id` и `restore_worker=Инна`.

---

## Task 4: RAG namespace (код, не дисциплина модели)

**Files:** `knowledge_os/app/ai_core.py` ANN-запрос ~1472

Уже есть: `AND NOT (metadata ? 'task_id')`, `RAG_MIN_SIMILARITY=0.45`.

Добавить (env `RAG_NAMESPACE_FILTER=true`):

- [x] Тест: чанк с `metadata.expert_name=Юлия` не попадает в контекст задачи Ксении.
- [x] Тест: чанк без expert_name (проектный док) допускается, но оборачивается маркером «СПРАВОЧНЫЙ КОНТЕКСТ (не задание)».
- [x] SQL/Python фильтр: drop rows where `metadata.expert_name` set AND != current expert.
- [x] Маркер контекста уже обсуждался в v149.64 — проверить что он жив; если нет — одна обёртка в сборке промпта.

**Done when:** pytest namespace + один живой QC overflow (Инна/Юлия/Ксения) без ответа на чужой вопрос.

---

## Task 5: Crystals — не изобретать, дожать env

**Files:** `knowledge_os/app/ai_pipeline.py` (код уже есть), compose env

Уже есть: `AI_PIPELINE_CRYSTALS_SKIP_OPERATIONAL` default true, deny-regex PgBouncer, тесты `test_memory_crystals_gating.py`.

- [x] Проверить, что воркеры **реально** видят эти env (compose, не только default в коде).
- [x] `pytest knowledge_os/tests/test_memory_crystals_gating.py -q`
- [x] Если колонки `expert_name` в `memory_crystals` нет — **не** мигрировать в этой волне. Хватит skip operational + deny-regex.
- [x] QC операционной задачи: в промпт-логе нет `💎 ПАМЯТЬ ПРОЕКТА` / PgBouncer.

**Done when:** gating-тесты green; compose/env подтверждены `docker exec ... env | rg CRYSTALS`.

---

## Task 6: Judge не оценивает смешанную пару

**Files:** `knowledge_os/app/expert_worker.py` `judge_gate_score`

- [x] Тест: question.task_id != answer.task_id → fail-open без score 9.0.
- [x] В мета задачи писать `judge_skipped=context_mismatch`.
- [x] Не регенерировать по чужому фидбеку.

**Done when:** pytest + в логах `JUDGE-GATE skip mismatch`.

---

## Task 7: Живой QC overflow

**Не** гонять мозг зря. Одна задача:

- [x] Поставить overflow-эксперту задачу A (агрегация / свой домен).
- [x] Сразу после — задачу B другому эксперту на том же dynamic-слоте.
- [x] Критерий: ответ B не содержит уникальных маркеров задачи A (`attack_report`, ИНН/ОГРН, PgBouncer crystals).
- [x] `scan_system_status`: stuck=0; 11434 всё ещё только qwen38.

**Done when:** QC-отчёт в `docs/audits/2026-11-02-isolation-qc.md`.

---

## Task 8: Библия

- [x] § v150.70 в `docs/MASTER_REFERENCE.md` и `docs/CHANGES_FROM_OTHER_CHATS.md`
- [ ] Коммит только файлов волны (не чужой dirty tree)

**Done when:** коммит по запросу владельца.

---

## Out of scope (следующие планы)

1. **GPU priority на 11437** — идеи bastion / ollama-queue-proxy: interactive vs background. Не мешать с изоляцией.
2. **json_repair + num_predict** для обрезанного JSON Глеба.
3. Consilium как дефолт для code/security — отдельно, мозг np=1.

---

## Rollback

- `WORKER_TASK_ISOLATION=false` → старый adopt (перезапись expert_name).
- `RAG_NAMESPACE_FILTER=false` → только текущий task_id + similarity cut-off.
- Crystals: `AI_PIPELINE_CRYSTALS_SKIP_OPERATIONAL=false` вернёт старое поведение.

## Pre-mortem

1. Overflow перестанет брать чужие задачи → сироты в dedicated streams. Страховка: pool остаётся, меняется только state.
2. RAG станет пустым → модель без контекста. Страховка: fallback top-k как у similarity cut-off; проектные доки без expert_name остаются.
3. contextvar не дойдёт до RAG (другой thread). Страховка: тест + копировать context в metadata задачи явно.
