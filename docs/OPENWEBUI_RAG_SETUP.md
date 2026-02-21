# Open WebUI: RAG и контекст для Singularity 15.0

Как подключить базу мудрости (Bible, .cursorrules, знания гигантов) к внешним моделям в Open WebUI.

## 1. Документы для RAG (Open WebUI Documents)

Загрузите в Open WebUI (Workspace → Documents) и привяжите к коллекции Victoria:

- **docs/MASTER_REFERENCE.md** — библия проекта, архитектура, последние изменения.
- **docs/COGNITIVE_CODE.md** — когнитивный кодекс (первые принципы, пять почему, KISS).
- **.cursorrules** — правила проекта и команда (опционально; при необходимости экспорт ключевых абзацев в один .md).

Для «знаний гигантов» (выкачанная мудрость по ИИ от корпораций и моделей):

- Убедитесь, что **knowledge_os/knowledge_base/ai_research/** проиндексирована в `knowledge_nodes` (скрипт `knowledge_os/scripts/index_external_docs.py` или аналог). Тогда Victoria при запросах через `/run` уже получает этот контекст через RAG по `knowledge_nodes`.
- При желании можно выгрузить выбранные файлы из `knowledge_base` (например, промпты гигантов) в Open WebUI Documents для RAG на стороне Open WebUI.

## 2. Golden Persona (системный промпт)

Для моделей, которые вызывают инструмент **ask_victoria**, задайте системный промпт из **docs/SINGULARITY_15_GOLDEN_PERSONA.md** (полная или краткая версия). Так внешняя модель будет делегировать исполнение только через Victoria и не симулировать экспертов.

## 3. Инструмент ask_victoria

- **Python-инструмент для Open WebUI (рекомендуется):** `configs/openwebui_ask_victoria_tool.py` — класс `Tools` с методом `ask_victoria`. Импорт: Open WebUI → Workspace → Tools → Import Tools → указать этот файл. Valves: `VICTORIA_URL` (default `http://victoria-agent:8000`), `USE_BACKEND_PROXY` (false = вызов Victoria `/run`, true = вызов бэкенда `/api/chat/ask-victoria`), `ASK_VICTORIA_TIMEOUT` (default 600). См. **docs/OPENWEBUI_SINGULARITY_15_RUNBOOK.md**.
- **Скрипт CLI:** `scripts/openwebui_ask_victoria.py` — вызов из CLI или из кода. Переменные: `VICTORIA_URL`, `ASK_VICTORIA_TIMEOUT`.
- **Backend:** `POST /api/chat/ask-victoria` (body: `goal`, `project_context`, `user_key`) — прокси к Victoria `/run` с `use_enhanced=True`. Ответ — текст; при `?format=json` — `{"status":"success"|"error","result":"..."}`.
- **Конфиг JSON:** `configs/openwebui_ask_victoria_tool.json` — описание и OpenAI-совместимая схема для API-инструмента. URL бэкенда в Docker: `http://atra-web-ide-backend:8080/api/chat/ask-victoria`; с хоста: `http://localhost:8080/api/chat/ask-victoria`.

## 4. project_context

По умолчанию `atra-web-ide`. Если пользователь упоминает другой проект (setki-21, atra), передайте его в `project_context` при вызове ask_victoria.

## 5. Единая память (LTM)

- **Open WebUI:** передавайте стабильный `user_key` (например `openwebui-{user_id}`) в ask_victoria, чтобы ответы Victoria сохранялись в Long-Term Memory для этого пользователя.
- **Telegram:** бот передаёт `session_id=telegram-{user_id}` в Victoria; при одном и том же маппинге user_id память можно считать общей (при необходимости можно связать openwebui-id и telegram-id в одном ключе).

## 6. Чеклист перед использованием

- [ ] Victoria и при необходимости бэкенд запущены (Docker или локально); Open WebUI в одной сети с Victoria/бэкендом.
- [ ] В Open WebUI задан системный промпт из `docs/SINGULARITY_15_GOLDEN_PERSONA.md` для моделей, которые должны делегировать в Victoria.
- [ ] Инструмент ask_victoria добавлен: импорт `configs/openwebui_ask_victoria_tool.py` (см. **docs/OPENWEBUI_SINGULARITY_15_RUNBOOK.md**) или настройка по `configs/openwebui_ask_victoria_tool.json`.
- [ ] Документы MASTER_REFERENCE и COGNITIVE_CODE загружены в Open WebUI Documents при необходимости RAG.
- [ ] Проверка: запрос «Проверь бэкенд» через модель с Golden Persona → вызов ask_victoria → ответ от Victoria. При использовании бэкенда: `GET /metrics/summary` содержит `ask_victoria_total`.

**Пошаговый запуск и проверка:** см. **docs/OPENWEBUI_SINGULARITY_15_RUNBOOK.md**.

---

*План: .cursor/plans/singularity_15.0_unified_consciousness_bridge_*.plan.md*
