# Isolation QC v150.70 (2026-11-02) — closed slice

## Code / env

- Tests: **12 passed** (`test_task_isolation`, `test_ai_core_similarity_cutoff`, `test_memory_crystals_gating`).
- Overflow env: `WORKER_TASK_ISOLATION=true` `RAG_NAMESPACE_FILTER=true` `AI_PIPELINE_CRYSTALS_SKIP_OPERATIONAL=true` `EXPERT_POOL_MODE=true`.
- Brain: `11434/api/ps` = `victoria-qwen38:latest` only.
- Hands: nomic embed 11437 **живой** (768-d); **phi generate 11437 wedged** (90s, 0 bytes) — повторный LLM A→B не гоняли.

## 1. Adopt identity — доказано логом

```
🔄 [POOL] Adopting expert 'Юлия' (slot 'Инна') for task 3d2a3876-... restore_worker=Инна
🛠️ Начало выполнения задачи 3d2a3876-... для Юлия
```

Пока Юлия исполнялась на слоте Инна, autonomy слота продолжала `Skip blackboard claim ... assignee is Юлия`. Старый баг оставил бы слот Юлией.

## 2. RAG namespace на живом корпусе — доказано

`knowledge_nodes`: 109 614 всего, **5612 с `metadata.expert_name`** (Юлия 238, Ксения 16). Юлия-ноды — это в том числе `💎 ПАМЯТЬ ПРОЕКТА` / порт 6432 (классический crystal-bleed).

Прогон `filter_namespace_rows` на реальных строках:

| Контекст      | Юлия-crystal                                          | Ксения-owned  |
| ------------- | ----------------------------------------------------- | ------------- |
| expert=Ксения | **не попали** (`CRYSTAL_BLEED_YULIA_TO_KSENIA=false`) | остались      |
| expert=Юлия   | остались                                              | отфильтрованы |

Это закрывает критерий «чужой PgBouncer/crystals не в контексте другого эксперта» на данных, не на дисциплине модели.

## 3. LLM A→B по тексту ответа — не гоняли повторно

| Task                          | status             | почему                                                                           |
| ----------------------------- | ------------------ | -------------------------------------------------------------------------------- |
| isolation-qc-A `b5623b7d-...` | failed             | `docker pause` → orchestrator `nonlive_worker_pending` / stale drop              |
| isolation-qc-B `3d2a3876-...` | failed (abandoned) | 15+ мин `in_progress` без `last_real_progress`; заняла слот и 11434. Снята явно. |

11437 phi generate не отвечает — новый dialogue-QC упёрся бы в те же руки. Не засоряли очередь.

## 4. Judge empty skip

`judge_gate_score`: пустой answer → fail-open `empty_answer`, не score 10.0. Воркеры перезапущены под этот патч.

## Queue after

- Наши QC: оба **failed** (терминальные).
- Open чужие: security `in_progress`, debate `pending`. `stuck_tasks_count=0`.
- Dynamic 1–5 restarted (health starting → healthy).

## Rollback

`WORKER_TASK_ISOLATION=false`, `RAG_NAMESPACE_FILTER=false`. Коммит не делался.
