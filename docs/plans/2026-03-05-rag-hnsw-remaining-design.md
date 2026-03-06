# Дизайн: закрытие пунктов «HNSW индекс» и «Параметры RAG под скорость»

**Дата:** 2026-03-05  
**Контекст:** Таблица «Что осталось сделать» — два конкретных шага (HNSW, RAG-параметры). Режимы /expert и /brainstorm.

---

## 1. Scope

- **HNSW индекс:** Убедиться, что миграция `add_hnsw_index_knowledge_nodes.sql` применена на всех средах, где работает RAG; проверка — `knowledge_os/scripts/verify_hnsw_index.py` (exit 0).
- **Параметры RAG под скорость:** Опционально выставить в `.env` (или в переменных сервиса Victoria) `RAG_CONTEXT_LIMIT`, `RAG_SNIPPET_CHARS`; зафиксировать в `.env.example` с комментарием.

---

## 2. Runbook (конкретные шаги)

### HNSW индекс (приоритет: средний)

1. **Применить миграции** (если ещё не применены):  
   `cd knowledge_os && [DATABASE_URL=...] .venv/bin/python scripts/apply_migrations.py`  
   Миграция `add_hnsw_index_knowledge_nodes.sql` лежит в `db/migrations/` и подхватывается `apply_migrations.py`.
2. **Проверить наличие индекса:**  
   `cd knowledge_os && python3 scripts/verify_hnsw_index.py`  
   **Exit 0** — индекс есть; **exit 1** — применить миграции или вручную:  
   `psql $DATABASE_URL -f knowledge_os/db/migrations/add_hnsw_index_knowledge_nodes.sql`
3. На текущей среде проверка уже выполнена: индекс `knowledge_nodes_embedding_hnsw_idx` присутствует.

### Параметры RAG под скорость (приоритет: низкий)

- В `victoria_server.py` используются: `RAG_CONTEXT_LIMIT` (по умолчанию 5), `RAG_SNIPPET_CHARS` (по умолчанию 500).
- Меньше значений — меньше токенов в промпте, быстрее первый токен.
- **Действие:** при желании в `.env` выставить, например:  
  `RAG_CONTEXT_LIMIT=3`, `RAG_SNIPPET_CHARS=300`.  
  В `.env.example` добавить закомментированные строки с кратким комментарием (скорость vs полнота контекста).

---

## 3. Критерии успеха

- **HNSW:** На всех средах с Knowledge OS выполнение `verify_hnsw_index.py` даёт exit 0.
- **RAG:** При необходимости под скорость — переменные заданы; в `.env.example` они описаны (опционально).

---

## 4. Документация

- В **HOW_TO_INDEX** или **VERIFICATION_CHECKLIST_OPTIMIZATIONS** добавить подпункт:  
  «HNSW индекс: миграции применяются при старте Knowledge OS (или вручную `apply_migrations.py`); проверка — `cd knowledge_os && python3 scripts/verify_hnsw_index.py` (exit 0). Параметры RAG под скорость — см. .env.example (RAG_CONTEXT_LIMIT, RAG_SNIPPET_CHARS).»

---

## 5. Следующий шаг

По правилу /brainstorm: **только writing-plans** — создать план внедрения (конкретные задачи, без перехода к коду до одобрения плана).
