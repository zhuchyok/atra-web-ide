# TODO/FIXME Backlog (приоритизация)

**Дата:** 2026-02-05  
**Источник:** PROJECT_GAPS_ANALYSIS §1, метод «решайте с командой».  
**Цель:** приоритизировать TODO/FIXME по критичности; закрывать в рамках задач или выносить в backlog. В коде рядом с каждым TODO добавлена ссылка: `# See docs/TODO_FIXME_BACKLOG.md`.

---

## Закрыто (вне плана)

| Тема | Контекст |
|------|----------|
| **web_search_fallback Ollama** | П.6 PRINCIPLE_EXPERTS_FIRST: после DuckDuckGo добавлен fallback на Ollama web_search при OLLAMA_API_KEY (POST ollama.com/api/web_search). Закрыто 2026-02-08. См. CHANGES §0.4ee. |
| **Куратор при деплое** | После деплоя один раз прогнать быстрый прогон куратора и сравнение с эталонами. Добавлено: [CURATOR_RUNBOOK.md](CURATOR_RUNBOOK.md) §1.5 «Куратор при деплое», скрипт `scripts/run_curator_post_deploy.sh`, строка в [HOW_TO_INDEX.md](HOW_TO_INDEX.md). Закрыто 2026-02-11. См. CHANGES §0.4dz. |

---

## Приоритет: высокий (горячие пути)

| Файл | Контекст |
|------|----------|
| `knowledge_os/app/smart_worker_autonomous.py` | Воркер задач — критичный путь (TODO latency_ms закрыт 2026-02-08) |
| `knowledge_os/app/orchestrator.py` | Закрыто (2026-02-08): автономный рекрутинг через expert_generator.recruit_expert(domain). |
| `knowledge_os/app/agent_protocol.py` | Закрыто (2026-02-08): _send_message — direct dispatch по реестру агентов + Event Bus (AGENT_MESSAGE) при отсутствии агента. |

---

## Приоритет: средний (расширения)

| Файл | Контекст |
|------|----------|
| `knowledge_os/app/extended_thinking.py` | Закрыто (2026-02-08): confidence через _calculate_confidence(thinking_steps). |
| `knowledge_os/app/plan_decomposer.py` | Закрыто (2026-02-08): check_for_missing_info и refine_subplan через LLM (run_smart_agent_async). |
| `knowledge_os/app/curiosity_engine.py` | Нет помеченных TODO в коде (парсинг # TODO в файлах — функционал). |
| `knowledge_os/app/codebase_understanding.py` | Закрыто (2026-02-08): _classify_component и classify_code_match с LLM, fallback на эвристику. |
| `knowledge_os/app/consensus_agent.py` | Нет помеченных # TODO в коде (при касании — проверить). |
| `knowledge_os/app/hierarchical_orchestration.py` | Закрыто (2026-02-11): генерация через модель; страховка с отработкой: при пустом/ошибке — повтор с упрощённым промптом (1. 2. 3.), затем эвристика по тексту (« и », « затем », запятые). Без заглушки «Подзадача 1/2/3». См. CHANGES §0.4eb. |
| `knowledge_os/app/recap_framework.py` | Закрыто (2026-02-11): в _build_context добавлен параметр results; в блок dependencies подставляются реальные результаты из results.get(dep_id, "pending"). При вызове _build_context из _execute_plan передаётся текущий словарь results. См. CHANGES §0.4dz. |
| `knowledge_os/app/query_orchestrator.py` | Закрыто (2026-02-11): подбор из БД — в select_context при наличии normalized_query вызывается enrich_context_from_db_async(goal); ILIKE по knowledge_nodes, до 5 сниппетов. См. CHANGES §0.4eb. |
| `knowledge_os/app/master_plan_generator.py` | Закрыто (2026-02-08): update_master_plan реализован — прямые поля (markdown, title, status, role_hint) и amend_instruction через LLM; StrategySessionManager: get_plan, update_plan. См. CHANGES §0.4ed. |
| `knowledge_os/app/strategy_discovery.py` | Закрыто (2026-02-08): LLM для анализа ответа и генерации уточняющих вопросов в _maybe_generate_follow_up_questions (run_smart_agent_async), до 3 вопросов, сохранение в сессию. См. CHANGES §0.4ed. |
| `knowledge_os/app/quality_assurance.py` | Нет помеченных # TODO (при касании — проверить). |
| `knowledge_os/app/safety_checker.py` | Нет помеченных # TODO (при касании — проверить). |
| `knowledge_os/app/skill_discovery.py` | Страховка с отработкой: при отсутствии api_info.function — поиск стандартных точек входа (skill_handler, run, execute) в модуле и вызов; если не найдено — явная ошибка. При api_info.function — иначе возврат ошибки, если функция не callable. См. CHANGES §0.4eb. |
| `knowledge_os/app/model_enhancer.py` | Закрыто (2026-02-08): векторный поиск через pgvector в retrieve_enhanced_context — get_embedding + ORDER BY embedding <=> $1::vector; fallback на ключевые слова при отсутствии embedding. См. CHANGES §0.4ed. |
| `knowledge_os/app/early_warning_system.py` | Закрыто (2026-02-08): интеграция Telegram (EARLY_WARNING_TELEGRAM_BOT_TOKEN, EARLY_WARNING_TELEGRAM_CHAT_ID) и Email (EARLY_WARNING_EMAIL_TO, SMTP_*) в escalate_critical_warnings. См. CHANGES §0.4ed. |
| `knowledge_os/app/self_learning_agent.py` | Закрыто (2026-02-08): CREATE TABLE IF NOT EXISTS для learning_tasks и learning_sessions. |

---

## Приоритет: низкий (скрипты, legacy)

| Файл | Контекст |
|------|----------|
| `knowledge_os/scripts/auto_generate_tests.py` | 5 TODO — шаблонные строки в сгенерированных стабах («Implement test»); при генерации создаются заглушки, см. docs. |
| `knowledge_os/scripts/optimize_symbol_parameters.py` | Закрыто (2026-02-08): передача params в AdvancedBacktest (_symbol_params_cache), grid search по PARAMETER_GRID (до 12 комбинаций). |
| `src/database/signal_live.py` | Условия включения: docs/SIGNALS_TODO_REENABLE.md (стр. ~4022, ~5443). При касании — по документу. |
| `src/signals/signal_live.py` | ML фильтр: docs/SIGNALS_TODO_REENABLE.md (стр. ~5880). При касании — по документу. |
| `knowledge_os/src/signals/signal_live.py` | При касании — проверить на TODO, сверять с SRC_AND_KNOWLEDGE_OS_BOUNDARIES. |
| `knowledge_os/src/monitoring/data_quality.py` | При касании — закрыть или вынести сюда с контекстом. |
| Остальные scripts/ | monitoring, backtest, integration — при касании закрывать или обновлять эту таблицу. |

---

## Рекомендации (команда)

- **Игорь (Backend):** при правках в smart_worker, orchestrator — закрывать или выносить TODO в этот документ с датой.
- **Анна (QA):** при добавлении тестов — проверить auto_generate_tests.py.
- **При изменении модуля:** либо закрыть TODO, либо обновить эту таблицу (ссылка из кода: `# See docs/TODO_FIXME_BACKLOG.md`).

---

*Документ обновляется при закрытии или добавлении TODO. Связь: PROJECT_GAPS_ANALYSIS §1, VERIFICATION_CHECKLIST §5.*
