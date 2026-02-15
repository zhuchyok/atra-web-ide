# Что не сделано и недоделано

**Цель:** один список открытых пунктов по проекту — из PROJECT_GAPS, VICTORIA_TASK_CHAIN_FULL, NEXT_STEPS, TODO_FIXME_BACKLOG. **Обновлено:** 2026-02-11.

---

## Закрыто в этой сессии / Не делаем (причины)

**Закрыто:** порог покрытия в CI поднят с 5% до 8% (замер unit knowledge_os ~12%); роль куратора-наставника и эталон list_files (CURATOR_RUNBOOK §0, CHANGES §0.4ct).

**Не делаем в этой сессии (и почему):**

| Пункт | Причина |
|-------|--------|
| Секреты в проде (Vault и т.д.) | Нет прод-окружения; нужна инфра и политика. |
| Аутентификация /health, /metrics | Реализация «по необходимости»; решение есть. |
| Реализация исполнения по assignments | Большая фича; решение «план = подсказка» зафиксировано в NEXT_STEPS §5. |
| Сведение дублирования src/ и knowledge_os | Крупный рефакторинг; при правках сверять SRC_AND_KNOWLEDGE_OS_BOUNDARIES. |
| Закрытие всех TODO (hierarchical_orchestration, recap_framework и др.) | По бэклогу — закрывать при касании модулей. |
| signal_live, data_quality | По SIGNALS_TODO_REENABLE и бэклогу — при касании. |

---

## Действия сейчас (погнали)

| Что делать | Как |
|------------|-----|
| **Куратор: полный прогон** | `CURATOR_MAX_WAIT=900 ./scripts/run_curator_scheduled.sh`. **launchd включён:** ежедневно 9:00 (`setup_curator_launchd.sh`), логи ~/Library/Logs/atra-curator.log. Отчёт в `docs/curator_reports/curator_*.json`. |
| **После прогона — сравнение с эталоном** | `python3 scripts/curator_compare_to_standard.py --report docs/curator_reports/curator_<новый>.json --standard status_project` (и при необходимости greeting, what_can_you_do, list_files, one_line_code). Эталон list_files донастроен (2026-02-11): ключевые слова STDOUT/total для ответа через Veronica — сравнение даёт 2/6 для задачи «список файлов». |
| **При расхождении с эталоном** | Доучить в RAG: `DATABASE_URL=... knowledge_os/.venv/bin/python scripts/curator_add_standard_to_knowledge.py`. Для status_project: `--update-status`. Обновить `docs/curator_reports/standards/`. |
| **Эталон «какой статус проекта?»** | **Сделано 3/3 (2026-02-10):** RAG + fallback-эталон в коде; кураторские запросы только в Enhanced (`is_curator_standard_goal`, prefer_veronica=False). Добавлен fallback при недоступности LLM — возвращается эталонный ответ (дашборд, список задач, MASTER_REFERENCE), куратор даёт 3/3. CHANGES §0.4co. |
| **Новые эталоны** | Добавлять в `docs/curator_reports/standards/` по новым типам запросов, затем в RAG через `curator_add_standard_to_knowledge.py` (при необходимости расширить скрипт). |
| **Стабильность** | Следить за Grafana (3002), алерт deferred_to_human; при падениях MLX/Ollama — `./scripts/system_auto_recovery.sh`. |

Остальное (план оркестратора → исполнение, секреты в проде, эмбеддинги, TODO в коде) — средний/низкий приоритет. RAG Redis реализован как опция (NEXT_STEPS §2). После правок в Victoria/Enhanced рекомендуется: `./scripts/run_all_system_tests.sh`, при необходимости пересборка образа victoria-agent и прогон куратора (VERIFICATION_CHECKLIST п.38, CURATOR_RUNBOOK §3). **При следующем поднятии стека (Victoria + сервисы):** быстрый прогон куратора или сравнение с эталоном — проверить эталоны после внедрённых изменений. Полный список ниже и в TODO_FIXME_BACKLOG.md.

---

## 1. Цепочка и оркестрация

| Что | Статус | Где |
|-----|--------|-----|
| **План оркестратора не ведёт к исполнению** | Решение зафиксировано | IntegrationBridge возвращает assignments и strategy; Victoria подставляет в контекст. Исполнение по assignments в POST /run не реализовано. | VICTORIA_TASK_CHAIN_FULL §6 |
| **Решение:** оставить «план = подсказка» до доработки | Принято | Зафиксировано в NEXT_STEPS_CORPORATION.md §5. При доработке — либо исполнение по assignments, либо явно «план всегда только контекст». |

---

## 2. Масштаб и инфраструктура

