# Фаза 4: Оптимизация качества ответов RAG (28 дней)

**Статус:** ✅ **ВЫПОЛНЕНО** (31.01.2026)

**Цель:** повысить качество ответов RAG по метрикам faithfulness, relevance, coherence; контекстуализация диалога; оценка качества; мультимодальность.

**Связь с предыдущими фазами:** Фазы 1–3 дали производительность (<50ms простые, 100–200ms фактуальные) и надёжность (rate limiter, кэш, метрики). Фаза 4 фокусируется на **качестве** без деградации латентности.

---

## Обзор по неделям

| Неделя | Фокус | Компоненты | Критерии готовности |
|--------|-------|------------|---------------------|
| **1** | RAG релевантность | Реранкинг, переписывание запросов, гибридный поиск | ✅ Реранкинг, QueryRewriter, validation set 100 |
| **2** | Контекстуализация | История диалога, персонализация, domain adaptation | ✅ ConversationContextManager, session_id, chat |
| **3** | Оценка качества | Векторные метрики, авто-оценка, человеческая оценка | ✅ RAGEvaluator, CI, record_human_preference |
| **4** | Мультимодальность | Изображения, документы, таблицы | ✅ 10+ форматов (PDF, DOCX, TXT, HTML, ODT, RTF) |

---

## Неделя 1: Улучшение RAG релевантности

### Задачи
1. **Validation set:** 100–200 запросов с эталонными ответами (или контекстом) для оценки. ✅ 100 запросов
2. **Реранкинг:** сервис `RerankingService` (cross-encoder / текстовое сходство / гибрид). ✅
3. **Переписывание запросов:** `QueryRewriter` для улучшения поиска (например, «как настроить?» → «инструкция по настройке»). ✅
4. **Интеграция в RAG-light:** опциональный реранкинг и переписывание (feature flag / A/B). ✅

### Файлы
- `backend/app/services/reranking.py` — реранкинг чанков.
- `backend/app/services/query_rewriter.py` — переписывание запроса для RAG.
- `data/validation_queries.json` — validation set.
- `scripts/evaluate_rag_quality.py` — скрипт оценки качества.

### Быстрый старт
```bash
pip install sentence-transformers rank-bm25  # при необходимости
python scripts/evaluate_rag_quality.py --dataset data/validation_queries.json
```

---

## Неделя 2: Контекстуализация ответов

### Задачи
1. **ConversationContextManager:** хранение истории диалога (session_id → сообщения). ✅
2. **Окно контекста:** последние N сообщений + ограничение по символам (max_context_chars). ✅
3. **Персонализация:** учёт предпочтений/домена пользователя. (опционально позже)
4. **Интеграция в chat:** передача контекста в Victoria и в MLX/Ollama. ✅

### Файлы
- `backend/app/services/conversation_context.py` — управление контекстом диалога (in-memory + опционально Redis, TTL).
- `backend/app/routers/chat.py` — поле `session_id` в ChatMessage, контекст в промпте, сохранение user/assistant после ответа.
- Конфиг: `CONVERSATION_CONTEXT_ENABLED`, `CONVERSATION_CONTEXT_TTL_SEC`, `CONVERSATION_CONTEXT_MAX_MESSAGES`, `CONVERSATION_CONTEXT_MAX_CHARS`, `CONVERSATION_CONTEXT_USE_REDIS`.

---

## Неделя 3: Оценка качества

### Задачи
1. **RAGEvaluator:** faithfulness, relevance, coherence, BLEU/ROUGE (при наличии reference). ✅
2. **Авто-оценка:** скрипт + пороги (faithfulness ≥ 0.8, relevance ≥ 0.85, coherence ≥ 0.7). ✅
3. **CI:** запуск оценки на validation set при push/PR (quality-validation.yml). ✅
4. **Человеческая оценка:** сбор Human Preference Score (1–5) для калибровки. ✅

### Файлы
- `backend/app/evaluation/rag_evaluator.py` — оценка ответов, DEFAULT_THRESHOLDS, check_thresholds() (QA).
- `scripts/evaluate_rag_quality.py` — запуск на датасете, порог coherence:0.7, использование RAGEvaluator.check_thresholds.
- `scripts/check_quality_thresholds.py` — проверка отчёта по порогам (по умолчанию 0.8/0.85/0.7).
- `scripts/record_human_preference.py` — запись оценки 1–5 (FeedbackCollector), калибровка.
- `backend/app/services/feedback_collector.py` — get_human_preference_score(days).
- `.github/workflows/quality-validation.yml` — пороги faithfulness:0.8, relevance:0.85, coherence:0.7.

---

## Неделя 4: Мультимодальность

### Задачи
1. **Обработка изображений:** Vision: Moondream Station (MLX) → Ollama (moondream/llava). ✅
2. **Обработка документов:** PDF (PyMuPDF), DOCX (python-docx) → текст для RAG. ✅
3. **Интеграция в основной пайплайн:** маршрутизация по типу контента (detect_content_type, get_text_for_rag). ✅

### Файлы
- `backend/app/services/multimodal_processor.py` — MultimodalProcessor, process_image, extract_document_text, get_text_for_rag.
- `backend/app/routers/multimodal.py` — POST /api/multimodal/process-image, process-document, GET content-type.
- `docs/MULTIMODAL_SETUP.md` — настройка Moondream Station, Ollama, опциональные зависимости (pymupdf, python-docx).

---

## Метрики качества (цели Фазы 4)

| Метрика | Текущее | Цель |
|---------|---------|------|
| Faithfulness (верность контексту) | ~75% | >90% |
| Relevance (релевантность запросу) | ~80% | >95% |
| Coherence (связность ответа) | ~85% | >95% |
| Human Preference Score | — | >4.0/5.0 |
| Multi-turn Success Rate | — | >80% |

---

## Инфраструктура

- **Канареечные развёртывания:** middleware или feature flag для новой модели/конфига (например, 10% трафика).
- **Обратная связь:** `FeedbackCollector` — сохранение рейтинга/комментария по ответу для последующего анализа и ретрайнинга.
- **Откат:** автоматический откат при падении метрик качества ниже порога.

---

## Документация

- **План:** `docs/PHASE4_PLAN.md` (этот файл).
- **Метрики качества:** `docs/QUALITY_METRICS.md`.
- **Мультимодальность:** `docs/MULTIMODAL_SETUP.md`.
- **Непрерывное улучшение:** `docs/CONTINUOUS_IMPROVEMENT.md`.

---

## Приоритеты на ближайшую неделю

1. ~~Создать validation set из 100–200 запросов~~ ✅ 100 запросов (merge + 15 base queries, 31.01.2026)
2. ~~Реализовать базовый реранкинг~~ ✅ RerankingService, интеграция в RAG-light, evaluate с RERANKING_ENABLED
3. ~~Настроить ежедневную/при-PR оценку качества~~ ✅ quality-validation.yml, run_quality_pipeline.sh
4. ~~Собирать обратную связь от пользователей~~ ✅ record_human_preference, FeedbackCollector
5. ~~Интегрировать QueryRewriter в RAG-light~~ ✅ _prepare_query_for_search (rewrite → expand), 31.01.2026

---

## Закрытие фазы (31.01.2026)

**Фаза 4 выполнена полностью.** Все недели 1–4 реализованы. Validation set 100 запросов, мультимодальность 10+ форматов, CI, self-healing, еженедельный цикл в CONTINUOUS_IMPROVEMENT. Дальше — достижение целевых метрик (faithfulness >90%, relevance >95%) при работе Ollama/MLX.
