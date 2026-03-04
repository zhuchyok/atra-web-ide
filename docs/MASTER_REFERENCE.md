# Единый справочник проекта ATRA Web IDE (Master Reference)

**«Библия» проекта** — это **этот документ + связка документов**, на которые он ссылается. Когда говорят **«библия»**, имеется в виду: изучить **docs/MASTER_REFERENCE.md** и при необходимости связанные документы:

- **docs/COGNITIVE_CODE.md** (Когнитивный кодекс: стандарты критического мышления).
- **PROJECT_ARCHITECTURE_AND_GUIDE**, **ARCHITECTURE_FULL**, **CURRENT_STATE_WORKER_AND_LLM**.
- **CHANGES_FROM_OTHER_CHATS.md** (Лог изменений).
- **VERIFICATION_CHECKLIST**, **DASHBOARDS_AND_AGENTS_FULL_PICTURE**.
  Закреплено в **.cursorrules** (раздел «Библия проекта»).

**Назначение:** при любых вопросах по разработке, изменениям, архитектуре, логике, портам, компонентам — **ищем здесь**. При добавлении нового или смене подхода — **отражаем здесь**. Документ всегда актуален.

**Правило репо:** правки вносить **в репозиторий того проекта, где живёт код**. setki-21 → репо setki-21; atra → репо atra; код Web IDE / Knowledge OS → atra-web-ide. Не править код setki-21 из atra-web-ide и наоборот.

**Quick links:** [CHANGES](CHANGES_FROM_OTHER_CHATS.md) · [VERIFICATION](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) · [CURATOR_RUNBOOK](CURATOR_RUNBOOK.md) · [CONTRIBUTING](../CONTRIBUTING.md) · [FAQ](FAQ.md) · [HOW_TO_INDEX](HOW_TO_INDEX.md)

**Обновлено:** 2026-03-03

---

## Wisdom Era Status (Singularity 21.5: Total Dominance)

**Архитектура:** Единый Интеллект v3.5. Мозг (MLX, порт 11435, Victoria Wisdom v3.5) + Руки (Ollama, victoria-wisdom-v3.5, KEEP_ALIVE=-1). Эксперты участвуют через оркестратор; v3.5 MoE (35B) обеспечивает бесшовную связь между планом и кодом.

**Полноценная Виктория (v3.5):** (1) **MLX (мозг):** `VICTORIA_MLX_BRAIN=true` — предзагрузка `victoria-wisdom-v3.5` (Pure MLX, Q5_K_M). (2) **Ollama (руки):** `victoria-wisdom-v3.5` загружена (GGUF, Q5_K_M), `OLLAMA_KEEP_ALIVE=-1` (бессмертная). (3) **Дефибриллятор:** активен на порту 9099. (4) **Victoria-agent:** использует v3.5 для всех критических фаз (Think/Act).

**Самовосстановление:** Система мониторит v3.5 в обоих каналах. При сбое MLX происходит мгновенный fallback на Ollama v3.5 без потери контекста.

**Последний аудит (03.03.2026):** Переход с 30B на 35B MoE (Qwen 3.5). Скорость загрузки в MLX: 4.6с. Личность подтверждена. Все эксперты уведомлены о смене ядра.

---

Последние изменения (2026-03-04): **Adaptive Ollama Memory Management & MLX Recovery Unload.** (1) Внедрена централизованная политика `app.ollama_keep_alive_policy` для всех вызовов Ollama (router, executor, ai_core, embeddings). (2) Реализован `MLX_RAM_RESERVE_GB` (32GB) для защиты памяти "Мозга" при работе Ollama. (3) Добавлена автоматическая выгрузка fallback-моделей из Ollama (`keep_alive=0`) при восстановлении MLX (событие "MLX Recovery") с дебаунсом 60с. (4) `victoria-wisdom-v3.5` в Ollama становится бессмертной (`-1`) только при падении MLX. См. CHANGES §28.

Последние изменения (2026-03-04): **Adaptive Ollama Memory Management.** (1) Глобальный `OLLAMA_KEEP_ALIVE` установлен в 10 минут (600с) для всех моделей. (2) `victoria-wisdom-v3.5` удалена из `IMMORTAL_MODELS` для экономии памяти Mac Studio. (3) В `local_router.py` внедрена логика «Fallback Immortality»: ядро v3.5 становится бессмертным в Ollama только если MLX-сервер («Мозг») недоступен. См. CHANGES §27.

Последние изменения (2026-03-03): **UI/UX Unification & Layout Stability.** (1) Унифицированы отступы и высота Hero-секций на всех страницах setki-21. (2) Исправлены «прыжки» верстки при переключении вкладок. (3) Хлебные крошки выведены из потока (absolute). См. CHANGES §26.

Последние изменения (2026-03-03): **Singularity 21.5: Victoria v3.5 Total Dominance.** (1) Полный переход на Qwen 3.5 MoE (35B) в MLX и Ollama. (2) Унификация знаний: Мозг и Руки теперь идентичны. (3) v3.5 добавлена в `IMMORTAL_MODELS` (бессмертные). (4) Обновлен `.env` и `local_router.py` для приоритета v3.5. См. CHANGES §25.

Последние изменения (2026-02-26): **Quick links, CONTRIBUTING по шагам, правило репо, FAQ.** В README и MASTER_REFERENCE добавлены блоки Quick links; CONTRIBUTING — таблица «Куда идти» (баг/предложение/вопрос), оглавление, правило репо, help wanted; создан docs/FAQ.md; в библии — правило репо, ссылки на FAQ, политика версий (Python 3.11+, Node 18+), метрики агентов. См. CHANGES §0.5q.

---

Последние изменения (2026-02-24): **Эра Мудрости: Совет Директоров и дефибриллятор.** (1) Закрыты 170 висящих strategy_sessions (active→cancelled). (2) Введён дефибриллятор MLX: `scripts/host_recovery_listener.py` (порт 9099), RECOVERY_WEBHOOK_URL в оркестраторе — при падении Ollama/MLX вызывается автовосстановление на хосте. (3) Handoff в новый чат: `docs/SESSION_HANDOFF_2026_02_24.md`. (4) Запущен один прогон run_board_meeting(); новые директивы — в board_decisions и на дашборде. См. CHANGES §0.5b.