| Что | Статус | Где |
|-----|--------|-----|
| **RAG-кэш в Redis** | Сделано (опция, 2026-02-10) | RAG_CACHE_BACKEND=memory|redis в victoria_server; при redis — REDIS_URL (в docker-compose для victoria-agent задан redis://redis:6379). По умолчанию memory. | NEXT_STEPS §2, CHANGES §0.4cr |
| **Секреты в проде** | Не сделано | Пароли/ключи в .env и compose; в проде — секрет-менеджер (Vault, облако), не коммитить .env. | PROJECT_GAPS §4, VERIFICATION §5 |
| **Аутентификация /health, /metrics** | Решение есть, реализация по необходимости | Внутренняя сеть = принять риск; иначе — auth или network policy. | VERIFICATION §5 |

---

## 3. Качество и тесты

| Что | Статус | Где |
|-----|--------|-----|
| **Порог покрытия в CI** | Сделано (2026-02-11) | В pytest-knowledge-os.yml задан COVERAGE_FAIL_UNDER=8 (оба job: no-db и with-db); замер unit knowledge_os ~12%. | VERIFICATION §2, PROJECT_GAPS §2 |
| **E2E Playwright (чат, health)** | Сделано (2026-02-09) | Тесты в frontend/tests/e2e/ (chat.spec.cjs, health.spec.cjs); запуск: `cd frontend && npm run e2e`; документировано в TESTING_FULL_SYSTEM, HOW_TO_INDEX, CONTRIBUTING. | CONTRIBUTING §2, TESTING_FULL_SYSTEM §2 |
| **Полный e2e «стратегический вопрос → board → Victoria»** | Сделано (2026-02-09) | Скрипт `./scripts/test_strategic_chat_e2e.sh`; описание в TESTING_FULL_SYSTEM §2. | TESTING_FULL_SYSTEM §2 |
| **Линтер по изменённым путям в CI** | Сделано (2026-02-09) | В pytest-knowledge-os.yml job lint: ruff только по изменённым .py (backend/, knowledge_os/, src/); без || true. | PROJECT_GAPS §3 |

---

## 4. Данные и RAG

| Что | Статус | Где |
|-----|--------|-----|
| **Эмбеддинги не у всех узлов knowledge_nodes** | Частично | **Все пути записи в app/ и observability/ (2026-02-11) по возможности сохраняют embedding:** rest_api, orchestrator, enhanced_orchestrator, streaming_orchestrator, enhanced_expert_evolver, expert_evolver, nightly_learner (3), knowledge_applicator, skill_discovery, strategic_board (2), dashboard_daily_improver, expert_council_discussion, researcher, expert_generator, process_expert_task, ad_generator, meta_synthesizer, knowledge_bridge (knowledge_os/src/ai). Уже с embedding: smart_worker_autonomous, corporation_knowledge_system, enhanced_scout_researcher, scout_researcher, main, server_46_knowledge_extractor, corporation_complete_knowledge, скрипты sync. Старые записи в БД без embedding — постепенно дополнять при обновлении или миграцией. | PROJECT_GAPS §6, VERIFICATION §3 |

---

## 5. TODO/FIXME в коде (низкий приоритет)

| Что | Статус | Где |
|-----|--------|-----|
| **auto_generate_tests.py** | 5 TODO — шаблонные «Implement test» в стабах | При генерации тестов — заглушки; при касании обновлять. | TODO_FIXME_BACKLOG |
| **signal_live, data_quality, прочие scripts/** | TODO в src/database, signals, monitoring | Закрывать при правках в этих модулях. | TODO_FIXME_BACKLOG |

---

## 6. Документация и процесс

| Что | Статус | Где |
|-----|--------|-----|
| **Эталоны в standards/** | Накапливать по мере прогонов | docs/curator_reports/standards/; использовать при прогонах и при добавлении в knowledge_nodes. | NEXT_STEPS §3 |
| **Куратор по расписанию** | Сделано (2026-02-09) | run_curator_scheduled.sh + пример cron в CURATOR_RUNBOOK; launchd: `bash scripts/setup_curator_launchd.sh` (ежедневно 9:00). | CURATOR_RUNBOOK, setup_curator_launchd.sh |
| **Дублирование src/ и knowledge_os/** | Задокументировано, не сведено | При правках сверять SRC_AND_KNOWLEDGE_OS_BOUNDARIES; при необходимости выносить общую логику в один модуль. | PROJECT_GAPS §1 |

---

## 7. Приоритеты (кратко)

1. **Высокий (уже закрыто в основном):** CI с pytest, один воркер, не хранить пароли в репо.
2. **Средний (осталось):** RAG Redis при масштабе; решение «план = контекст или исполнение»; мониторинг deferred_to_human (алерт есть). Порог покрытия в CI — закрыт (8%, поднят 2026-02-11).
3. **Низкий:** E2E Playwright (чат, health) — сделано; полный e2e стратегия→board — сделано (скрипт + док); линтер по путям в CI — сделано; закрытие оставшихся TODO при касании модулей.

---

## 8. Связь с документами

- **PROJECT_GAPS_ANALYSIS_2026_02_05.md** — недостатки по зонам.
- **VICTORIA_TASK_CHAIN_FULL.md** — разрывы цепочки (§6), рекомендации (§7).
- **NEXT_STEPS_CORPORATION.md** — RAG Redis, куратор, эталоны.
- **TODO_FIXME_BACKLOG.md** — приоритизация TODO в коде.
- **ROADMAP_CORPORATION_LIKE_AI.md** — когда корпорация «как я», что дальше.
- **KNOWLEDGE_BASE_USAGE.md** — кто и как использует накапливаемую базу знаний (Victoria, Veronica, оркестраторы, эксперты).
- **HOW_TO_INDEX.md** — единый индекс «как что делать» для команды и агентов (runbook’и, команды, быстрая шпаргалка).

- **CORPORATION_CHECK.md** — пошаговая проверка корпорации: правильно ли делают; причина, как нужно, переделать до правильного.

При закрытии пунктов обновлять этот документ и при необходимости MASTER_REFERENCE, CHANGES_FROM_OTHER_CHATS.
