# Проект Сетки 21 — подключение к корпорации

Проект зарегистрирован в реестре корпорации. Victoria, Veronica и оркестратор обслуживают его параллельно с atra-web-ide и atra.

**Автоматизация:** setki-21 добавлен в сидер миграции `add_projects_table.sql` и в `DEFAULT_PROJECT_CONFIGS` (project_registry.py). При применении миграций и при новом деплое проект уже будет в реестре; ручная регистрация не требуется.

## Регистрация вручную (если БД была без миграции с сидером)

Если таблица `projects` уже существовала до обновления миграции и setki-21 в ней нет, выполните из корня репо:

```bash
# Требуется: Knowledge OS (PostgreSQL) запущен, DATABASE_URL в .env или по умолчанию
python scripts/register_project.py setki-21 "Сетки 21" --description "Проект Сетки 21 — корпорация ведёт"
```

Или через API (Knowledge OS на порту 8002):

```bash
curl -X POST http://localhost:8002/api/projects/register \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"slug": "setki-21", "name": "Сетки 21", "description": "Проект Сетки 21 — корпорация ведёт"}'
```

После регистрации перезапустите агенты:

```bash
docker compose -f knowledge_os/docker-compose.yml restart victoria-agent veronica-agent
```

## В репо Сетки 21 (или atra-web-ide при переключении контекста)

В `.env` задать:

```
PROJECT_CONTEXT=setki-21
PROJECT_NAME=setki-21
VICTORIA_URL=http://localhost:8010
KNOWLEDGE_OS_API_URL=http://localhost:8002
```

Backend передаёт `project_context` в Victoria; задачам и чату будет присваиваться контекст `setki-21`.

## Дашборд

Во вкладке «📁 Проекты» корпорации (порт 8501) — setki-21 появится в списке. Фильтр задач по `project_context=setki-21`.
