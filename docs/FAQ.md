# FAQ — типовые вопросы

Ответы на повторяющиеся вопросы по проекту ATRA Web IDE и Knowledge OS. При обновлении ответа меняйте только этот файл — агенты и команда получают актуальную версию.

---

## Почему Victoria не отвечает?

1. **Проверить, что контейнеры подняты:** `docker compose -f knowledge_os/docker-compose.yml ps` — victoria-agent и veronica-agent должны быть Up.
2. **Victoria (8010):** `curl -s http://localhost:8010/health` — должен вернуть 200. Если нет — перезапуск: `docker compose -f knowledge_os/docker-compose.yml restart victoria-agent`.
3. **Ollama/MLX:** Victoria ходит в LLM. Ollama: `curl -s http://localhost:11434/api/ps`. MLX (если мозг): `curl -s http://localhost:11435/api/tags`. При падении MLX срабатывает дефибриллятор (recovery listener на 9099) или ручной перезапуск: `bash scripts/start_mlx_api_server.sh`.
4. **Перегрузка:** при 503 бэкенд возвращает «Victoria временно недоступна» и Retry-After — подождать или увеличить лимит `MAX_CONCURRENT_VICTORIA` в backend config.

Подробнее: [VERIFICATION_CHECKLIST_OPTIMIZATIONS](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §3 (причины сбоев), [CURATOR_RUNBOOK](CURATOR_RUNBOOK.md).

---

## Как добавить проект в dev/?

Создайте папку в `dev/` с допустимым именем (буквы, цифры, дефис), например `dev/my-app`. Реестр проектов (project_registry) сканирует `/workspace/dev`; новый проект подхватывается при следующей загрузке реестра (TTL кэша до 5 мин). Правка docker-compose не нужна. Контекст: `PROJECT_CONTEXT=my-app` или в чате: «перейди в проект my-app».

См. [GATEWAY_AND_STACK_QUICK](GATEWAY_AND_STACK_QUICK.md) §5, [CHANGES_FROM_OTHER_CHATS](CHANGES_FROM_OTHER_CHATS.md) §0.5l.

---

## Какой порядок запуска контейнеров?

1. Сначала **Knowledge OS** (агенты, БД, Redis): `docker compose -f knowledge_os/docker-compose.yml up -d`.
2. Через 15–20 сек — **Web IDE**: `docker compose up -d`.
3. Проверка: `curl -s http://localhost:8080/health`, `curl -s http://localhost:8010/status`.

Если Docker не запущен — Victoria локально: `bash START_VICTORIA_LOCAL.sh` (порт 8010). См. README и [PROJECT_ARCHITECTURE_AND_GUIDE](PROJECT_ARCHITECTURE_AND_GUIDE.md).

---

## Где смотреть метрики и логи?

- **Метрики backend:** `GET /metrics`, `GET /metrics/summary` (доля fallback, chat_expert_answer_total и т.д.).
- **Grafana Web IDE:** порт 3002. Дашборды — «Web IDE» / «Knowledge OS» в левой панели.
- **Логи:** Docker — `docker compose -f knowledge_os/docker-compose.yml logs -f victoria-agent`; ротация настроена (max-size: 10m, max-file: 3).

Таблица метрик по моделям/агентам (время ответа, регрессии): заполняется по данным `/metrics` и прогонов; см. [MASTER_REFERENCE](MASTER_REFERENCE.md) § «Что перезагрузить» и ссылки на MODEL_TIMING_REFERENCE, MODEL_COLD_START_REFERENCE.

---

## Как запустить тесты?

- **Все системные:** `./scripts/run_all_system_tests.sh` (backend + knowledge_os).
- **Только backend:** `pytest backend/app/tests/ -q`
- **Только knowledge_os:** `pytest knowledge_os/tests/ -q`
- **E2E (Playwright):** после поднятия frontend/backend: `cd frontend && npm run e2e`

См. [TESTING_FULL_SYSTEM](TESTING_FULL_SYSTEM.md), [CONTRIBUTING](../CONTRIBUTING.md) §2.

---

## Скрипт/куратор прерывается по таймауту

Среда запуска (Cursor, CI, IDE) может убивать процесс по своему таймауту. Задавайте **timeout не меньше** требуемого: куратор `--quick` — ≥ 10 мин, полный прогон куратора — ≥ 30 мин. В новых долгих скриптах указывайте в docstring/runbook рекомендуемый timeout.

См. [VERIFICATION_CHECKLIST_OPTIMIZATIONS](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §3, §5, [CURATOR_RUNBOOK](CURATOR_RUNBOOK.md) §1, [CONTRIBUTING](../CONTRIBUTING.md) §2.

---

## В каком репозитории править код?

В репозитории **того проекта, где живёт код**. Код setki-21 — в репо setki-21; код atra — в репо atra; код Web IDE и Knowledge OS — в atra-web-ide. Не вносить правки к setki-21 из atra-web-ide и наоборот, чтобы не было рассинхрона.

См. [MASTER_REFERENCE](MASTER_REFERENCE.md) (правило репо), [CONTRIBUTING](../CONTRIBUTING.md).

---

_При отсутствии ответа в FAQ — [HOW_TO_INDEX](HOW_TO_INDEX.md), [MASTER_REFERENCE](MASTER_REFERENCE.md), команда экспертов (configs/experts/team.md)._
