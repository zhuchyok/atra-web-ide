# Руководство для контрибьюторов (Contributing Guide)

**Для кого:** разработчики и участники команды ATRA Web IDE.  
**Связь:** [HOW_TO_INDEX.md](docs/HOW_TO_INDEX.md) — «как что сделать»; [MASTER_REFERENCE.md](docs/MASTER_REFERENCE.md) — библия проекта.

---

## 1. С чего начать

- **Архитектура и запуск:** [docs/PROJECT_ARCHITECTURE_AND_GUIDE.md](docs/PROJECT_ARCHITECTURE_AND_GUIDE.md) — структура, порты, порядок запуска (сначала Knowledge OS, затем Web IDE).
- **Быстрый старт:** [README.md](README.md) — установка, `docker compose`, локальный backend/frontend.
- **Роли и эксперты:** [.cursor/README.md](.cursor/README.md) — индекс правил Cursor; [configs/experts/team.md](configs/experts/team.md) — команда и соответствие ролям.

---

## 2. Как тестировать

- **Полный обзор тестов:** [docs/TESTING_FULL_SYSTEM.md](docs/TESTING_FULL_SYSTEM.md) — backend, knowledge_os, один скрипт `./scripts/run_all_system_tests.sh`.
- **Unit-тесты:**  
  - Backend: `pytest backend/app/tests/ -q`  
  - Knowledge OS: `pytest knowledge_os/tests/ -q` (без БД по умолчанию; с БД — см. TESTING_FULL_SYSTEM).
- **E2E (Playwright):** чат и health. Запуск после поднятия сервисов:
  ```bash
  cd frontend && npm run e2e
  ```
  Переменные: `BASE_URL=http://localhost:3000`, `BACKEND_URL=http://localhost:8080`. Конфиг: `frontend/tests/e2e/playwright.config.cjs`.
- **Перед коммитом:** по возможности прогнать затронутые тесты; при правках в воркере/Ollama/MLX/Victoria — см. [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](docs/VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §1 (что проверять).
- **Скрипты с длительным выполнением:** при запуске куратора, полного прогона тестов, E2E или load test **из среды с таймаутом** (Cursor, CI) задавать timeout не меньше указанного в runbook: куратор `--quick` — ≥ 10 мин, полный прогон куратора — ≥ 30 мин. Иначе процесс может быть убит по внешнему лимиту. См. VERIFICATION §3 (причина «Прогон куратора прерывается по таймауту»), §5, [CURATOR_RUNBOOK.md](docs/CURATOR_RUNBOOK.md) §1.

---

## 3. Методология и правила

- **Библия проекта:** при изменениях сверяться с [MASTER_REFERENCE.md](docs/MASTER_REFERENCE.md) и при необходимости обновлять его (раздел «Последние изменения») и [CHANGES_FROM_OTHER_CHATS.md](docs/CHANGES_FROM_OTHER_CHATS.md).
- **При правках в зоне ответственности:** открыть [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](docs/VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §5 «При следующих изменениях» (чат, воркер, Ollama/MLX, Совет Директоров, дашборд и т.д.) и выполнить пункты по затронутым компонентам.
- **При появлении сбоя:** раздел §3 того же чеклиста — причины сбоев и как не допускать; при новой причине — дополнить таблицу.
- **Секреты:** не коммитить `.env` с паролями и ключами; в проде — секрет-менеджер (Vault, облако). См. чеклист §5.

**Чеклист при коммите:** после изменений в backend/chat/Victoria — прогнать `pytest backend/app/tests/ -q` и при необходимости `pytest knowledge_os/tests/ -q`; при изменении маршрутизации или эталонов — по желанию куратор или сравнение с эталоном (`scripts/curator_compare_to_standard.py`). После значимых правок в архитектуре или контуре — обновить [MASTER_REFERENCE.md](docs/MASTER_REFERENCE.md) (раздел «Последние изменения») и при необходимости [CHANGES_FROM_OTHER_CHATS.md](docs/CHANGES_FROM_OTHER_CHATS.md).

---

## 4. Как добавить эксперта / изменить команду

- **Единый источник:** [configs/experts/employees.json](configs/experts/employees.json). Добавить запись → запустить `python scripts/sync_employees.py` → при необходимости правило в `.cursor/rules/` и строка в [configs/experts/team.md](configs/experts/team.md).
- Подробный runbook: [docs/EXPERT_CONNECTION_ARCHITECTURE.md](docs/EXPERT_CONNECTION_ARCHITECTURE.md) §4.

---

## 5. Развитие Victoria и корпорации

- **Дорожная карта:** [docs/ROADMAP_CORPORATION_LIKE_AI.md](docs/ROADMAP_CORPORATION_LIKE_AI.md) — когда корпорация «как я», приоритеты (куратор по расписанию, эталоны в RAG, RAG Redis, план оркестратора).
- **Следующие шаги:** [docs/NEXT_STEPS_CORPORATION.md](docs/NEXT_STEPS_CORPORATION.md) — что сделано, RAG Redis при масштабе, эталоны, verbose steps в API.
- **Новые фичи Victoria:** при добавлении возможностей учитывать [VICTORIA_TASK_CHAIN_FULL.md](docs/VICTORIA_TASK_CHAIN_FULL.md) (цепочка задачи, делегирование, PREFER_EXPERTS_FIRST) и обновлять [configs/victoria_capabilities.txt](configs/victoria_capabilities.txt) при изменении «что умеет».

---

## 6. TODO/FIXME в коде

- **Приоритизация:** [docs/TODO_FIXME_BACKLOG.md](docs/TODO_FIXME_BACKLOG.md). При правках в модуле — либо закрыть TODO, либо обновить backlog с датой и контекстом.
- В коде можно оставлять ссылку: `# See docs/TODO_FIXME_BACKLOG.md`.

---

## 7. Ручные проверки (по желанию)

После больших изменений или перед релизом полезно пройти: [docs/MANUAL_VERIFICATION_CHECKLIST.md](docs/MANUAL_VERIFICATION_CHECKLIST.md) — полный сценарий чата (эхо/503), делегирование, Grafana Prometheus, launchd.

---

*При вопросах «как что сделать» — сначала [HOW_TO_INDEX.md](docs/HOW_TO_INDEX.md); при изменении архитектуры или контура — MASTER_REFERENCE и CHANGES.*
