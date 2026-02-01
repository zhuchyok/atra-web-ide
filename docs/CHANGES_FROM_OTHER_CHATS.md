# Правки из других чатов — сводка для агента

Документ собирает ключевые изменения и улучшения, сделанные в других чатах, чтобы новый контекст (агент/чат) мог опираться на уже внедрённое.

---

## 1. Victoria: один сервис, три уровня (8010)

- **Victoria Agent / Enhanced / Initiative** — один сервис на порту **8010**, три уровня возможностей в одном процессе.
- Для полноценной работы **все три уровня должны быть запущены** (USE_VICTORIA_ENHANCED=true, ENABLE_EVENT_MONITORING=true).
- Проверка: `GET http://localhost:8010/status` → `victoria_levels`: agent, enhanced, initiative (все true).
- **Автопроверка и автовключение:** скрипты `scripts/check_and_start_containers.sh` и `scripts/system_auto_recovery.sh` всегда проверяют три уровня; если enhanced или initiative выключены — автоматически перезапускают victoria-agent.
- Детали: `docs/VICTORIA_PROCESS_FULL.md`, `.cursorrules` (раздел Компоненты).

---

## 2. Correlation ID и уточняющие вопросы

- **Correlation ID:** заголовок `X-Correlation-ID` или автогенерация; поле в TaskResponse, в 202/GET status, в knowledge.metadata.
- **Уточняющие вопросы:** при неоднозначной задаче (эвристики в `_check_ambiguity`) возвращается `status: "needs_clarification"`, `clarification_questions`, `suggested_restatement`; выполнение не запускается. Для выполнения используется `restated_goal`.
- Файлы: `src/agents/bridge/victoria_server.py`.
- Детали: `docs/IMPROVEMENTS_IMPLEMENTED.md`.

---

## 3. Кэш в LocalAIRouter

- Кэш по ключу (prompt, category, model), TTL 30 мин, max 500 записей; возвращается кортеж (result, routing_source).
- Статистика: `_prompt_cache_hits`, `_prompt_cache_misses`.
- Файл: `knowledge_os/app/local_router.py`.
- Детали: `docs/IMPROVEMENTS_IMPLEMENTED.md`.

---

## 4. Архитектура: кто выполняет и кто кому докладывает

- **Department Heads:** «сотрудники» (эксперты из БД) выполняют через **локальные модели** внутри процесса Victoria (`ai_core.run_smart_agent_async`). Veronica (8011) **не вызывается**. Итог собирает Victoria.
- **Делегирование:** Victoria отправляет задачу на Veronica (8011) по HTTP; Veronica выполняет и возвращает результат Victoria → пользователю.
- Детали: `docs/ARCHITECTURE_FULL.md` (раздел «Кто выполняет задачу и кто кому докладывает»).

---

## 5. Task plan и Task Distribution

- План от Victoria может возвращаться как структурированный `task_plan_struct`; Task Distribution использует его без повторного вызова Victoria для парсинга.
- Smart Worker проверяет результат через общий валидатор перед отметкой completed.
- Детали: `docs/ARCHITECTURE_FULL.md` (схема и текст).

---

## 6. Таймауты для тяжёлых моделей

- 180 сек мало: тяжёлая модель может долго запускаться + обработка локальными моделями.
- **Backend:** `VICTORIA_TIMEOUT` по умолчанию **600** сек (config: `victoria_timeout`).
- Чат и клиенты Victoria должны использовать этот таймаут (или больше) для вызовов `/run`.
- Файлы: `backend/app/config.py`, `backend/app/services/victoria.py`, при необходимости — chat router, Telegram bot, scripts.

---

## 7. Исправления багов (из чатов)

- Исправлен отступ блока `if best:` в `_ensure_best_available_models` (victoria_server.py).
- Dashboard: обработка отсутствующих данных (get/or '', strftime, stderr/stdout), консолидация traceback, логика _categorize_task для сложных задач.
- Детали: `docs/IMPROVEMENTS_IMPLEMENTED.md`, `docs/ARCHITECTURE_IMPROVEMENTS_ANALYSIS.md` (раздел «Реализовано»).

---

## 8. Маршрутизация: эксперты первыми (Veronica — «руки»)

- **PREFER_EXPERTS_FIRST** (по умолчанию `true`): execution-задачи («сделай», «напиши код», «создай API») идут в **Victoria Enhanced** (85 экспертов в БД); в **Veronica** — только простые одношаговые запросы («покажи файлы», «выведи список», «прочитай файл»). Реальная роль Veronica — исполнитель шагов (руки), не «решатель».
- **Исправлен баг** в `task_delegation.select_best_agent`: блок «если нет required_capabilities» был с неправильным отступом; код подсчёта agent_scores стал достижим.
- Файлы: `src/agents/bridge/task_detector.py`, `knowledge_os/app/task_delegation.py`, `knowledge_os/docker-compose.yml` (victoria-agent: PREFER_EXPERTS_FIRST).
- Детали: `docs/VERONICA_REAL_ROLE.md`, `.cursorrules` (раздел «Маршрутизация: эксперты первыми»).

---

## 9. Документы для углубления

| Тема | Документ |
|------|----------|
| Полная архитектура, схема, порты | `docs/ARCHITECTURE_FULL.md` |
| Victoria: процесс от запроса до ответа | `docs/VICTORIA_PROCESS_FULL.md` |
| Внедрённые улучшения (Correlation ID, кэш, уточняющие вопросы) | `docs/IMPROVEMENTS_IMPLEMENTED.md` |
| Анализ улучшений, что внедрить | `docs/ARCHITECTURE_IMPROVEMENTS_ANALYSIS.md` |
| Обновление PLAN.md (компоненты 54+) | `PLAN_UPDATE_SUMMARY.md` |
| Фиксы (Scout, Victoria, сервер, чат и др.) | `docs/*FIX*.md`, `docs/mac-studio/*.md` |
| Реальная роль Veronica, PREFER_EXPERTS_FIRST | `docs/VERONICA_REAL_ROLE.md` |
| Цепочка Victoria → эксперты: нестабильности, таймауты, чеклист | `docs/TELEGRAM_VICTORIA_CHAIN_CHECKLIST.md` |

---

*Сводка актуализирована с учётом правок из чатов. При добавлении новых изменений — дополнять этот документ и при необходимости .cursorrules.*
