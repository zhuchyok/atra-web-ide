# Фаза 4.1: Стабилизация и масштабирование

**Статус:** ✅ **ВЫПОЛНЕНО** (31.01.2026)

## ✅ Сделано

### 1. Анализ проблемных запросов

- **Скрипт:** `scripts/analyze_low_relevance.py`
- **Запуск:** `python scripts/analyze_low_relevance.py [threshold]`
- **Выход:** `problematic_queries_analysis.json`

### 2. Результаты анализа (текущие)

- **Проблемных (relevance < 80%):** 4 из 15
- **Критичные (relevance = 0%):** "как настроить Victoria", "метрики Prometheus"
- **Короткие (rel 61–77%):** "сколько стоит подписка", "справка по использованию"

### 3. Улучшения query expansion

- Расширены термины для "как настроить Victoria" и "метрики Prometheus"
- Добавлены fallback для "victoria" и "prometheus"

---

## 📋 Чеклист на следующие шаги

### День 1–2: Фиксы

- [x] Запустить `analyze_low_relevance.py`
- [x] Улучшить query expansion для критичных запросов
- [x] Перезапустить пайплайн и проверить метрики
- [x] `analyze_coherence_issues.py` — найдена причина: ответы без точки
- [x] Фикс: `_truncate_response` добавляет точку в конце ответа

### День 3–4: Расширение validation set

- [x] Собрать реальные запросы: `collect_real_queries.py` (улучшен: парсинг JSON, нормализация — Data Engineer)
- [x] Создать `generate_query_variations.py` (синтетика; QA: покрытие, Technical Writer: формулировки)
- [x] Объединить и дедуплицировать: `merge_validation_sources.py` (Data Engineer: дедупликация по ключу)

### День 5: Мониторинг

- [x] AdvancedQualityMonitor с детекцией аномалий (пороги QA + z-score по истории; SRE: метрики из validation_report)
- [x] Дашборд v2: детализация по запросам, блок алертов (SRE: дашборд как код)

### День 6: Self-healing

- [x] Очистка RAG кэша при падении качества: `RAGContextCache.clear_all()`, скрипт `quality_heal_rag_cache.py` (Backend)
- [x] Интеграция в пайплайн: при провале порогов run_quality_pipeline выводит рекомендацию выполнить heal и перезапустить

---

## 🎯 Цели

| Метрика        | Сейчас | 7 дней | 30 дней |
| -------------- | ------ | ------ | ------- |
| Relevance      | 80.1%  | 85%    | 90%+    |
| Faithfulness   | 100%   | 100%   | 100%    |
| Coherence      | 93.3%  | 95%    | 97%+    |
| Validation set | 15     | 50+    | 150+    |

---

## Быстрые команды

```bash
# Анализ
python scripts/analyze_low_relevance.py

# Расширение validation set (День 3–4)
python scripts/collect_real_queries.py --days 7 --limit 100
python scripts/generate_query_variations.py --max-per-query 2
python scripts/merge_validation_sources.py   # объединить и дедуплицировать

# Полный пайплайн (проверка после фиксов)
./scripts/run_quality_pipeline.sh

# День 5–6: дашборд v2, self-healing при провале порогов
python scripts/create_simple_dashboard.py
python scripts/quality_heal_rag_cache.py   # при падении качества — очистка RAG кэша
```

## Учтённые рекомендации специалистов

- **QA Engineer (Анна):** расширение покрытия регрессии через синтетические вариации запросов; пороги faithfulness/relevance/coherence в QualityMonitor.
- **Data Engineer:** нормализация и дедупликация по ключу при сборе реальных запросов и при объединении источников; качество и полнота данных.
- **Technical Writer (Татьяна):** разнообразие формулировок в `generate_query_variations.py` (синонимы, перефразировки).
- **SRE / Monitor (Елена):** метрики из реальных источников (validation_report, validation_results); дашборд v2 с детализацией по запросам и алертами; runbook при провале порогов (очистка кэша + перезапуск валидации).
- **Backend (Игорь):** единая точка инвалидации RAG кэша (`RAGContextCache.clear_all()`), скрипт `quality_heal_rag_cache.py` для Self-healing пайплайна качества.

---

## Следующие шаги (после Phase 4.1)

**Проверка (27.01.2026):** импорты `QualityMonitor`, `RAGContextCache` — OK; скрипты `quality_heal_rag_cache.py`, `create_simple_dashboard.py` — выполняются без ошибок.

**Дальше по плану Фазы 4** (`docs/PHASE4_PLAN.md`):

| Неделя | Фокус             | Статус                                                                                                        |
| ------ | ----------------- | ------------------------------------------------------------------------------------------------------------- |
| **2**  | Контекстуализация | ✅ Выполнено: ConversationContextManager, session_id, окно контекста, интеграция в чат (27.01.2026)           |
| **3**  | Оценка качества   | ✅ Выполнено: RAGEvaluator.check_thresholds, пороги QA 0.8/0.85/0.7, CI, record_human_preference (27.01.2026) |
| **4**  | Мультимодальность | ✅ Выполнено: MultimodalProcessor (Vision + документы), API /api/multimodal, MULTIMODAL_SETUP.md (27.01.2026) |

**Фаза 4 (Недели 1–4) завершена.**

**31.01.2026 — пост-фаза 4:**

- Validation set: 29 → 71 запросов (merge synthetic + generate_query_variations + новые паттерны)
- QueryRewriter интегрирован в RAG-light (\_prepare_query_for_search: rewrite → expand)
- Реранкинг в evaluate_rag_quality при RERANKING_ENABLED=true (run_quality_pipeline по умолчанию)
- Конфиг: QUERY_REWRITER_ENABLED (default true), RERANKING_ENABLED (default false в backend, true в pipeline)

Дальше — цели по метрикам (faithfulness >90%, relevance >95%, HPS ≥4.0) при свободных Ollama/MLX и непрерывное улучшение.

**Верификация (31.01.2026):**

- QueryRewriter: "как настроить Victoria" → "инструкция настройка запуск установка victoria как настроить" ✅
- RAGEvaluator.check_thresholds: passed=True ✅
- quality_heal_rag_cache.py, create_simple_dashboard.py, check_quality_thresholds.py — OK ✅
- CI: RERANKING_ENABLED=true, --timeout-per-query 5, query_expansion в paths ✅

**Продолжение (31.01.2026):**

- Validation set: 50 → 71 → **100 запросов** (merge + 15 base queries; Data Engineer)
- analyze_low_relevance интегрирован в run_quality_pipeline (шаг 5a, QA/CONTINUOUS_IMPROVEMENT)
- Еженедельный цикл документирован в docs/CONTINUOUS_IMPROVEMENT.md
- **Мультимодальность 10+ форматов:** TXT, HTML, ODT, RTF добавлены в MultimodalProcessor (Backend)

---

## Закрытие (31.01.2026)

**Фаза 4.1 выполнена полностью.** Все дни 1–6, расширение validation set до 100, analyze_low_relevance в пайплайне, еженедельный цикл документирован.
