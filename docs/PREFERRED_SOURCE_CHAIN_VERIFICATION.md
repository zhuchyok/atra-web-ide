# Верификация цепочки preferred_source (оркестратор → воркер → роутер)

**Дата:** 2026-02-03  
**Цель:** убедиться, что preferred_source учитывается везде от и до.

---

## 1. Цепочка от и до

| № | Компонент | Файл | Что делает |
|---|-----------|------|------------|
| 1 | **Orchestrator (assign)** | enhanced_orchestrator.py:375-391 | Назначает preferred_source по отделу эксперта (ML/Backend/R&D → mlx, остальные → ollama). Пишет в task.metadata. |
| 2 | **Orchestrator (rebalance)** | enhanced_orchestrator.py:458-469 | При перераспределении обновляет preferred_source по отделу нового эксперта. |
| 3 | **Worker SELECT** | smart_worker_autonomous.py:749 | SELECT t.metadata — читает metadata из БД. |
| 4 | **Worker distribution** | smart_worker_autonomous.py:795-826 | Читает metadata.preferred_source; если есть — использует; иначе fallback по intelligent_model_router. |
| 5 | **Worker process_task** | smart_worker_autonomous.py:268-276 | Берёт preferred_source из task, устанавливает router._preferred_source. |
| 6 | **ai_core** | ai_core.py:514-517 | Использует router, переданный воркером (local_router с _preferred_source). |
| 7 | **LocalRouter** | local_router.py:775-786 | Читает _preferred_source, ставит предпочтительный узел (MLX/Ollama) в начало списка. |

---

## 2. Проверка покрытия

- [x] **Назначение (assign_task_to_best_expert):** preferred_source пишется в metadata
- [x] **Перераспределение (rebalance_workload):** preferred_source обновляется при смене эксперта
- [x] **Воркер SELECT:** t.metadata в выборке
- [x] **Воркер distribution:** чтение metadata.preferred_source, fallback при отсутствии
- [x] **Воркер process_task:** передача preferred_source в роутер
- [x] **ai_core:** использование router с _preferred_source
- [x] **LocalRouter:** учёт _preferred_source при выборе узла

---

## 3. Граничные случаи

| Случай | Поведение |
|--------|-----------|
| Задача создана с assignee (Victoria, API) | metadata.preferred_source может быть задан создателем; orchestrator не перезаписывает (assign_task не вызывается). Воркер читает metadata. |
| Задача без assignee | Orchestrator вызывает assign_task → пишет preferred_source. |
| metadata.preferred_source уже есть от создателя | Orchestrator уважает (строки 379-383). |
| metadata = null | COALESCE(metadata, '{}') → пустой объект; orch_source = None; fallback по intelligent_model_router. |
| Перераспределение задачи | rebalance обновляет preferred_source по отделу нового эксперта. |

---

*Цепочка верифицирована. При изменениях — обновить этот документ.*
